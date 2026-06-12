from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from .flags import FlagSink
from .log import get_logger
from .scheduling import PendingTasks


class BaseRunner(ABC):
    stats_interval = 15.0

    def __init__(self, level: str, *, out: str, verbose: bool) -> None:
        self.logger = get_logger(level)
        self.sink = FlagSink(Path(out), self.logger)
        self._stop = asyncio.Event()
        self._tasks = PendingTasks()
        self._started = 0.0

    @abstractmethod
    async def setup(self) -> None: ...

    @abstractmethod
    def workers(self) -> list[Coroutine[Any, Any, None]]: ...

    async def teardown(self) -> None: ...

    @abstractmethod
    def start_line(self) -> str: ...

    @abstractmethod
    def stats_line(self) -> str: ...

    def final_line(self) -> str:
        return f"Total: {self.sink.count} flags"

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._started

    @property
    def flags_per_min(self) -> float:
        return self.sink.count / self.elapsed * 60 if self.elapsed else 0.0

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        self._tasks.spawn(coro)

    async def sleep_or_stop(self, delay: float) -> bool:
        if delay <= 0:
            return self._stop.is_set()
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=delay)
            return True
        except TimeoutError:
            return False

    async def _stats_loop(self) -> None:
        while not self._stop.is_set():
            if await self.sleep_or_stop(self.stats_interval):
                break
            self.logger.info(self.stats_line())

    async def run(self, duration: float | None = None) -> int:
        await self.setup()
        self._started = time.monotonic()
        self.logger.info(self.start_line())
        tasks = [asyncio.create_task(w) for w in self.workers()]
        tasks.append(asyncio.create_task(self._stats_loop()))
        if duration:
            await self.sleep_or_stop(duration)
        else:
            await self._stop.wait()
        self._stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._tasks.drain()
        await self.teardown()
        self.logger.info(self.final_line())
        return self.sink.count
