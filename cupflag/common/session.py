from __future__ import annotations

import asyncio

import httpx

from .auth import USER_AGENT, password_hash
from .log import Logger

LOGIN_BACKOFF_MAX = 5.0


class PlatformClient:
    def __init__(self, base_url: str, logger: Logger, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            limits=httpx.Limits(max_connections=64, max_keepalive_connections=64),
            trust_env=False,
        )

    @property
    def http(self) -> httpx.AsyncClient:
        return self._client

    async def login(self, username: str, *, retries: int = 5) -> None:
        password = password_hash(username)
        self.logger.info(f"Connecting to {self.base_url}")
        self.logger.info(f"Login: user={username}")
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                resp = await self._client.post("/login", data={"login": username, "password": password})
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(min(0.5 * 2 ** (attempt - 1), LOGIN_BACKOFF_MAX))
                continue
            if resp.status_code not in (302, 303, 200):
                raise RuntimeError(f"login failed: HTTP {resp.status_code}")
            if "sid" not in self._client.cookies:
                raise RuntimeError("login did not return a session cookie")
            self.logger.info(f"POST /login -> {resp.status_code}")
            return
        raise RuntimeError(f"login failed after {retries} attempts: {last_exc!r}")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> PlatformClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
