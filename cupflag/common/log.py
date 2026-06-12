from __future__ import annotations

import logging
from datetime import datetime

import structlog
from structlog.typing import EventDict, FilteringBoundLogger, WrappedLogger

Logger = FilteringBoundLogger


def now_ts() -> str:
    now = datetime.now()
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _add_timestamp(logger: WrappedLogger, name: str, event_dict: EventDict) -> EventDict:
    event_dict["ts"] = now_ts()
    return event_dict


def _render(logger: WrappedLogger, name: str, event_dict: EventDict) -> str:
    ts = event_dict.pop("ts", "")
    tag = event_dict.pop("tag", "")
    event = event_dict.pop("event", "")
    rest = " ".join(f"{k}={v}" for k, v in event_dict.items())
    line = f"[{ts}] [{tag}] {event}"
    return f"{line} {rest}" if rest else line


def configure(*, verbose: bool = False) -> None:
    structlog.configure(
        processors=[_add_timestamp, _render],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG if verbose else logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(tag: str) -> Logger:
    return structlog.get_logger().bind(tag=tag)
