from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Lvl1Config:
    base_url: str = "https://lvl1.cupflag.top"
    username: str = "flaghunter"
    duration: float | None = None
    out: str = "flags_lvl1.jsonl"
    verbose: bool = False
    req_timeout: float = 2.0
    shots: int = 2
    span: float = 0.06
    target_arrival: float = 0.05
    rtt_init: float = 0.13
    rtt_alpha: float = 0.2
    cooldown_factor: float = 0.5
