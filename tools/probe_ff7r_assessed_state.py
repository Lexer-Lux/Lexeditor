#!/usr/bin/env python3
"""Compare controlled FF7R save pairs for #424 Assessed-state research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from games.ff7r.save_diff_probe import analyze_save_paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find stable byte transitions across repeated before/after FF7R Assess save experiments."
    )
    parser.add_argument(
        "--pair",
        action="append",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        required=True,
        help="A controlled pre-Assess and post-Assess save pair; repeat for stronger evidence.",
    )
    args = parser.parse_args()
    path_pairs = [
        (Path(before), Path(after), f"pair-{index + 1}")
        for index, (before, after) in enumerate(args.pair)
    ]
    print(json.dumps(analyze_save_paths(path_pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
