from __future__ import annotations

import time
from abc import abstractmethod

from .runner import BaseRunner
from .scheduling import next_boundary

AIM_MAX_DELAY = 1.5


class BurstRunner(BaseRunner):
    def __init__(
        self,
        level: str,
        *,
        out: str,
        verbose: bool,
        shots: int,
        span: float,
        target_arrival: float,
        rtt_init: float,
        rtt_alpha: float,
        cooldown_factor: float,
    ) -> None:
        super().__init__(level, out=out, verbose=verbose)
        self._shots = shots
        self._span = span
        self._target_arrival = target_arrival
        self._rtt = rtt_init
        self._rtt_alpha = rtt_alpha
        self._cooldown_factor = cooldown_factor
        self._attempts = 0
        self._rate_limited = 0
        self._last_capture_t: float | None = None
        self._min_gap: float | None = None
        self._cooldown_until = 0.0

    def _update_rtt(self, sample: float) -> None:
        alpha = self._rtt_alpha
        self._rtt = (1 - alpha) * self._rtt + alpha * sample

    def _center(self) -> float:
        return self._target_arrival - self._rtt / 2

    def _offsets(self) -> list[float]:
        center = self._center()
        if self._shots <= 1:
            return [center]
        start = center - self._span / 2
        step = self._span / (self._shots - 1)
        return [start + i * step for i in range(self._shots)]

    def _on_capture(self) -> None:
        now = time.monotonic()
        if self._last_capture_t is not None:
            gap = now - self._last_capture_t
            self._min_gap = gap if self._min_gap is None else min(self._min_gap, gap)
        self._last_capture_t = now
        if self._cooldown_factor > 0 and self._min_gap is not None:
            self._cooldown_until = now + self._cooldown_factor * self._min_gap

    async def _aim(self, target: float) -> bool:
        delay = target - time.time()
        if 0 < delay < AIM_MAX_DELAY:
            await self.sleep_or_stop(delay)
        return not self.stopping

    @abstractmethod
    async def _fire(self, target: float) -> None: ...

    async def _loop(self) -> None:
        while not self.stopping:
            remaining = self._cooldown_until - time.monotonic()
            if remaining > 0:
                if await self.sleep_or_stop(remaining):
                    break
                continue
            offsets = self._offsets()
            boundary = next_boundary()
            if await self.sleep_or_stop(boundary + offsets[0] - time.time()):
                break
            for off in offsets:
                self.spawn(self._fire(boundary + off))
            if await self.sleep_or_stop(boundary + 1.0 + offsets[0] - time.time()):
                break
