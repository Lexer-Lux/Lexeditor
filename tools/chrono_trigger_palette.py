#!/usr/bin/env python3
"""Inspect and safely edit Chrono Trigger Steam scene/world palettes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.palettes import load_palette, save_palette_color


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chrono Trigger Steam BGR555 palette editor")
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", required=True, type=Path, help="Writable Lexeditor/CTExt project")
    parser.add_argument("--kind", required=True, choices=("scene", "world"))
    parser.add_argument("--palette", required=True, type=int, dest="palette_id")
    sub = parser.add_subparsers(dest="action", required=True)
    show = sub.add_parser("show", help="Show decoded 256-color palette")
    show.add_argument("--source", choices=("mine", "vanilla"), default="mine")
    set_color = sub.add_parser("set", help="Change one color in the project overlay")
    set_color.add_argument("--index", required=True, type=int)
    set_color.add_argument("--sha256", required=True)
    group = set_color.add_mutually_exclusive_group(required=True)
    group.add_argument("--raw", type=lambda value: int(value, 0), help="15-bit BGR555 value (decimal or 0xhex)")
    group.add_argument("--rgb", nargs=3, type=int, metavar=("R", "G", "B"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    game = args.game.expanduser().resolve()
    project = args.project.expanduser().resolve()
    archive = game / "resources.bin"
    if not archive.is_file():
        print(json.dumps({"error": f"resources.bin not found: {archive}"}))
        return 2
    try:
        store = OverlayStore(archive, project)
        if args.action == "show":
            payload = load_palette(store, args.kind, args.palette_id, args.source)
        else:
            values = ({"raw": args.raw} if args.raw is not None else
                      {"red": args.rgb[0], "green": args.rgb[1], "blue": args.rgb[2]})
            payload = save_palette_color(
                store, args.kind, args.palette_id, args.index, args.sha256, values,
            )
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
