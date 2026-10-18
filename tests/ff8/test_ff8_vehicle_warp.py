"""Tier-A vehicle warp editing: retarget warp cases by cell.

Each section-11 script matches one world-map cell (the FF06 operand,
0-767) and answers the vehicle caller with a destination id. Rewriting the
operand word changes which cell the case matches; scripts keep their
length, so the pointer header is never touched.
"""
import os
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from plugins.ff8 import world_data_merge, world_map

PATH = "direct/world/dat/wmsetus.obj"


def _warp_words(cell, vehicle=128, destination=0, bound=None):
    words = [0xFF01, 0x0000, 0xFF06, cell, 0xFF04, 0x0000, 0xFF0A, 0x0000]
    if bound is not None:
        words += [0xFF0F, bound]
    words += [0xFF09, vehicle, 0xFF0B, 0x0000, 0xFF15, destination,
              0xFF05, 0x0000, 0xFF16]
    return words


def _section_11(*scripts):
    base = (len(scripts) + 1) * 4
    table, cursor = [], base
    for words in scripts:
        table.append(cursor)
        cursor += len(words) * 2
    return struct.pack(f"<{len(table) + 1}I", *table, 0) + b"".join(
        struct.pack(f"<{len(words)}H", *words) for words in scripts)


def _full_wmset(warp_scripts):
    sections = [bytes(4) for _ in range(world_map.SECTION_COUNT)]
    sections[0] = bytes(4) + struct.pack("<BBH", 1, 2, 0) + bytes(4)
    sections[1] = bytes(world_map.REGION_COUNT)
    sections[3] = struct.pack("<16H", *range(1, 17)) + bytes(4)
    sections[world_map.FIELD_RETURN_SECTION] = struct.pack("<iihh", 10, 20, 30, 0x1234) + bytes(4)
    sky = bytearray([0xA5] * world_map.SKY_RECORD_SIZE)
    struct.pack_into("<iii", sky, 0, 100, 200, 300)
    sections[world_map.SKY_SECTION] = struct.pack("<II", 8, 0) + sky
    sections[world_map.DRAW_SECTION] = (bytes(world_map.DRAW_HEADER_SIZE)
                                        + bytes([1, 2, 3, 0xA5]) * world_map.DRAW_POINT_COUNT)
    sections[world_map.VEHICLE_WARP_SECTION] = _section_11(*warp_scripts)
    pointers, cursor = [], world_map.SECTION_COUNT * 4
    for section in sections:
        pointers.append(cursor)
        cursor += len(section)
    return struct.pack(f"<{world_map.SECTION_COUNT}I", *pointers) + b"".join(sections)


def _fixture_warps():
    return [_warp_words(205, 128, 1), _warp_words(300, 128, 0),
            _warp_words(329, 128, 2), _warp_words(406, 50, 3, bound=0x19FF)]


def _cells(data):
    rows = world_map.scripts_in_section(bytes(data), world_map.VEHICLE_WARP_SECTION)
    decoded = []
    for row in rows:
        count = row["bytes"] // 2
        words = struct.unpack(f"<{count}H", data[row["offset"]:row["offset"] + row["bytes"]])
        decoded.append(world_map._vehicle_warp_decode(words)["cell"])
    return decoded


def test_decode_reports_cell_vehicle_and_destination(tmp_path):
    source = tmp_path / "wmsetus.obj"
    source.write_bytes(_full_wmset(_fixture_warps()))
    with patch.object(world_map, "source_path", return_value=source):
        rows = world_map.vehicle_warp_scripts("current")["rows"]
    assert [(row["cell"], row["vehicle"], row["returnValue"]) for row in rows] == [
        (205, 128, 1), (300, 128, 0), (329, 128, 2), (406, 50, 3)]


def test_misshapen_script_leaves_decoded_fields_blank(tmp_path):
    source = tmp_path / "wmsetus.obj"
    source.write_bytes(_full_wmset([[0xFF01, 0x0000, 0xFF06, 0x00CD, 0xFF16]]))
    with patch.object(world_map, "source_path", return_value=source):
        rows = world_map.vehicle_warp_scripts("current")["rows"]
    assert len(rows) == 1 and rows[0]["cell"] is None
    assert rows[0]["head"] == "01 ff 00 00 06 ff cd 00"


def test_shipped_warp_cases():
    root = Path(os.environ["LOCALAPPDATA"]) / "Lexeditor/game-data/ff8/baseline/en/world/wmsetus.obj"
    if not root.is_file():
        pytest.skip("Requires extracted FF8 baseline")
    with patch.object(world_map, "source_path", return_value=root):
        rows = world_map.vehicle_warp_scripts("vanilla")["rows"]
    assert [(row["cell"], row["vehicle"], row["returnValue"]) for row in rows] == [
        (205, 128, 1), (300, 128, 0), (329, 128, 2), (406, 50, 3)]


def test_retarget_moves_only_the_operand_word():
    vanilla = _full_wmset(_fixture_warps())
    saved = world_map.apply_vehicle_warp_edits(
        vanilla, [{"id": 1, "cell": 500}, {"id": 3, "cell": 0}])
    assert len(saved) == len(vanilla)
    assert bytes(saved[:192]) == vanilla[:192]
    changed = [index for index, (a, b) in enumerate(zip(vanilla, saved)) if a != b]
    operands = dict(world_map.vehicle_warp_operands(bytes(saved)))
    assert changed and set(changed) <= {
        operands[1], operands[1] + 1, operands[3], operands[3] + 1}
    assert _cells(saved) == [205, 500, 329, 0]


def test_retarget_rejects_bad_edits():
    vanilla = _full_wmset(_fixture_warps())
    with pytest.raises(ValueError, match="0 to 767"):
        world_map.apply_vehicle_warp_edits(vanilla, [{"id": 0, "cell": 768}])
    with pytest.raises(ValueError, match="0 to 767"):
        world_map.apply_vehicle_warp_edits(vanilla, [{"id": 0, "cell": -1}])
    with pytest.raises(ValueError, match="Vehicle warp script"):
        world_map.apply_vehicle_warp_edits(vanilla, [{"id": 4, "cell": 10}])
    with pytest.raises(ValueError, match="edited twice"):
        world_map.apply_vehicle_warp_edits(
            vanilla, [{"id": 0, "cell": 10}, {"id": 0, "cell": 11}])
    broken = _full_wmset([[0xFF01, 0x0000, 0xFF06, 0x00CD, 0xFF16]])
    with pytest.raises(ValueError, match="warp-case shape"):
        world_map.apply_vehicle_warp_edits(broken, [{"id": 0, "cell": 10}])


def test_merge_composes_independent_retargets():
    vanilla = _full_wmset(_fixture_warps())
    first = world_map.apply_vehicle_warp_edits(vanilla, [{"id": 0, "cell": 111}])
    second = world_map.apply_vehicle_warp_edits(vanilla, [{"id": 2, "cell": 222}])
    merged, conflicts, fallback = world_data_merge.merge(
        vanilla, [("first", bytes(first)), ("second", bytes(second))], "wmset", PATH)
    assert not fallback and not conflicts
    assert _cells(merged) == [111, 300, 222, 406]


def test_merge_collision_follows_priority_with_conflict_unit():
    vanilla = _full_wmset(_fixture_warps())
    low = world_map.apply_vehicle_warp_edits(vanilla, [{"id": 1, "cell": 111}])
    high = world_map.apply_vehicle_warp_edits(vanilla, [{"id": 1, "cell": 222}])
    merged, conflicts, fallback = world_data_merge.merge(
        vanilla, [("low", bytes(low)), ("high", bytes(high))], "wmset", PATH)
    assert not fallback
    assert conflicts == [{"unit": f"{PATH}:warp:1:cell", "winner": "high",
                          "claimants": ["low", "high"]}]
    operands = dict(world_map.vehicle_warp_operands(merged))
    assert struct.unpack_from("<H", merged, operands[1])[0] == 222


def test_merge_rejects_a_reshaped_script():
    vanilla = _full_wmset(_fixture_warps())
    other = bytearray(vanilla)
    offset = dict(world_map.vehicle_warp_operands(vanilla))[0] - 2
    struct.pack_into("<H", other, offset, 0xFF07)  # Same size, unknown shape.
    merged, conflicts, fallback = world_data_merge.merge(
        vanilla, [("other", bytes(other))], "wmset", PATH)
    assert merged is None and not conflicts and "not a supported" in fallback


def test_save_writes_vehicle_warp(tmp_path, monkeypatch):
    wmset = tmp_path / world_map.DIRECT_RELATIVE
    wmset.parent.mkdir(parents=True)
    wmset.write_bytes(_full_wmset(_fixture_warps()))
    monkeypatch.setattr(world_map, "source_path", lambda dataset: wmset)
    monkeypatch.setattr(world_map.paths, "DIRECT_ROOT", tmp_path)
    result = world_map.save([{"kind": "vehicleWarp", "id": 2, "cell": 600}])
    assert result["saved"] == 1
    with patch.object(world_map, "source_path", return_value=wmset):
        rows = world_map.vehicle_warp_scripts("current")["rows"]
    assert [row["cell"] for row in rows] == [205, 300, 600, 406]
