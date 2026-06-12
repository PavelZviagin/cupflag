#!/usr/bin/env python3
from __future__ import annotations

import argparse

from cupflag.common import cli
from cupflag.lvl3 import Lvl3Config, Lvl3Runner


def main() -> None:
    p = argparse.ArgumentParser(description="cupflag LVL3")
    p.add_argument("--base-url", default="https://lvl3.cupflag.top")
    p.add_argument("--username", default="flaghunter")
    p.add_argument("--flaresolverr-url", default="http://localhost:8191/v1")
    cli.add_common_args(p, default_out="flags_lvl3.jsonl")
    p.add_argument("--io-log", default="lvl3_io.jsonl")
    a = p.parse_args()
    cfg = Lvl3Config(
        base_url=a.base_url,
        username=a.username,
        flaresolverr_url=a.flaresolverr_url,
        duration=a.duration,
        out=a.out,
        verbose=a.verbose,
        io_log=a.io_log,
    )
    cli.run(Lvl3Runner(cfg), duration=cfg.duration, verbose=cfg.verbose)


if __name__ == "__main__":
    main()
