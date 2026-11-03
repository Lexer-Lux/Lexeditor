"""Per-section, per-record merge for battle enemy files.

Independent stat, script and text edits compose; collisions follow load
order with a named unit; model and texture sections stay opaque claims.
"""
import json
import struct
from pathlib import Path

from plugins.ff8 import (
    assets, enemy_ai, enemy_battle_text, enemy_data_merge, enemy_tables,
    kernel_text, runtime_layout,
)

PATH = "direct/battle/c0m001.dat"
INFO_SIZE = 0x180
SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "plugins" / "ff8" / "schema"


def _ai_section():
    scripts = [bytes([13, index, 0, 0]) for index in range(5)]
    starts, cursor = [], 20
    for block in scripts:
        starts.append(cursor)
        cursor += len(block)
    text_offset = 16 + cursor
    line0 = kernel_text.encode("Alpha") + b"\0"
    line1 = kernel_text.encode("Beta") + b"\0"
    table = struct.pack("<2H", 0, len(line0))
    text_data_offset = text_offset + len(table)
    text_data = line0 + line1 + bytes(-(len(line0) + len(line1)) % 4)
    section = (struct.pack("<4I", 3, 16, text_offset, text_data_offset)
               + struct.pack("<5I", *starts) + b"".join(scripts) + table + text_data)
    assert len(section) % 4 == 0
    return section


def _assemble(bodies):
    positions, cursor = [], 4 + (len(bodies) + 1) * 4
    for body in bodies:
        positions.append(cursor)
        cursor += len(body)
    positions.append(cursor)
    return (struct.pack("<I", len(bodies))
            + struct.pack(f"<{len(positions)}I", *positions) + b"".join(bodies))


def _info():
    return bytes((index * 7 + 3) % 256 for index in range(INFO_SIZE))


def _nomodel(info=None):
    return _assemble([_info() if info is None else info, _ai_section()])


def _monster(info=None):
    pad = [bytes([number + 1]) * 16 for number in range(6)]
    tail = [bytes([number + 9]) * 16 for number in range(3)]
    return _assemble(pad + [_info() if info is None else info, _ai_section()] + tail)


def _sections(raw):
    rows = assets.parse_dat_sections(raw)
    return [raw[row["offset"]:row["offset"] + row["size"]] for row in rows]


def _tables(raw, info_start):
    return enemy_tables.read_tables(raw, info_start)


def test_layout_names_cover_both_enemy_shapes():
    assert enemy_data_merge._layout("c0m001.dat", 11)[1:] == (7, 8)
    assert enemy_data_merge._layout("c0m127.dat", 2)[1:] == (1, 2)
    assert enemy_data_merge._layout("c0m001.dat", 5) is None
    assert enemy_data_merge._layout("d01w003.dat", 11) is None


def test_info_units_do_not_overlap():
    units, masked = enemy_data_merge._info_units()
    spans = [(offset, offset + size, label) for label, offset, size in units]
    for first in range(len(spans)):
        for second in range(first + 1, len(spans)):
            assert spans[first][1] <= spans[second][0] or spans[second][1] <= spans[first][0], (
                spans[first], spans[second])
    assert set(masked).isdisjoint(
        {offset for _, start, size in units for offset in range(start, start + size)})
    assert max(set(masked)) < INFO_SIZE


def test_independent_info_records_coexist():
    vanilla = _nomodel()
    info_start = 16
    first = bytearray(vanilla)
    first[info_start + 0x102:info_start + 0x104] = (1234).to_bytes(2, "little")
    second = bytearray(vanilla)
    enemy_tables.apply_edits(second, info_start, [
        {"kind": "devour", "slot": 0, "devourId": 5}], SCHEMA_ROOT, set(), set())
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("first", bytes(first)), ("second", bytes(second))], PATH)
    assert not fallback and not conflicts
    assert int.from_bytes(merged[info_start + 0x102:info_start + 0x104], "little") == 1234
    assert _tables(merged, info_start)["devour"][0]["devourId"] == 5
    assert assets.parse_dat_sections(merged) is not None


def test_info_collision_follows_priority_with_conflict_unit():
    vanilla = _nomodel()
    info_start = 16
    low = bytearray(vanilla)
    low[info_start + 0x102:info_start + 0x104] = (100).to_bytes(2, "little")
    high = bytearray(vanilla)
    high[info_start + 0x102:info_start + 0x104] = (200).to_bytes(2, "little")
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("low", bytes(low)), ("high", bytes(high))], PATH)
    assert not fallback
    assert int.from_bytes(merged[info_start + 0x102:info_start + 0x104], "little") == 200
    assert conflicts == [{"unit": f"{PATH}:info:stat:xp", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_masked_bits_in_one_byte_coexist():
    vanilla = _nomodel()
    info_start = 16
    assert vanilla[info_start + 0xF7] & 0x03 == 0
    zombie = bytearray(vanilla)
    zombie[info_start + 0xF7] |= 0x01
    flying = bytearray(vanilla)
    flying[info_start + 0xF7] |= 0x02
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("zombie", bytes(zombie)), ("flying", bytes(flying))], PATH)
    assert not fallback and not conflicts
    assert merged[info_start + 0xF7] & 0x03 == 0x03


def test_same_masked_bit_twice_is_not_a_conflict():
    vanilla = _nomodel()
    info_start = 16
    first = bytearray(vanilla)
    first[info_start + 0xF7] |= 0x02
    second = bytearray(vanilla)
    second[info_start + 0xF7] |= 0x02
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("first", bytes(first)), ("second", bytes(second))], PATH)
    assert not fallback and not conflicts
    assert merged[info_start + 0xF7] & 0x02 == 0x02


def test_independent_scripts_coexist():
    vanilla = _nomodel()
    turn, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 1, "offset": 0, "operand": 0, "value": 40}])
    counter, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 2, "offset": 0, "operand": 0, "value": 41}])
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("turn", turn), ("counter", counter)], PATH)
    assert not fallback and not conflicts
    scripts = enemy_ai.read(merged)["scripts"]
    assert scripts[1]["instructions"][0]["operands"][0]["value"] == 40
    assert scripts[2]["instructions"][0]["operands"][0]["value"] == 41
    assert scripts[0]["instructions"][0]["operands"][0]["value"] == 0


def test_script_collision_follows_priority_with_conflict_unit():
    vanilla = _nomodel()
    low, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 1, "offset": 0, "operand": 0, "value": 40}])
    high, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 1, "offset": 0, "operand": 0, "value": 44}])
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("low", low), ("high", high)], PATH)
    assert not fallback
    assert enemy_ai.read(merged)["scripts"][1]["instructions"][0]["operands"][0]["value"] == 44
    assert conflicts == [{"unit": f"{PATH}:ai:Turn", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_independent_text_lines_coexist_across_size_changes():
    vanilla = _nomodel()
    first, _ = enemy_battle_text.apply_edits(vanilla, [{"id": 0, "text": "Alpha Gamma"}])
    second, _ = enemy_battle_text.apply_edits(vanilla, [{"id": 1, "text": "Zeta Bluish Green"}])
    assert len(first) != len(vanilla) and len(second) != len(vanilla)
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("first", first), ("second", second)], PATH)
    assert not fallback and not conflicts
    assert [line["text"] for line in enemy_battle_text.read(merged)["lines"]] == [
        "Alpha Gamma", "Zeta Bluish Green"]
    assert len(enemy_ai.read(merged)["scripts"]) == 5


def test_text_collision_follows_priority_with_conflict_unit():
    vanilla = _nomodel()
    low, _ = enemy_battle_text.apply_edits(vanilla, [{"id": 0, "text": "Lowland"}])
    high, _ = enemy_battle_text.apply_edits(vanilla, [{"id": 0, "text": "Highland"}])
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("low", low), ("high", high)], PATH)
    assert not fallback
    assert enemy_battle_text.read(merged)["lines"][0]["text"] == "Highland"
    assert conflicts == [{"unit": f"{PATH}:text:0", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_scripts_and_text_compose_together():
    vanilla = _nomodel()
    scripted, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 4, "offset": 0, "operand": 0, "value": 9}])
    worded, _ = enemy_battle_text.apply_edits(vanilla, [{"id": 1, "text": "Delta Force"}])
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("scripted", scripted), ("worded", worded)], PATH)
    assert not fallback and not conflicts
    assert enemy_ai.read(merged)["scripts"][4]["instructions"][0]["operands"][0]["value"] == 9
    assert [line["text"] for line in enemy_battle_text.read(merged)["lines"]][1] == "Delta Force"


def test_same_script_value_is_not_a_conflict():
    vanilla = _nomodel()
    edit = [{"script": 0, "offset": 0, "operand": 0, "value": 7}]
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("first", enemy_ai.apply_edits(vanilla, edit)[0]),
                  ("second", enemy_ai.apply_edits(vanilla, edit)[0])], PATH)
    assert not fallback and not conflicts


def test_monster_shape_merges_records_and_opaque_sections():
    vanilla = _monster()
    info_start = 52 + 96
    stats = bytearray(vanilla)
    stats[info_start + 0x14F] = 200
    scripted, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 0, "offset": 0, "operand": 0, "value": 11}])
    textured = bytearray(vanilla)
    bodies = _sections(bytes(textured))
    assert len(bodies) == 11
    tail = bytearray(bodies[10])
    tail[0] ^= 0xFF
    textured = vanilla[:len(vanilla) - len(bodies[10])] + bytes(tail)
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("stats", bytes(stats)), ("scripted", scripted),
                  ("textured", bytes(textured))], PATH)
    assert not fallback and not conflicts
    assert merged[info_start + 0x14F] == 200
    assert enemy_ai.read(merged)["scripts"][0]["instructions"][0]["operands"][0]["value"] == 11
    assert _sections(merged)[10] == _sections(bytes(textured))[10]


def test_opaque_section_collision_names_the_section():
    vanilla = _monster()
    bodies = _sections(vanilla)
    first = vanilla[:len(vanilla) - len(bodies[10])] + bytes([1]) * len(bodies[10])
    second = vanilla[:len(vanilla) - len(bodies[10])] + bytes([2]) * len(bodies[10])
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("first", first), ("second", second)], PATH)
    assert not fallback
    assert _sections(merged)[10] == bytes([2]) * len(bodies[10])
    assert conflicts == [{"unit": f"{PATH}:section:11:Textures", "winner": "second",
                          "claimants": ["first", "second"]}]


def test_info_bytes_outside_records_degrade_to_a_section_claim():
    vanilla = _nomodel()
    other = bytearray(vanilla)
    other[16 + 0x00] ^= 0xFF
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("other", bytes(other))], PATH)
    assert not fallback and not conflicts
    assert _sections(merged)[0] == bytes(other[16:16 + INFO_SIZE])


def test_masked_byte_unknown_bits_degrade_to_a_section_claim():
    vanilla = _nomodel()
    other = bytearray(vanilla)
    other[16 + 0xF7] |= 0x04  # No stat field owns bit 2.
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("other", bytes(other))], PATH)
    assert not fallback and not conflicts
    assert _sections(merged)[0] == bytes(other[16:16 + INFO_SIZE])


def test_ai_bytes_outside_records_degrade_to_a_section_claim():
    vanilla = _nomodel()
    other = bytearray(vanilla)
    other[-1] ^= 0xFF  # The text-data padding must stay zero.
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("other", bytes(other))], PATH)
    assert not fallback and not conflicts
    assert _sections(merged)[1] == bytes(other[16 + INFO_SIZE:])


def test_section_count_change_falls_back_opaque():
    vanilla = _nomodel()
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("other", _monster())], PATH)
    assert merged is None and not conflicts and "section count" in fallback


def test_unparseable_source_falls_back_opaque():
    vanilla = _nomodel()
    merged, conflicts, fallback = enemy_data_merge.merge(
        vanilla, [("broken", b"nope")], PATH)
    assert merged is None and not conflicts and "not a supported" in fallback


def test_unparseable_vanilla_falls_back_opaque():
    merged, conflicts, fallback = enemy_data_merge.merge(
        b"nope", [("other", _nomodel())], PATH)
    assert merged is None and not conflicts and "not a supported battle model" in fallback


def _write_mod(root, mod_id, payload, order):
    (root / "direct" / "battle").mkdir(parents=True, exist_ok=True)
    (root / PATH).write_bytes(payload)
    (root / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": mod_id, "name": mod_id.title(), "order": order, "enabled": True,
    }), encoding="utf-8")


def test_compose_merges_enemy_records_semantically(tmp_path):
    project, mods, active = tmp_path / "project", tmp_path / "mods", tmp_path / "active"
    baseline = tmp_path / "baseline"
    (baseline / "battle").mkdir(parents=True)
    vanilla = _nomodel()
    (baseline / "battle" / "c0m001.dat").write_bytes(vanilla)
    project.mkdir(parents=True)
    (project / runtime_layout.MOD_FILE).write_text(json.dumps({
        "id": "project", "name": "Project", "order": -1, "enabled": True,
    }), encoding="utf-8")
    stats = bytearray(vanilla)
    stats[16 + 0x102:16 + 0x104] = (300).to_bytes(2, "little")
    _write_mod(mods / "low", "low", bytes(stats), 0)
    scripted, _ = enemy_ai.apply_edits(
        vanilla, [{"script": 3, "offset": 0, "operand": 0, "value": 60}])
    worded, _ = enemy_battle_text.apply_edits(scripted, [{"id": 0, "text": "Lowland"}])
    _write_mod(mods / "high", "high", worded, 1)
    rows = runtime_layout.configure(project, mods, ["project", "low", "high"],
                                    {"project": True, "low": True, "high": True})
    result = runtime_layout.compose(project, active, rows, baseline_root=baseline)
    merged = (active / PATH).read_bytes()
    assert int.from_bytes(merged[16 + 0x102:16 + 0x104], "little") == 300
    assert enemy_ai.read(merged)["scripts"][3]["instructions"][0]["operands"][0]["value"] == 60
    assert enemy_battle_text.read(merged)["lines"][0]["text"] == "Lowland"
    conflict = next(row for row in result["conflicts"] if row["path"] == PATH)
    assert conflict["mode"] == "semantic merge" and conflict["claimants"] == ["low", "high"]
    assert "units" not in conflict
