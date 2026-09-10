#!/usr/bin/env python3
"""Audit Chrono Trigger Steam field-event editor coverage.

This is the CLI wrapper around :mod:`games.chrono_trigger.event_audit`. It can
consume exported Event JSON or scan a real Steam install/project directly. All
modes are read-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.event_audit import audit_event, audit_store, merge_audits


def _load(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Chrono Trigger Steam field-event editor coverage."
    )
    parser.add_argument("inputs", nargs="*", help="Event JSON file(s), or '-' for stdin")
    parser.add_argument("--game", type=Path, help="Chrono Trigger Steam install directory")
    parser.add_argument("--project", type=Path, help="Lexeditor/CTExt project overlay")
    parser.add_argument("--source", choices=("mine", "vanilla"), default="mine",
                        help="Direct-scan source: project overlay when present, or immutable vanilla")
    parser.add_argument("--event", dest="event_ids", action="append", type=int, default=[],
                        help="Direct scan: restrict to this event ID; repeat for multiple events")
    parser.add_argument("--limit", type=int, default=0,
                        help="Direct scan: maximum events after filtering; 0 scans all")
    args = parser.parse_args(argv)

    direct_mode = args.game is not None or args.project is not None
    if direct_mode:
        if args.game is None or args.project is None:
            parser.error("--game and --project must be supplied together")
        if args.inputs:
            parser.error("JSON inputs cannot be combined with --game/--project")
        archive = args.game.expanduser().resolve() / "resources.bin"
        if not archive.is_file():
            print(json.dumps({"error": f"resources.bin not found: {archive}"}, ensure_ascii=False))
            return 1
        try:
            output = audit_store(
                OverlayStore(archive, args.project.expanduser().resolve()),
                args.source,
                args.event_ids,
                args.limit,
            )
        except Exception as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
            return 1
    else:
        if args.event_ids or args.limit or args.source != "mine":
            parser.error("--event, --limit and --source require --game/--project")
        if not args.inputs:
            parser.error("provide event JSON input(s) or --game/--project")
        if args.inputs.count("-") > 1:
            parser.error("stdin may be specified only once")
        audits = [audit_event(_load(path)) for path in args.inputs]
        output = audits[0] if len(audits) == 1 else merge_audits(audits)

    print(json.dumps(output, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
