#!/usr/bin/env python3
"""Print FF7R #414 installed-build minimap state/input evidence as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from games.ff7r.minimap_runtime_probe import probe_minimap_runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("game_root", type=Path, help="FINAL FANTASY VII REMAKE install root")
    args = parser.parse_args()
    print(json.dumps(probe_minimap_runtime(args.game_root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
