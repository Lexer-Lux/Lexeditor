"""Static and binary contracts for Lexeditor issue #39."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    editor = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    server = (ROOT / "games/ff8/server.py").read_text(encoding="utf-8")
    require("Read-only inventory" not in editor, "The old read-only enemy placeholder remains")
    require('/api/enemies/save' in server, "The enemy save route is missing")
    require('function enemyDisplayName(name)' in editor,
            "The Enemies UI has no display-only special-name formatter")
    require('`「${match[1]}」`' in editor,
            "Special enemy names do not use the native FF8 bracket glyphs")
    require('recordHoverLabel("enemies",row,enemyDisplayName(row.name))' in editor,
            "The Enemies table still sends raw braces to the game font")
    require('sharedDetail({...row,name:enemyDisplayName(row.name)}' in editor,
            "The Enemies detail heading still sends raw braces to the game font")
    require('className:"enemy-scan-section"' in editor and 'field:"scan_description"' in editor,
            "The Enemies detail panel does not expose and save Scan descriptions")
    require('className:"enemy-properties-section"' in editor and 'class:"enemy-properties-row"' in editor,
            "enemy properties must use one compact shared row")

    from games.ff8 import formats, paths, scan_text

    vanilla = formats.enemy_rows("vanilla")
    require(vanilla["rows"], "No extracted enemies were loaded")
    row = next(row for row in vanilla["rows"] if row.get("available") and row.get("fields"))
    require(any(field["field"] == "flying" for field in row["fields"]), "Flying is not editable")
    require(any(field["field"] == "hp_a" for field in row["fields"]), "HP curves are not editable")
    require(row.get("scanDescription"), "The enemy has no decoded Scan description")

    source = paths.BASELINE_ROOT / "battle" / row["filename"]
    before = source.read_bytes()
    original_root = paths.PROJECT_ROOT
    try:
        with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-enemies-", ignore_cleanup_errors=True) as temp:
            paths.PROJECT_ROOT = Path(temp)
            paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
            hp = next(field for field in row["fields"] if field["field"] == "hp_a")
            replacement = (int(hp["value"]) + 1) % 256
            scan_replacement = row["scanDescription"] + " TEST"
            result = formats.save_enemies([
                {"id": row["id"], "field": "hp_a", "value": replacement},
                {"id": row["id"], "field": "scan_description", "value": scan_replacement},
            ])
            target = Path(result["file"])
            after = target.read_bytes()
            require(len(after) == len(before), "Enemy save changed the DAT size")
            changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
            section = int.from_bytes(before[4 + 6 * 4:8 + 6 * 4], "little")
            require(changed == [section + 0x18], f"Enemy save changed unexpected bytes: {changed}")
            loaded = formats.enemy_rows("current")
            saved = next(candidate for candidate in loaded["rows"] if candidate["id"] == row["id"])
            value = next(field["value"] for field in saved["fields"] if field["field"] == "hp_a")
            require(value == replacement, "Saved enemy value did not survive reload")
            require(saved["scanDescription"] == scan_replacement,
                    "Saved Scan description did not survive reload")
            msd = paths.DIRECT_ROOT / "ff8" / "en" / "exe" / "battle_scans.msd"
            descriptions = scan_text.read_msd(msd)
            entity_id = int(next(monster for monster in formats.MONSTERS
                                 if int(monster["com_id"]) == row["id"])["entity_id"])
            vanilla_descriptions = scan_text.read_executable(paths.GAME_ROOT / "FF8_EN.exe")
            require(descriptions[entity_id] == scan_replacement,
                    "The FFNx Scan override did not contain the edit")
            require(all(value == vanilla_descriptions[index] for index, value in enumerate(descriptions)
                        if index != entity_id),
                    "The Scan save changed an unedited description")
    finally:
        paths.PROJECT_ROOT = original_root
        paths.DIRECT_ROOT = original_root / "direct"

    print(json.dumps({"issue": 39, "enemy": row["filename"], "scanDescriptions": 160,
                      "status": "ok"}))


if __name__ == "__main__":
    main()
