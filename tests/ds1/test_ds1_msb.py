"""Map placement reading, editing and byte preservation on synthetic MSBs."""
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from msb_fixture import build_msb
from plugins.ds1.msb import MsbDocument, MsbError

NPC_IDS = frozenset({120000, 120100, 121000})


def test_placements_listed_with_models_and_links():
    doc = MsbDocument(build_msb())
    placements = doc.placements()
    assert [(p["type"], p["partId"], p["kind"]) for p in placements] == [(2, 0, "Enemy"), (4, 0, "Player"), (1, 0, "Object")]
    enemy = placements[0]
    assert (enemy["name"], enemy["model"], enemy["npc"], enemy["think"]) == ("enemy0", "c1200", 120000, 1000)
    assert enemy["pos"] == (1.0, 2.0, 3.0) and enemy["rot"] == (0.0, 90.0, 0.0)
    assert doc.read_placement((2, 0))["fields"][-1]["key"] == "npcId"
    assert [f["key"] for f in doc.read_placement((4, 0))["fields"]] == ["posX", "posY", "posZ", "rotX", "rotY", "rotZ"]


def test_edit_roundtrip_exact_byte_boundary_and_revert():
    raw = build_msb()
    doc = MsbDocument(raw)
    doc.edit((2, 0), "posX", 10.5)
    doc.edit((2, 0), "rotY", -45.0)
    doc.edit((2, 0), "npcId", 120100, NPC_IDS)
    doc.edit((4, 0), "posZ", 7.25)
    assert doc.dirty_count == 4
    changed = doc.export()
    diff = [i for i, (a, b) in enumerate(zip(raw, changed)) if a != b]
    assert 0 < len(diff) <= 16
    assert MsbDocument(changed).read_placement((2, 0))["fields"][0]["value"] == 10.5
    doc.edit((2, 0), "posX", 1.0)
    doc.edit((2, 0), "rotY", 90.0)
    doc.edit((2, 0), "npcId", 120000, NPC_IDS)
    doc.edit((4, 0), "posZ", 3.0)
    assert doc.export() == raw and doc.dirty_count == 0


def test_npc_validation_and_unknown_original_reset():
    raw = build_msb(parts=(("enemy", 2, 0, 0, 999001),))
    doc = MsbDocument(raw)
    with pytest.raises(MsbError):
        doc.edit((2, 0), "npcId", 999002, NPC_IDS)
    with pytest.raises(MsbError):
        doc.edit((2, 0), "npcId", 120000.5, NPC_IDS)
    doc.edit((2, 0), "npcId", 120000, NPC_IDS)
    doc.edit((2, 0), "npcId", 999001, NPC_IDS)
    assert doc.export() == raw and doc.dirty_count == 0


def test_float_validation_and_protected_fields():
    doc = MsbDocument(build_msb())
    for bad in (float("nan"), float("inf"), "1.5", True, None):
        with pytest.raises(MsbError):
            doc.edit((2, 0), "posX", bad)
    doc.edit((2, 0), "posX", 5)
    assert doc.read_placement((2, 0))["fields"][0]["value"] == 5.0
    for key in ("think", "talk", "model", "name", "scale"):
        with pytest.raises(MsbError):
            doc.edit((2, 0), key, 0)
    with pytest.raises(MsbError):
        doc.edit((4, 0), "npcId", 120000, NPC_IDS)
    with pytest.raises(MsbError):
        doc.edit((0, 0), "posX", 1.0)
    with pytest.raises(MsbError):
        doc.read_placement((2, 99))


def test_object_placements_move_but_name_nothing():
    raw = build_msb()
    doc = MsbDocument(raw)
    placement = next(p for p in doc.placements() if p["type"] == 1)
    assert (placement["partId"], placement["kind"], placement["name"]) == (0, "Object", "chest0")
    assert "npc" not in placement and "think" not in placement
    assert [f["key"] for f in doc.read_placement((1, 0))["fields"]] == ["posX", "posY", "posZ", "rotX", "rotY", "rotZ"]
    doc.edit((1, 0), "posX", 10.5)
    doc.edit((1, 0), "rotY", -45.0)
    assert doc.dirty_count == 2
    changed = doc.export()
    diff = [i for i, (a, b) in enumerate(zip(raw, changed)) if a != b]
    assert 0 < len(diff) <= 8
    assert MsbDocument(changed).read_placement((1, 0))["fields"][0]["value"] == 10.5
    doc.edit((1, 0), "posX", 1.0)
    doc.edit((1, 0), "rotY", 90.0)
    assert doc.export() == raw and doc.dirty_count == 0
    units = [unit for unit in doc.merge_units() if unit[0] == (1, 0)]
    assert {unit[1] for unit in units} == {"posX", "posY", "posZ", "rotX", "rotY", "rotZ"}
    with pytest.raises(MsbError):
        doc.edit((1, 0), "npcId", 120000, NPC_IDS)
    rubble = MsbDocument(build_msb(parts=(("rubble", 9, 0, 1, None),)))
    assert [(p["type"], p["kind"]) for p in rubble.placements()] == [(9, "Object")]
    rubble.edit((9, 0), "posZ", 5.0)
    assert rubble.read_placement((9, 0))["fields"][2]["value"] == 5.0


def test_malformed_maps_rejected():
    good = build_msb()
    trunc = bytearray(good[:100])
    with pytest.raises(MsbError):
        MsbDocument(bytes(trunc))
    bad_version = bytearray(good)
    struct.pack_into("<i", bad_version, 0, 1)
    with pytest.raises(MsbError):
        MsbDocument(bytes(bad_version))
    bad_count = bytearray(good)
    struct.pack_into("<i", bad_count, 8, 0)
    with pytest.raises(MsbError):
        MsbDocument(bytes(bad_count))
    dup = build_msb(parts=(("enemy", 2, 0, 0, 120000), ("enemy", 2, 0, 0, 120100)))
    with pytest.raises(MsbError):
        MsbDocument(dup)
    raw = bytearray(build_msb())
    doc = MsbDocument(bytes(raw))
    base = doc.parts[0]["base"]
    raw[base + 4] = 99
    with pytest.raises(MsbError):
        MsbDocument(bytes(raw))
    raw = bytearray(build_msb())
    struct.pack_into("<i", raw, doc.parts[0]["base"] + 12, 99)
    with pytest.raises(MsbError):
        MsbDocument(bytes(raw))
    raw = bytearray(build_msb())
    struct.pack_into("<i", raw, doc.parts[0]["base"] + 0x60, 1)
    with pytest.raises(MsbError):
        MsbDocument(bytes(raw))


def test_create_placement_from_same_model_template():
    doc = MsbDocument(build_msb())
    row = doc.create_placement("c1200", [10.0, 20.0, 30.0], [0.0, 45.0, 0.0])
    assert row["model"] == "c1200"
    fields = {item["key"]: item["value"] for item in row["fields"]}
    assert (fields["posX"], fields["posY"], fields["posZ"]) == (10.0, 20.0, 30.0)
    assert (fields["rotX"], fields["rotY"], fields["rotZ"]) == (0.0, 45.0, 0.0)
    assert row["partId"] != 0
    assert row["think"] == 1000
    assert fields["npcId"] == 120000


def test_create_placement_needs_a_template():
    doc = MsbDocument(build_msb())
    with pytest.raises(MsbError):
        doc.create_placement("nope", [0, 0, 0], [0, 0, 0])
    single = MsbDocument(build_msb(parts=(("piece", 0, 0, 1, None),)))
    with pytest.raises(MsbError, match="no enemy or object placement"):
        single.create_placement("m10piece", [0, 0, 0], [0, 0, 0])
    player_only = MsbDocument(build_msb(parts=(("player", 4, 0, 1, None),)))
    with pytest.raises(MsbError, match="no enemy or object placement"):
        player_only.create_placement("m10piece", [0, 0, 0], [0, 0, 0])


def test_create_placement_takes_pasted_enemy_identity():
    doc = MsbDocument(build_msb())
    row = doc.create_placement("c1200", [1, 2, 3], [0, 0, 0], npc=120100)
    fields = {item["key"]: item["value"] for item in row["fields"]}
    assert fields["npcId"] == 120100
