#!/usr/bin/env python3
from __future__ import annotations

import argparse

from cupflag.common import cli
from cupflag.lvl2 import Lvl2Config, Lvl2Runner


def main() -> None:
    p = argparse.ArgumentParser(description="cupflag LVL2")
    p.add_argument("--base-url", default="https://lvl2.cupflag.top")
    p.add_argument("--username-prefix", default="hunter")
    cli.add_common_args(p, default_out="flags_lvl2.jsonl")
    p.add_argument("--shots", type=int, default=3)
    p.add_argument("--pool-size", type=int, default=48)
    p.add_argument("--cooldown-factor", type=float, default=0.5)
    a = p.parse_args()
    cfg = Lvl2Config(
        base_url=a.base_url,
        username_prefix=a.username_prefix,
        duration=a.duration,
        out=a.out,
        verbose=a.verbose,
        shots=a.shots,
        pool_size=a.pool_size,
        cooldown_factor=a.cooldown_factor,
    )
    cli.run(Lvl2Runner(cfg), duration=cfg.duration, verbose=cfg.verbose)


if __name__ == "__main__":
    main()
