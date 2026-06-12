from __future__ import annotations

import asyncio
import time

import httpx

from ..common import Clearance, FlareSolverr, Logger, password_hash

FORCE_REFRESH_GRACE = 5.0


class ClearanceManager:
    def __init__(
        self, base_url: str, flaresolverr_url: str, username: str, logger: Logger, *, ttl: float, req_timeout: float
    ) -> None:
        self.base_url = base_url
        self.username = username
        self.logger = logger
        self.ttl = ttl
        self.req_timeout = req_timeout
        self.fs = FlareSolverr(flaresolverr_url)
        self._clearance: Clearance | None = None
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("clearance not acquired; call ensure() first")
        return self._client

    def _fresh(self) -> bool:
        return self._clearance is not None and (time.monotonic() - self._clearance.obtained_at) < self.ttl

    async def ensure(self, *, force: bool = False) -> None:
        if not force and self._fresh():
            return
        async with self._lock:
            if not force and self._fresh():
                return
            if (
                force
                and self._clearance is not None
                and (time.monotonic() - self._clearance.obtained_at) < FORCE_REFRESH_GRACE
            ):
                return
            await self._refresh()

    async def _refresh(self) -> None:
        self.logger.info("solving Cloudflare challenge via FlareSolverr...")
        clearance = await self.fs.get_clearance(self.base_url + "/")
        clearance.obtained_at = time.monotonic()
        self._clearance = clearance
        if self._client is not None:
            await self._client.aclose()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.req_timeout,
            follow_redirects=False,
            trust_env=False,
            http2=True,
            headers={"User-Agent": clearance.user_agent},
            cookies=clearance.cookies,
            limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=120.0),
        )
        self.logger.info("clearance OK; logging in")
        await self._login()

    async def _login(self) -> None:
        resp = await self.client.post("/login", data={"login": self.username, "password": password_hash(self.username)})
        self.logger.info(f"login -> {resp.status_code}")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
