from __future__ import annotations

from dataclasses import dataclass

DUMMY_CAPTCHA_TOKEN = "1.0000000000000000000000000000000000000000000000000000000000000000"


@dataclass
class Lvl2Config:
    base_url: str = "https://lvl2.cupflag.top"
    username_prefix: str = "hunter"
    captcha_token: str = DUMMY_CAPTCHA_TOKEN
    duration: float | None = None
    out: str = "flags_lvl2.jsonl"
    verbose: bool = False
    pool_size: int = 48
    cooldown: float = 13.0
    req_timeout: float = 2.0
    login_concurrency: int = 8
    shots: int = 3
    span: float = 0.08
    target_arrival: float = 0.06
    rtt_init: float = 0.18
    rtt_alpha: float = 0.2
    cooldown_factor: float = 0.5
