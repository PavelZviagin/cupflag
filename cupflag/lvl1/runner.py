from __future__ import annotations

import time
from collections.abc import Coroutine
from typing import Any

import httpx

from ..common import BurstRunner, PlatformClient
from .config import Lvl1Config


class Lvl1Runner(BurstRunner):
    def __init__(self, cfg: Lvl1Config) -> None:
        super().__init__(
            "lvl1",
            out=cfg.out,
            verbose=cfg.verbose,
            shots=cfg.shots,
            span=cfg.span,
            target_arrival=cfg.target_arrival,
            rtt_init=cfg.rtt_init,
            rtt_alpha=cfg.rtt_alpha,
            cooldown_factor=cfg.cooldown_factor,
        )
        self.cfg = cfg
        self._session: PlatformClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._session is None:
            raise RuntimeError("not connected")
        return self._session.http

    async def _capture(self) -> dict[str, Any] | None:
        t0 = time.time()
        try:
            resp = await self.http.post("/v1/capture", json={}, timeout=self.cfg.req_timeout)
        except httpx.HTTPError:
            return None
        self._update_rtt(time.time() - t0)
        self._attempts += 1
        try:
            return resp.json()
        except ValueError:
            return None

    async def _fire(self, target: float) -> None:
        if not await self._aim(target):
            return
        data = await self._capture()
        if not data:
            return
        if data.get("status") == "ok" and data.get("flag"):
            if self.sink.add(str(data["flag"])):
                self._on_capture()
        elif data.get("status") == "rate_limited":
            self._rate_limited += 1

    async def setup(self) -> None:
        self._session = PlatformClient(self.cfg.base_url, self.logger)
        await self._session.login(self.cfg.username)

    def workers(self) -> list[Coroutine[Any, Any, None]]:
        return [self._loop()]

    async def teardown(self) -> None:
        if self._session is not None:
            await self._session.aclose()

    def start_line(self) -> str:
        return "Starting capture loop..."

    def _per_flag(self) -> float:
        return self._attempts / self.sink.count if self.sink.count else 0.0

    def stats_line(self) -> str:
        return (
            f"stats: {self.sink.count} flags, {self._attempts} attempts, "
            f"{self._rate_limited} rate_limited, {self.flags_per_min:.1f} flags/min, "
            f"{self._per_flag():.1f} req/flag"
        )

    def final_line(self) -> str:
        return f"Total: {self.sink.count} flags ({self._attempts} attempts, {self._rate_limited} rate_limited)"
