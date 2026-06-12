from __future__ import annotations

import asyncio
import time
import uuid

import httpx

from ..common import Logger, password_hash
from ..common.auth import USER_AGENT
from .config import Lvl2Config

LOGIN_RETRY_BACKOFF = 0.3


class Session:
    __slots__ = ("client", "username", "ready_at", "alive", "fails")

    def __init__(self, client: httpx.AsyncClient, username: str) -> None:
        self.client = client
        self.username = username
        self.ready_at = 0.0
        self.alive = True
        self.fails = 0


class SessionPool:
    def __init__(self, cfg: Lvl2Config, logger: Logger) -> None:
        self.cfg = cfg
        self.logger = logger
        self.sessions: list[Session] = []

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.cfg.base_url,
            timeout=self.cfg.req_timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2, keepalive_expiry=60.0),
        )

    async def _login(self, session: Session, retries: int = 3) -> bool:
        for attempt in range(retries):
            try:
                resp = await session.client.post(
                    "/login", data={"login": session.username, "password": password_hash(session.username)}
                )
            except httpx.HTTPError:
                await asyncio.sleep(LOGIN_RETRY_BACKOFF * (attempt + 1))
                continue
            if resp.status_code in (302, 303, 200) and "sid" in session.client.cookies:
                session.alive = True
                return True
            await asyncio.sleep(LOGIN_RETRY_BACKOFF * (attempt + 1))
        session.alive = False
        return False

    async def login_all(self) -> int:
        sem = asyncio.Semaphore(self.cfg.login_concurrency)

        async def make(i: int) -> Session | None:
            username = f"{self.cfg.username_prefix}{i}_{uuid.uuid4().hex[:8]}"
            session = Session(self._new_client(), username)
            async with sem:
                ok = await self._login(session)
            if ok:
                return session
            await session.client.aclose()
            return None

        results = await asyncio.gather(*[make(i) for i in range(self.cfg.pool_size)])
        self.sessions = [s for s in results if s is not None]
        self.logger.info(f"pool: {len(self.sessions)}/{self.cfg.pool_size} sessions authenticated")
        return len(self.sessions)

    def acquire(self, n: int) -> list[Session]:
        now = time.monotonic()
        ready = sorted((s for s in self.sessions if s.alive and s.ready_at <= now), key=lambda s: s.ready_at)[:n]
        for s in ready:
            s.ready_at = now + self.cfg.cooldown
        return ready

    @property
    def ready_count(self) -> int:
        now = time.monotonic()
        return sum(1 for s in self.sessions if s.alive and s.ready_at <= now)

    async def relogin(self, session: Session) -> None:
        session.client.cookies.clear()
        await self._login(session, retries=1)

    async def replenish(self) -> None:
        sem = asyncio.Semaphore(self.cfg.login_concurrency)

        async def fix(session: Session) -> None:
            async with sem:
                session.client.cookies.clear()
                await self._login(session, retries=1)

        async def add() -> Session | None:
            username = f"{self.cfg.username_prefix}{uuid.uuid4().hex[:10]}"
            session = Session(self._new_client(), username)
            async with sem:
                ok = await self._login(session, retries=1)
            if ok:
                return session
            await session.client.aclose()
            return None

        dead = [s for s in self.sessions if not s.alive]
        missing = max(0, self.cfg.pool_size - len(self.sessions))
        tasks = [fix(s) for s in dead] + [add() for _ in range(missing)]
        if not tasks:
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Session):
                self.sessions.append(r)

    async def aclose(self) -> None:
        await asyncio.gather(*[s.client.aclose() for s in self.sessions], return_exceptions=True)
