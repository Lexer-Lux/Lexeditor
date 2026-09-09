#!/usr/bin/env python3
"""Render one Chrono Trigger Steam scene layer from resources.bin/project overlays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.scene_render import render_scene_layer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a Chrono Trigger Steam scene layer to PNG")
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", type=Path, help="Optional Lexeditor/CTExt loose-file project")
    parser.add_argument("--source", choices=("mine", "vanilla"), default="mine")
    parser.add_argument("--scene", required=True, type=int)
    parser.add_argument("--layer", required=True, type=int, choices=(1, 2))
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    game = args.game.expanduser().resolve()
    archive = game / "resources.bin"
    if not archive.is_file():
        print(json.dumps({"error": f"resources.bin not found: {archive}"}))
        return 2
    project = (args.project.expanduser().resolve() if args.project
               else game / "mods" / "LexeditorPreview")
    output = args.output.expanduser().resolve()
    if output.suffix.casefold() != ".png":
        print(json.dumps({"error": "Output must use the .png extension"}))
        return 2
    if output.is_dir():
        print(json.dumps({"error": f"Output is a directory: {output}"}))
        return 2
    try:
        store = OverlayStore(archive, project)
        png, metadata = render_scene_layer(store, args.scene, args.layer, args.source)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(png)
        temporary.replace(output)
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "output": str(output),
        "bytes": len(png),
        **metadata,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
