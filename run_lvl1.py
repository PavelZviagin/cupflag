#!/usr/bin/env python3
from __future__ import annotations

import argparse

from cupflag.common import cli
from cupflag.lvl1 import Lvl1Config, Lvl1Runner


def main() -> None:
    p = argparse.ArgumentParser(description="cupflag LVL1")
    p.add_argument("--base-url", default="https://lvl1.cupflag.top")
    p.add_argument("--username", default="flaghunter")
    cli.add_common_args(p, default_out="flags_lvl1.jsonl")
    p.add_argument("--shots", type=int, default=2)
    p.add_argument("--cooldown-factor", type=float, default=0.5)
    a = p.parse_args()
    cfg = Lvl1Config(
        base_url=a.base_url,
        username=a.username,
        duration=a.duration,
        out=a.out,
        verbose=a.verbose,
        shots=a.shots,
        cooldown_factor=a.cooldown_factor,
    )
    cli.run(Lvl1Runner(cfg), duration=cfg.duration, verbose=cfg.verbose)


if __name__ == "__main__":
    main()
