from __future__ import annotations

import json
import threading
from pathlib import Path

from .log import Logger, now_ts


class FlagSink:
    def __init__(self, path: Path, logger: Logger) -> None:
        self.path = path
        self.logger = logger
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, flag: str) -> bool:
        if "decoy" in flag:
            return False
        with self._lock:
            if flag in self._seen:
                return False
            self._seen.add(flag)
            count = len(self._seen)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": now_ts(), "flag": flag, "n": count}) + "\n")
        self.logger.info(f"flag #{count} captured: {flag}")
        return True

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._seen)
