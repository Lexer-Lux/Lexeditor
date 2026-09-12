#!/usr/bin/env python3
"""Inspect/revert Chrono Trigger overlays or export a deterministic CTExt CTP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.changes import list_changes, revert_change  # noqa: E402
from games.chrono_trigger.ctp import default_target, export_ctp  # noqa: E402
from games.chrono_trigger.data import OverlayStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chrono Trigger Lexeditor project utilities")
    parser.add_argument("command", choices=("changes", "revert", "export-ctp"))
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--resources", type=Path, help="Steam resources.bin (required for changes/revert)")
    parser.add_argument("--path", help="Virtual resource path to revert")
    parser.add_argument("--sha256", help="Expected project SHA-256 for revert")
    parser.add_argument("--output", type=Path, help="CTP destination; defaults beside the project")
    args = parser.parse_args(argv)

    project = args.project.resolve()
    if args.command == "export-ctp":
        result = export_ctp(project, (args.output or default_target(project)).resolve())
    else:
        if args.resources is None:
            parser.error("--resources is required for changes/revert")
        store = OverlayStore(args.resources.resolve(), project)
        if args.command == "changes":
            result = list_changes(store)
        else:
            if not args.path or not args.sha256:
                parser.error("--path and --sha256 are required for revert")
            result = revert_change(store, args.path, args.sha256)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
