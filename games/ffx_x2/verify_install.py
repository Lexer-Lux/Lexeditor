"""Read-only verification for a real FFX/X-2 HD Remaster Steam installation.

This utility deliberately performs no project writes, deployment, or process launch.
It validates the installed VBF indexes and attempts to parse every structured table
Lexeditor currently claims to support, producing a machine-readable acceptance
report suitable for real-install testing that CI cannot provide.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Iterable

from . import (
    auto_ability_prices, ctb_base, ffx_commands, ffx2_accessories, ffx2_abilities,
    gear_shops, item_prices, item_shops, launch, mix_table, paths, treasures,
)
from .vbf import VBFError, VBFIndex, read_entry, read_index


ARCHIVE_FILES = {
    "x": Path("data") / "FFX_Data.vbf",
    "x2": Path("data") / "FFX2_Data.vbf",
}

STRUCTURED_SPECS = (
    {"game": "x", "key": "treasures", "archivePath": treasures.ARCHIVE_PATH, "builder": treasures.payload},
    {"game": "x", "key": "item-prices", "archivePath": item_prices.ARCHIVE_PATH, "builder": item_prices.payload},
    {"game": "x", "key": "auto-ability-prices", "archivePath": auto_ability_prices.ARCHIVE_PATH, "builder": auto_ability_prices.payload},
    {"game": "x", "key": "ctb-base", "archivePath": ctb_base.ARCHIVE_PATH, "builder": ctb_base.payload},
    {"game": "x", "key": "mix-table", "archivePath": mix_table.ARCHIVE_PATH, "builder": mix_table.payload},
    {"game": "x", "key": "item-shops", "archivePath": item_shops.ARCHIVE_PATH, "builder": item_shops.payload},
    {"game": "x", "key": "gear-shops", "archivePath": gear_shops.ARCHIVE_PATH, "builder": gear_shops.payload},
    {"game": "x", "key": "ffx-commands", "archivePath": ffx_commands.TABLES["command"].archive_path,
     "builder": lambda data: ffx_commands.payload_for(data, "command")},
    {"game": "x", "key": "ffx-items", "archivePath": ffx_commands.TABLES["item"].archive_path,
     "builder": lambda data: ffx_commands.payload_for(data, "item")},
    {"game": "x", "key": "ffx-monmagic1", "archivePath": ffx_commands.TABLES["monmagic1"].archive_path,
     "builder": lambda data: ffx_commands.payload_for(data, "monmagic1")},
    {"game": "x", "key": "ffx-monmagic2", "archivePath": ffx_commands.TABLES["monmagic2"].archive_path,
     "builder": lambda data: ffx_commands.payload_for(data, "monmagic2")},
    {"game": "x2", "key": "ffx2-abilities", "archivePath": ffx2_abilities.ARCHIVE_PATH, "builder": ffx2_abilities.payload},
    {"game": "x2", "key": "ffx2-accessories", "archivePath": ffx2_accessories.ARCHIVE_PATH, "builder": ffx2_accessories.payload},
)


def _find_entry(index: VBFIndex, game: str, archive_path: str):
    for candidate in paths.source_archive_candidates(game, archive_path):
        try:
            return index.find(candidate)
        except FileNotFoundError:
            continue
    raise FileNotFoundError(archive_path)


def inspect_install(game_root: Path, specs: Iterable[dict] = STRUCTURED_SPECS) -> dict:
    """Validate installed archives and all requested structured tables read-only."""
    root = Path(game_root).resolve()
    indexes: dict[str, VBFIndex] = {}
    archives: dict[str, dict] = {}

    for game, relative in ARCHIVE_FILES.items():
        target = root / relative
        state = {
            "game": game,
            "path": str(target),
            "ready": False,
            "fileCount": 0,
        }
        if not target.is_file():
            state["error"] = "Archive is missing"
        else:
            try:
                index = read_index(target)
                indexes[game] = index
                state.update({
                    "ready": True,
                    "headerMd5": index.header_md5,
                    "headerBytes": index.header_length,
                    "fileCount": index.file_count,
                    "bytes": target.stat().st_size,
                })
            except (OSError, VBFError, ValueError) as error:
                state["error"] = str(error)
        archives[game] = state

    structured = []
    for spec in specs:
        game = str(spec["game"])
        archive_path = str(spec["archivePath"])
        builder: Callable[[bytes], dict] = spec["builder"]
        row = {
            "game": game,
            "key": str(spec["key"]),
            "archivePath": archive_path,
            "status": "unavailable",
        }
        index = indexes.get(game)
        if index is None:
            row["error"] = f"{game} archive did not validate"
            structured.append(row)
            continue
        try:
            entry = _find_entry(index, game, archive_path)
            data = read_entry(index, entry)
            parsed = builder(data)
            row.update({
                "status": "validated",
                "sourcePath": entry.path,
                "bytes": len(data),
                "tableSha256": parsed.get("baselineSha256"),
                "rowCount": len(parsed.get("rows", [])),
            })
            for key in ("minIndex", "maxIndex", "recordSize", "slotCount", "partnerCount"):
                if key in parsed:
                    row[key] = parsed[key]
        except (FileNotFoundError, OSError, VBFError, ValueError, RuntimeError) as error:
            row["error"] = str(error)
        structured.append(row)

    launch_state = launch.status(root)
    archives_ok = all(state.get("ready") for state in archives.values())
    structured_ok = all(row.get("status") == "validated" for row in structured)
    return {
        "contract": "Lexeditor.ffx-x2-install-verification",
        "gameRoot": str(root),
        "ok": bool(archives_ok and structured_ok),
        "archives": archives,
        "structured": structured,
        "launch": launch_state,
    }


def _human_report(report: dict, require_fahrenheit: bool) -> str:
    lines = [f"FFX/X-2 install: {report['gameRoot']}"]
    for game in ("x", "x2"):
        state = report["archives"][game]
        if state.get("ready"):
            lines.append(
                f"  {game}: VBF OK — {state['fileCount']} files, header {state['headerMd5']}"
            )
        else:
            lines.append(f"  {game}: VBF FAIL — {state.get('error', 'unavailable')}")
    for row in report["structured"]:
        if row["status"] == "validated":
            details = [f"{row['rowCount']} rows"]
            if "recordSize" in row:
                details.append(f"0x{row['recordSize']:X}-byte records")
            lines.append(f"  {row['key']}: OK — {', '.join(details)}")
        else:
            lines.append(f"  {row['key']}: FAIL — {row.get('error', 'unavailable')}")
    launch_state = report["launch"]
    launch_ready = bool(
        launch_state.get("ready")
        and all(game.get("ready") for game in launch_state.get("games", {}).values())
    )
    lines.append(f"  Fahrenheit launch prerequisites: {'OK' if launch_ready else 'NOT READY'}")
    accepted = report["ok"] and (launch_ready if require_fahrenheit else True)
    lines.append(f"Result: {'PASS' if accepted else 'FAIL'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, default=paths.GAME_ROOT,
                        help="FFX/X-2 Steam collection root (defaults to the configured plugin root)")
    parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON")
    parser.add_argument("--require-fahrenheit", action="store_true",
                        help="Also fail unless Stage 0, Stage 1 and both game executables are present")
    args = parser.parse_args(argv)

    report = inspect_install(args.game_root)
    launch_state = report["launch"]
    launch_ready = bool(
        launch_state.get("ready")
        and all(game.get("ready") for game in launch_state.get("games", {}).values())
    )
    accepted = bool(report["ok"] and (launch_ready if args.require_fahrenheit else True))
    report["acceptanceReady"] = accepted
    report["fahrenheitRequired"] = bool(args.require_fahrenheit)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_report(report, args.require_fahrenheit))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
