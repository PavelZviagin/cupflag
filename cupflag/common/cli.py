from __future__ import annotations

import argparse
import asyncio
import signal

from .log import configure
from .runner import BaseRunner


def add_common_args(parser: argparse.ArgumentParser, *, default_out: str) -> None:
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument("--out", default=default_out)
    parser.add_argument("-v", "--verbose", action="store_true")


def run(runner: BaseRunner, *, duration: float | None, verbose: bool) -> None:
    configure(verbose=verbose)

    async def _main() -> int:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, runner.stop)
            except NotImplementedError:
                pass
        return await runner.run(duration)

    raise SystemExit(0 if asyncio.run(_main()) >= 0 else 1)
