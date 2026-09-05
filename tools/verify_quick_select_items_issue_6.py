"""Contract and temporary-file verification for Lexeditor issue 6."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(r"C:\RDR2Mod")
EDITOR = ROOT / "games" / "rdr2" / "editor.html"
SERVER = ROOT / "games" / "rdr2" / "server.py"
DATA_MAP = ROOT / "games" / "rdr2" / "data_map.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


editor = EDITOR.read_text(encoding="utf-8")
server_source = SERVER.read_text(encoding="utf-8")
data_map_source = DATA_MAP.read_text(encoding="utf-8")

for marker in (
    'QUICK_SELECT_FILE = "quickselectitems.ymt"',
    'elif path == "/api/quick-select":',
    'def get_quick_select(',
    'def apply_quick_select_edits(',
    'edits.get("quickSelect", [])',
):
    require(marker in server_source, f"server contract is missing {marker}")

require('quickSelectEdits: {}' in editor, "quick-select edits are not tracked")
require('field("Quick-select slots",cells.quickSelect' in editor,
        "Item Details has no Quick-select slots field")
require('quickSelect: quickSelect' in editor,
        "the normal catalog save does not include quick-select edits")
require('"quickSelectEdits"' in editor,
        "undo/redo does not capture quick-select edits")
start = editor.find("function quickSelectSlotsCell(")
end = editor.find("\nfunction ", start + 20)
require(start >= 0 and end > start, "quick-select field renderer is missing")
field_source = editor[start:end]
require('el("select"' in field_source, "slot rows are not real selectors")
require('pickIdentifier("Add quick-select slot"' in field_source,
        "add-slot control does not use the controlled picker")
for banned in ('el("input"', "datalist", "validatedKeyEditor"):
    require(banned not in field_source,
            f"quick-select field contains forbidden free-entry control: {banned}")
require('("quickselectitems.ymt",' in data_map_source and '"integrated"' in data_map_source,
        "Data Map does not mark quickselectitems.ymt integrated")

with tempfile.TemporaryDirectory(prefix="lexeditor-issue-6-", ignore_cleanup_errors=True) as temp_name:
    mod = Path(temp_name) / "mod"
    mod.mkdir()
    for name in ("catalog_sp.ymt", "quickselectitems.ymt", "install.xml"):
        shutil.copy2(PROJECT / "MyOverhaul" / name, mod / name)
    os.environ["LEXEDITOR_RDR2_PROJECT"] = str(PROJECT)
    os.environ["LEXEDITOR_MOD_ROOT"] = str(mod)
    sys.path.insert(0, str(ROOT))
    from games.rdr2 import server  # noqa: E402

    before = server.get_quick_select()
    require(before["available"], "temporary quick-select file was not loaded")
    items = before["items"]
    one_slot = next((key for key, row in items.items()
                     if row["group"] == server.QUICK_SELECT_SATCHEL_GROUP
                     and len(row["slots"]) == 1), None)
    remove_key = next((key for key, row in items.items()
                       if key != one_slot
                       and row["group"] == server.QUICK_SELECT_SATCHEL_GROUP
                       and len(row["slots"]) == 1), None)
    multi_slot = next((key for key, row in items.items() if len(row["slots"]) > 1), None)
    catalog_keys = server._catalog_ids()
    unmapped = next((key for key in catalog_keys if key not in items and not key.startswith("WEAPON_")), None)
    require(all((one_slot, remove_key, multi_slot, unmapped)),
            "fixture lacks one-slot, multi-slot, removable, or unmapped items")

    original = items[one_slot]
    old_slot = original["slots"][0]
    replacement = next(slot for slot in before["slotsByGroup"][original["group"]]
                       if slot != old_slot["id"])
    untouched_key = next(key for key in items if key not in {one_slot, remove_key, multi_slot})
    tree_before = ET.parse(mod / "quickselectitems.ymt")
    untouched_before = ET.tostring(next(
        node for node in tree_before.findall("./ItemGroups/Item/Items/Item")
        if node.get("key") == untouched_key), encoding="unicode")

    changed = server.apply_quick_select_edits([
        {"item": one_slot, "slots": [{"id": replacement,
                                         "sortOrder": old_slot["sortOrder"]}]},
        {"item": unmapped, "slots": [{"id": "PLAYER_PROVISIONS",
                                        "sortOrder": None}]},
        {"item": remove_key, "slots": []},
    ])
    require(changed == 3, f"expected three changed item mappings, got {changed}")
    after = server.get_quick_select()
    require(after["items"][one_slot]["slots"] == [{"id": replacement,
                                                      "sortOrder": old_slot["sortOrder"]}],
            "changing a slot did not preserve its sort order")
    require(after["items"][unmapped]["slots"][0]["id"] == "PLAYER_PROVISIONS",
            "unmapped item did not receive the selected slot")
    require(isinstance(after["items"][unmapped]["slots"][0]["sortOrder"], int),
            "new slot did not receive an automatic numeric sort order")
    require(remove_key not in after["items"], "removed mapping still exists")
    require(after["items"][multi_slot] == before["items"][multi_slot],
            "unrelated multi-slot mapping changed")
    tree_after = ET.parse(mod / "quickselectitems.ymt")
    untouched_after = ET.tostring(next(
        node for node in tree_after.findall("./ItemGroups/Item/Items/Item")
        if node.get("key") == untouched_key), encoding="unicode")
    require(untouched_after == untouched_before, "unrelated XML entry changed")
    require((mod / "quickselectitems.ymt.bak").is_file(), "save did not create a backup")

    before_invalid = digest(mod / "quickselectitems.ymt")
    try:
        server.apply_quick_select_edits([
            {"item": one_slot, "slots": [{"id": "MADE_UP_SLOT", "sortOrder": 10}]}
        ])
    except ValueError:
        pass
    else:
        raise SystemExit("FAIL: server accepted a free-entry slot ID")
    require(digest(mod / "quickselectitems.ymt") == before_invalid,
            "rejected slot changed the file")

print("PASS: Lexeditor #6 controlled item quick-select assignments")
