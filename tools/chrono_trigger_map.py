#!/usr/bin/env python3
"""Render Chrono Trigger Steam scene or overworld layers from ARC1/project data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.scene_render import render_scene_layer
from games.chrono_trigger.world_render import render_world_layer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a Chrono Trigger Steam map layer to PNG")
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", type=Path, help="Optional Lexeditor/CTExt loose-file project")
    parser.add_argument("--source", choices=("mine", "vanilla"), default="mine")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--scene", type=int, help="Scene ID to render")
    target.add_argument("--world", type=int, help="Overworld ID to render")
    parser.add_argument("--layer", required=True, type=int, choices=(1, 2, 3),
                        help="Scene layer 1/2/3 or overworld layer 1/2")
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.world is not None and args.layer == 3:
        print(json.dumps({"error": "Overworld raster preview supports layer 1 or 2; layer 3 is scene-only."}))
        return 2
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
        if args.scene is not None:
            png, metadata = render_scene_layer(store, args.scene, args.layer, args.source)
            metadata["renderKind"] = "scene"
        else:
            png, metadata = render_world_layer(store, args.world, args.layer, args.source)
            metadata["renderKind"] = "world"
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
