"""Prove lossless FF8 mitem, enemy-table, and scene.out edits on real data."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from games.ff8 import formats, paths  # noqa: E402


def changed_offsets(before: bytes, after: bytes) -> set[int]:
    assert len(before) == len(after)
    return {index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]}


def main() -> None:
    baseline = paths.BASELINE_ROOT
    required = [baseline / "menu" / "mitem.bin", baseline / "battle" / "scene.out",
                baseline / "battle" / "c0m000.dat"]
    assert all(path.is_file() for path in required), required

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-data-", ignore_cleanup_errors=True) as temp_name:
        temp = Path(temp_name)
        direct = temp / "direct"
        old_project, old_direct = paths.PROJECT_ROOT, paths.DIRECT_ROOT
        paths.PROJECT_ROOT, paths.DIRECT_ROOT = temp, direct
        try:
            # mitem.bin: one four-byte row changes and every other byte is identical.
            before = required[0].read_bytes()
            row = formats.menu_item_rows()["rows"][0]
            assert len(formats.menu_item_rows()["rows"]) == 199
            result = formats.save_menu_items([{**row, "param1": (row["param1"] + 1) % 256}])
            after = Path(result["file"]).read_bytes()
            assert changed_offsets(before, after) == {2}
            assert formats.menu_item_rows()["rows"][0]["param1"] == (row["param1"] + 1) % 256

            # scene.out: one slot changes only its known masks, coordinates, enemy and level.
            before = required[1].read_bytes()
            first = formats.encounter_rows()["rows"][0]
            slot = dict(first["slots"][0])
            slot.update({"id": 0, "slot": 0, "enemyId": 0, "enabled": not slot["enabled"],
                         "visible": not slot["visible"], "loaded": not slot["loaded"],
                         "targetable": not slot["targetable"], "x": slot["x"] + 1,
                         "y": slot["y"] - 1, "z": slot["z"] + 2,
                         "level": (slot["level"] + 1) % 256})
            result = formats.save_encounters([slot])
            after = Path(result["file"]).read_bytes()
            allowed = set(range(4, 8)) | set(range(0x08, 0x0E)) | {0x38, 0x78}
            assert changed_offsets(before, after) <= allowed
            readback = formats.encounter_rows()["rows"][0]["slots"][0]
            for key in ("enemyId", "enabled", "visible", "loaded", "targetable", "x", "y", "z", "level"):
                assert readback[key] == slot[key], (key, readback[key], slot[key])

            # Enemy tables: ability, Draw, drop, card, and defence edit exact fixed ranges.
            before = required[2].read_bytes()
            start = formats._enemy_info_start(before)
            payload = formats.enemy_table_rows(enemy_id=0)
            assert len(payload["rows"]) == 1
            edits = [
                {"id": 0, "kind": "ability", "tier": "low", "slot": 0,
                 "type": 2, "animation": 7, "abilityId": 1},
                {"id": 0, "kind": "draw", "tier": "low", "slot": 0,
                 "valueId": 1, "quantity": 9},
                {"id": 0, "kind": "drop", "tier": "high", "slot": 3,
                 "valueId": 1, "quantity": 2},
                {"id": 0, "kind": "card", "slot": 0, "cardId": 1},
                {"id": 0, "kind": "elementDefence", "slot": 0, "stored": 91},
            ]
            result = formats.save_enemy_tables(edits)
            after = Path(result["file"]).read_bytes()
            allowed = (set(range(start + 0x34, start + 0x38)) |
                       set(range(start + 0x104, start + 0x106)) |
                       set(range(start + 0x14A, start + 0x14C)) |
                       {start + 0xF8, start + 0x160})
            assert changed_offsets(before, after) <= allowed
            tables = formats.enemy_table_rows(enemy_id=0)["rows"][0]["tables"]
            assert tables["abilities"]["low"][0] == {
                "slot": 0, "type": 2, "animation": 7, "abilityId": 1}
            assert tables["draw"]["low"][0]["valueId"] == 1
            assert tables["drops"]["high"][3]["quantity"] == 2
            assert tables["cards"][0]["cardId"] == 1
            assert tables["elementDefence"][0]["stored"] == 91

            # Invalid finite references fail before a file is written.
            try:
                formats.save_enemy_tables([{
                    "id": 0, "kind": "ability", "tier": "low", "slot": 0,
                    "type": 2, "animation": 0, "abilityId": 65535}])
            except ValueError:
                pass
            else:
                raise AssertionError("Unknown Magic id was accepted")
        finally:
            paths.PROJECT_ROOT, paths.DIRECT_ROOT = old_project, old_direct

    print("FF8 mitem, enemy table, and scene.out lossless edit checks passed")


if __name__ == "__main__":
    main()
