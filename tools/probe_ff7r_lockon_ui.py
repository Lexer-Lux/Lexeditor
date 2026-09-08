#!/usr/bin/env python3
"""Read-only installed-PAK probe for FF7R's lock-on UMG/Blueprint assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff7r.raw_asset_probe import probe_installed_assets


DEFAULT_TERMS = ("lockonmarker", "battlelockonmarker")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find installed FF7R lock-on UI cooked assets and report relevant binary strings."
    )
    parser.add_argument("game_root", type=Path, help="FINAL FANTASY VII REMAKE INTERGRADE installation root")
    parser.add_argument(
        "--term",
        action="append",
        dest="terms",
        default=None,
        help="Case-insensitive PAK path term. May be supplied more than once.",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    result = probe_installed_assets(args.game_root, terms=args.terms or DEFAULT_TERMS)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
