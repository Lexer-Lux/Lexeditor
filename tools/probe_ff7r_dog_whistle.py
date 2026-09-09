#!/usr/bin/env python3
"""Inspect installed FF7R data/native candidates for the Dog Whistle tweak."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff7r.archive import build_index
from games.ff7r.dog_whistle_probe import probe_dog_whistle_sources


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe installed Item/Chapter/EnemyBook/native FF7R Dog Whistle candidates."
    )
    parser.add_argument("game_root", type=Path, help="FINAL FANTASY VII REMAKE INTERGRADE installation root")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "out" / "ff7r-dog-whistle-probe",
        help="Extraction/index cache directory",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT / "out" / "ff7r-project",
        help="Project root used only for text-package loader context; vanilla source is always read",
    )
    parser.add_argument("--language", default="US")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    game_root = args.game_root.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    project_root = args.project_root.expanduser().resolve()
    index = build_index(game_root, data_root)
    result = probe_dog_whistle_sources(
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
