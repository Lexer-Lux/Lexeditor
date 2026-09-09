#!/usr/bin/env python3
"""Inspect or safely patch fixed-width Chrono Trigger Steam field-event commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.event_edit import save_event_arguments
from games.chrono_trigger.events import get_event
from games.chrono_trigger.field_editors import decorate_event_editors, save_event_fields


def _json_object(value: str) -> dict:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON object: {error}") from error
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and patch fixed-width Chrono Trigger Steam Atel commands",
    )
    parser.add_argument("--game", required=True, type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", required=True, type=Path, help="Writable Lexeditor/CTExt project")
    parser.add_argument("--event", required=True, type=int, help="Atel event ID")
    parser.add_argument("--object", dest="object_id", type=int, default=0)
    parser.add_argument("--function", dest="function_id", type=int, default=0)
    parser.add_argument("--command", dest="command_index", type=int, default=0)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show", help="Show decoded event commands and named editor schemas")
    raw = sub.add_parser("set-args", help="Replace exact fixed-width argument bytes")
    raw.add_argument("--sha256", required=True, help="Event SHA from show/open operation")
    raw.add_argument("--hex", required=True, dest="arguments_hex", help="Exact argument bytes, e.g. '34 12 80'")
    named = sub.add_parser("set-fields", help="Patch named fixed-width fields")
    named.add_argument("--sha256", required=True, help="Event SHA from show/open operation")
    named.add_argument("--values", required=True, type=_json_object,
                       help='JSON object such as {"enemyId":42,"slot":1}')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    game = args.game.expanduser().resolve()
    project = args.project.expanduser().resolve()
    archive = game / "resources.bin"
    if not archive.is_file():
        print(json.dumps({"error": f"resources.bin not found: {archive}"}))
        return 2
    try:
        store = OverlayStore(archive, project)
        if args.action == "show":
            payload = decorate_event_editors(get_event(store, args.event, "mine"))
        elif args.action == "set-args":
            payload = save_event_arguments(
                store, args.event, args.object_id, args.function_id, args.command_index,
                args.sha256, args.arguments_hex,
            )
            payload = decorate_event_editors(payload)
        else:
            payload = save_event_fields(
                store, args.event, args.object_id, args.function_id, args.command_index,
                args.sha256, args.values,
            )
            payload = decorate_event_editors(payload)
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
