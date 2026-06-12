from __future__ import annotations

import json
import statistics
import time
from collections import deque
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TextIO

import httpx

from ..common import BaseRunner, now_ts
from .clearance import ClearanceManager
from .config import Lvl3Config
from .protocol import iter_sse_events, sign_claim


class Lvl3Runner(BaseRunner):
    def __init__(self, cfg: Lvl3Config) -> None:
        super().__init__("lvl3", out=cfg.out, verbose=cfg.verbose)
        self.cfg = cfg
        self.clearance = ClearanceManager(
            cfg.base_url,
            cfg.flaresolverr_url,
            cfg.username,
            self.logger,
            ttl=cfg.clearance_ttl,
            req_timeout=cfg.req_timeout,
        )
        self._cycles = 0
        self._claims = 0
        self._rtts: deque[float] = deque(maxlen=cfg.rtt_window)
        self._iofh: TextIO | None = None

    def _io(self, **rec: Any) -> None:
        if self._iofh is None:
            return
        rec = {"ts": now_ts(), "t": round(time.monotonic(), 4), **rec}
        self._iofh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._iofh.flush()

    def _rtt(self) -> float:
        return statistics.median(self._rtts) if self._rtts else self.cfg.rtt_init

    async def _join(self) -> str | None:
        resp = await self.clearance.client.post("/v1/queue/join")
        self._io(dir="resp", kind="join", status=resp.status_code, body=resp.text[:200])
        if resp.status_code == 403:
            await self.clearance.ensure(force=True)
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        return data.get("queue_token")

    async def _claim(self, queue_token: str, book_key: str, plan: dict[str, Any]) -> None:
        timestamp = int(time.time())
        body = {
            "queue_token": queue_token,
            "book_key": book_key,
            "captcha_token": self.cfg.captcha_token,
            "timestamp": timestamp,
            "signature": sign_claim(queue_token, timestamp),
        }
        self._io(dir="req", kind="claim", plan=plan)
        self._claims += 1
        t0 = time.time()
        try:
            resp = await self.clearance.client.post("/v1/queue/claim", json=body)
        except httpx.HTTPError as exc:
            self._io(dir="resp", kind="claim", error=str(exc))
            return
        self._rtts.append(time.time() - t0)
        try:
            data = resp.json()
        except ValueError:
            self._io(dir="resp", kind="claim", status=resp.status_code, body=resp.text[:200])
            return
        self._io(dir="resp", kind="claim", status=resp.status_code, body=data)
        if data.get("status") == "ok" and data.get("flag"):
            self.sink.add(str(data["flag"]))
        else:
            reason = data.get("reason") or data.get("retry_after_ms") or ""
            self.logger.info(
                f"claim -> {data.get('status')} {reason} "
                f"[window={plan['window_ms']}ms wait={plan['wait_ms']}ms rtt={round(self._rtt() * 1000)}ms]"
            )

    async def _handle_open(self, queue_token: str, msg: dict[str, Any]) -> None:
        book_key = msg.get("book_key")
        if not book_key:
            return
        window_s = float(msg.get("window_ms", 0)) / 1000.0
        server_time = msg.get("server_time")
        claim_at = msg.get("claim_at")
        rtt = self._rtt()
        if claim_at is not None and server_time is not None:
            margin = min(self.cfg.target_margin_ms / 1000.0, self.cfg.margin_frac * window_s)
            wait_s = (float(claim_at) - float(server_time)) + margin - rtt
        else:
            margin = 0.0
            wait_s = float(msg.get("next_ms", 0)) / 1000.0
        plan = {
            "window_ms": msg.get("window_ms"),
            "wait_ms": round(wait_s * 1000),
            "margin_ms": round(margin * 1000),
            "rtt_ms": round(rtt * 1000),
        }
        if wait_s > 0:
            await self.sleep_or_stop(wait_s)
        await self._claim(queue_token, book_key, plan)

    async def _run_cycle(self) -> None:
        queue_token = await self._join()
        if not queue_token:
            return
        self._cycles += 1
        try:
            async with self.clearance.client.stream(
                "GET", "/v1/queue/wait", params={"queue_token": queue_token}
            ) as resp:
                if resp.status_code != 200:
                    return
                start = time.monotonic()
                async for event, msg in iter_sse_events(resp):
                    self._io(dir="event", kind=event, data=msg)
                    if self.stopping:
                        return
                    if event == "open":
                        await self._handle_open(queue_token, msg)
                        return
                    if event == "closed":
                        return
                    if time.monotonic() - start > self.cfg.cycle_timeout:
                        self._io(kind="cycle_timeout")
                        return
        except httpx.HTTPError:
            return

    async def _loop(self) -> None:
        while not self.stopping:
            await self.clearance.ensure()
            await self._run_cycle()

    async def setup(self) -> None:
        self._iofh = Path(self.cfg.io_log).open("a", encoding="utf-8")
        await self.clearance.ensure()

    def workers(self) -> list[Coroutine[Any, Any, None]]:
        return [self._loop() for _ in range(self.cfg.concurrency)]

    async def teardown(self) -> None:
        await self.clearance.aclose()
        if self._iofh is not None:
            self._iofh.close()

    def start_line(self) -> str:
        return f"Starting queue loop (io_log={self.cfg.io_log})..."

    def _conversion(self) -> float:
        return self.sink.count / self._claims * 100 if self._claims else 0.0

    def stats_line(self) -> str:
        return (
            f"stats: {self.sink.count} flags, {self._cycles} cycles, {self._claims} claims, "
            f"{self._conversion():.0f}% conv, {self.flags_per_min:.1f} flags/min, rtt={self._rtt() * 1000:.0f}ms"
        )

    def final_line(self) -> str:
        return (
            f"Total: {self.sink.count} flags ({self._cycles} cycles, {self._claims} claims, "
            f"{self._conversion():.0f}% conversion)"
        )
