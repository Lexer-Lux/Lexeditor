#!/usr/bin/env python3
"""Locate cooked FF7R Sector 7 bench/vending candidates for Better Restore."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff7r.bench_probe import probe_chapter3_bench


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe installed FF7R slum7 cooked assets for the Chapter 3 bench/vending pair."
    )
    parser.add_argument("game_root", type=Path, help="FINAL FANTASY VII REMAKE INTERGRADE installation root")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    result = probe_chapter3_bench(args.game_root)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
