from __future__ import annotations

import time
import uuid
from collections.abc import Coroutine
from typing import Any

import httpx

from ..common import BurstRunner
from .config import Lvl2Config
from .pool import Session, SessionPool

REPLENISH_INTERVAL = 8.0
NETWORK_BACKOFF = 2.0
FAILS_BEFORE_DEAD = 3


class Lvl2Runner(BurstRunner):
    def __init__(self, cfg: Lvl2Config) -> None:
        super().__init__(
            "lvl2",
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
        self.pool = SessionPool(cfg, self.logger)

    async def _capture(self, session: Session) -> None:
        headers = {"X-Request-Id": str(uuid.uuid4())}
        t0 = time.time()
        try:
            resp = await session.client.post(
                "/v1/capture", json={"captcha_token": self.cfg.captcha_token}, headers=headers
            )
        except httpx.HTTPError:
            session.ready_at = time.monotonic() + NETWORK_BACKOFF
            session.fails += 1
            if session.fails >= FAILS_BEFORE_DEAD:
                session.alive = False
            return
        self._update_rtt(time.time() - t0)
        session.fails = 0
        if resp.status_code in (401, 403):
            self.spawn(self.pool.relogin(session))
            return
        self._attempts += 1
        try:
            data = resp.json()
        except ValueError:
            return
        status = data.get("status")
        if status == "ok" and data.get("flag"):
            if self.sink.add(str(data["flag"])):
                self._on_capture()
        elif status == "rate_limited":
            self._rate_limited += 1
            retry = float(data.get("retry_after_ms", self.cfg.cooldown * 1000)) / 1000.0
            session.ready_at = time.monotonic() + retry

    async def _fire(self, target: float) -> None:
        if not await self._aim(target):
            return
        sessions = self.pool.acquire(1)
        if not sessions:
            return
        await self._capture(sessions[0])

    async def _replenisher(self) -> None:
        while not self.stopping:
            if await self.sleep_or_stop(REPLENISH_INTERVAL):
                break
            await self.pool.replenish()

    async def setup(self) -> None:
        self.logger.info(f"Connecting to {self.cfg.base_url}")
        n = await self.pool.login_all()
        if n == 0:
            raise RuntimeError("no sessions authenticated")

    def workers(self) -> list[Coroutine[Any, Any, None]]:
        return [self._loop(), self._replenisher()]

    async def teardown(self) -> None:
        await self.pool.aclose()

    def start_line(self) -> str:
        return f"Starting capture loop (pool={len(self.pool.sessions)}, shots={self._shots})..."

    def stats_line(self) -> str:
        return (
            f"stats: {self.sink.count} flags, {self._attempts} attempts, "
            f"{self._rate_limited} rate_limited, {self.pool.ready_count} ready, "
            f"{self.flags_per_min:.1f} flags/min"
        )

    def final_line(self) -> str:
        return f"Total: {self.sink.count} flags ({self._attempts} attempts, {self._rate_limited} rate_limited)"
