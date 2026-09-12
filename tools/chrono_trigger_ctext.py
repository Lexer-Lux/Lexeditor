#!/usr/bin/env python3
"""Inspect and explicitly manage one Lexeditor Chrono Trigger project through CTExt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.chrono_trigger.ctext_manager import (
    deactivate_project,
    deploy_project,
    status,
    undeploy_project,
)
from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.integrity import audit_project


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chrono Trigger Steam CTExt project status/audit/deployment lifecycle",
    )
    parser.add_argument("--game", type=Path, required=True, help="Chrono Trigger Steam directory")
    parser.add_argument("--project", type=Path, required=True, help="Lexeditor/CTExt loose-file project")
    parser.add_argument(
        "action", choices=("status", "audit", "deploy", "deactivate", "undeploy"),
        nargs="?", default="status", help="operation to perform (default: status)",
    )
    args = parser.parse_args(argv)
    game = args.game.resolve()
    project = args.project.resolve()

    if args.action == "status":
        _print(status(game, project))
        return 0
    if args.action == "deactivate":
        _print(deactivate_project(game, project))
        return 0
    if args.action == "undeploy":
        _print(undeploy_project(game, project))
        return 0

    archive = game / "resources.bin"
    if not archive.is_file():
        parser.error(f"resources.bin is missing: {archive}")
    store = OverlayStore(archive, project)
    audit = audit_project(store)
    if args.action == "audit":
        _print(audit)
        return 0 if audit["ok"] else 1

    if not audit["ok"]:
        _print({
            "deployed": False,
            "reason": "Project audit contains errors; deployment was not attempted.",
            "audit": audit,
        })
        return 1
    result = deploy_project(game, project)
    _print({"deployment": result, "audit": audit})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
