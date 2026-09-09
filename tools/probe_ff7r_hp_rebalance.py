#!/usr/bin/env python3
"""Inspect installed FF7R HP data sources and final-status native candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff7r.archive import build_index
from games.ff7r.hp_rebalance_probe import probe_hp_rebalance_sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Correlate installed FF7R player HP DataObjects with final-status native getter candidates."
    )
    parser.add_argument("game_root", type=Path, help="FINAL FANTASY VII REMAKE INTERGRADE installation root")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "out" / "ff7r-hp-probe",
        help="Extraction/index cache directory",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT / "out" / "ff7r-project",
        help="Project root used for localized text loader context",
    )
    parser.add_argument("--language", default="US")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    game_root = args.game_root.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    project_root = args.project_root.expanduser().resolve()
    index = build_index(game_root, data_root)
    result = probe_hp_rebalance_sources(
        game_root, data_root, project_root, index, language=args.language)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
