from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Coroutine
from typing import Any


def next_boundary(now: float | None = None) -> float:
    return math.floor(now if now is not None else time.time()) + 1.0


class PendingTasks:
    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
