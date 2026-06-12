from __future__ import annotations

from dataclasses import dataclass

from .protocol import DUMMY_CAPTCHA_TOKEN


@dataclass
class Lvl3Config:
    base_url: str = "https://lvl3.cupflag.top"
    username: str = "flaghunter"
    flaresolverr_url: str = "http://localhost:8191/v1"
    concurrency: int = 1
    clearance_ttl: float = 1500.0
    captcha_token: str = DUMMY_CAPTCHA_TOKEN
    req_timeout: float = 8.0
    cycle_timeout: float = 28.0
    duration: float | None = None
    out: str = "flags_lvl3.jsonl"
    verbose: bool = False
    io_log: str = "lvl3_io.jsonl"
    rtt_init: float = 0.08
    rtt_window: int = 8
    target_margin_ms: float = 25.0
    margin_frac: float = 0.25
