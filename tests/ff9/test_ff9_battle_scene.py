"""Synthetic Unity archive/raw16 fixtures; no game assets are committed."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import pytest

from plugins.ff9 import battle_scene as battle, paths


def align4(value): return (value + 3) & ~3


def raw16():
    data = bytearray(8 + 56 + 116)
    struct.pack_into("<BBBBH", data, 0, 1, 1, 1, 0, 0x12)
    # pattern
    struct.pack_into("<BBBBI", data, 8, 100, 1, 2, 0, 77)
    struct.pack_into("<BBBBhhhh", data, 16, 0, 0, 0, 0, 10, 20, 30, 40)
    # enemy
    base = 64
    struct.pack_into("<IIIHHHH", data, base, 1, 2, 4, 1234, 55, 99, 222)
    data[base + 20:base + 24] = bytes([1, 2, 3, 4])
    data[base + 24:base + 28] = bytes([5, 6, 7, 8])
    struct.pack_into("<Hh", data, base + 28, 333, -44)
    struct.pack_into("<HH", data, base + 48, 0x1234, 17)
    data[base + 52:base + 56] = bytes([10, 11, 12, 13])
    data[base + 60:base + 72] = bytes([1, 2, 4, 8, 9, 3, 88, 40, 5, 6, 7, 21])
    struct.pack_into("<H", data, base + 76, 123)
    data[base + 78] = 9
    struct.pack_into("<HHHBBhhB", data, base + 98, 456, 25, 26, 4, 10, -2, 3, 5)
    return bytes(data)


def text_asset(name: str, content: bytes) -> bytes:
    raw = name.encode()
    value = bytearray(struct.pack("<I", len(raw)) + raw)
    value += b"\0" * (align4(len(raw)) - len(raw))
    value += struct.pack("<I", len(content)) + content
    return bytes(value)


def asset_bundle(path: str, info: int) -> bytes:
    raw = path.encode()
    value = bytearray(struct.pack("<III", 0, 0, 1))
    value += struct.pack("<I", len(raw)) + raw
    value += b"\0" * (align4(len(value)) - len(value))
    value += struct.pack("<IIIq", 2, 0, 0, info)
    return bytes(value)


def raw16_with_attacks():
    data = bytearray(8 + 56 + 116 + 32)
    struct.pack_into("<BBBBH", data, 0, 1, 1, 1, 2, 0x5555)
    # pattern (same shape as raw16)
    struct.pack_into("<BBBBI", data, 8, 100, 1, 2, 0, 77)
    struct.pack_into("<BBBBhhhh", data, 16, 0, 0, 0, 0, 10, 20, 30, 40)
    # minimal valid enemy record
    base = 64
    struct.pack_into("<IIIHHHH", data, base, 1, 2, 4, 1234, 55, 99, 222)
    # attack 0: SingleEnemy target, ally cursor, Hp display, VFX 300, legacy
    # sound bits set, for-dead, default-on-dead.
    attack = 8 + 56 + 116
    info = 2 | (1 << 4) | (1 << 5) | (300 << 8) | (0xABC << 17) | (1 << 29) | (1 << 31)
    struct.pack_into("<I", data, attack, info)
    struct.pack_into("<BBBBBBBBHH", data, attack + 4, 7, 80, 3, 90, 4, 20, 6, 1, 0x1234, 0x0042)
    # attack 1 stays zeroed: SingleAny(0), no flags, no bytes.
    return bytes(data)


def archive(scene="B3_001", payload=None) -> bytes:
    info_bundle, info_text = 1001, 1002
    path = f"assets/resources/battlemap/battlescene/evt_battle_{scene}/dbfile0000.raw16.bytes"
    bundle = asset_bundle(path, info_text)
    text = text_asset("dbfile0000", raw16() if payload is None else payload)
    # Header through object count, then align to 4 and two 28-byte records.
    prefix = bytearray()
    prefix += struct.pack(">IIIII", 0, 0, 0x0F, 100, 0)
    prefix += b"5.6.7f1\0"
    prefix += struct.pack("<I", 0) + b"\0" + struct.pack("<I", 0) + struct.pack("<I", 2)
    prefix += b"\0" * (align4(len(prefix)) - len(prefix))
    assert len(prefix) == 44
    prefix += struct.pack("<qIIIII", info_bundle, 0, len(bundle), 142, 0, 0)
    prefix += struct.pack("<qIIIII", info_text, len(bundle), len(text), 49, 0, 0)
    assert len(prefix) == 100
    return bytes(prefix) + bundle + text


@pytest.fixture
def store(tmp_path, monkeypatch):
    game = tmp_path / "game"; project = tmp_path / "project"
    target = game / "StreamingAssets/p0data2.bin"; target.parent.mkdir(parents=True)
    target.write_bytes(archive())
    monkeypatch.setattr(paths, "GAME_ROOT", game)
    monkeypatch.setattr(paths, "PROJECT_ROOT", project)
    return battle.BattleSceneStore(), target


@pytest.fixture
def attack_store(tmp_path, monkeypatch):
    game = tmp_path / "game"; project = tmp_path / "project"
    target = game / "StreamingAssets/p0data2.bin"; target.parent.mkdir(parents=True)
    target.write_bytes(archive("B3_002", raw16_with_attacks()))
    monkeypatch.setattr(paths, "GAME_ROOT", game)
    monkeypatch.setattr(paths, "PROJECT_ROOT", project)
    return battle.BattleSceneStore(), target


def test_unity_archive_finds_battle_scene(store):
    data = battle.UnityArchive(store[1]).battle_scenes()
    assert list(data) == ["B3_001"]
    assert data["B3_001"] == raw16()


def test_enemy_and_encounter_rows(store):
    database, _ = store
    enemies = database.load("enemies")
    assert enemies["rows"][0]["values"]["MaxHP"] == 1234
    assert enemies["rows"][0]["values"]["BlueMagic"] == 21
    encounters = database.load("encounters")
    row = encounters["rows"][0]
    assert row["values"]["Rate"] == 100 and row["values"]["Slot1X"] == 10


def test_enemy_save_writes_raw16_overlay_only(store):
    database, archive_path = store
    before = archive_path.read_bytes()
    data = database.load("enemies"); row = data["rows"][0]
    saved = database.save("enemies", data["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"], "values": {"MaxHP": 4321, "BlueMagic": 44}
    }])
    assert saved["rows"][0]["values"]["MaxHP"] == 4321
    assert saved["rows"][0]["values"]["BlueMagic"] == 44
    assert archive_path.read_bytes() == before
    overlay = database.project_root / database.relative("B3_001")
    assert overlay.is_file() and overlay.read_bytes() != raw16()
    assert overlay.relative_to(database.project_root).as_posix() == (
        "StreamingAssets/Assets/Resources/BattleMap/BattleScene/"
        "EVT_BATTLE_B3_001/dbfile0000.raw16.bytes"
    )


def test_encounter_save_bounds_and_stale_hash(store):
    database, _ = store
    data = database.load("encounters"); row = data["rows"][0]
    with pytest.raises(ValueError, match="Monster count"):
        database.save("encounters", data["sceneHashes"], [{"scene":"B3_001","record":0,"values":{"MonsterCount":5}}])
    source = database.project_root / database.relative("B3_001")
    source.parent.mkdir(parents=True, exist_ok=True); source.write_bytes(raw16())
    stale = database.load("encounters")
    source.write_bytes(source.read_bytes() + b"changed")
    with pytest.raises(RuntimeError, match="changed outside"):
        database.save("encounters", stale["sceneHashes"], [{"scene":"B3_001","record":0,"values":{"Rate":99}}])


def test_encounter_descriptors_match_runtime_bounds(store):
    database, _ = store
    data = database.load("encounters")
    fields = {field["key"]: field for field in data["fields"]}
    assert fields["MonsterCount"]["max"] == 4
    row = data["rows"][0]
    assert row["fieldBounds"]["MonsterCount"] == {"min": 0, "max": 4}
    assert row["fieldBounds"]["Slot1Type"] == {"min": 0, "max": 0}


def test_attack_rows_decode_verified_layout(attack_store):
    database, _ = attack_store
    data = database.load("enemy-attacks")
    assert [row["name"] for row in data["rows"]] == ["B3_002 · Attack 1", "B3_002 · Attack 2"]
    first = data["rows"][0]["values"]
    assert first["Target"] == "SingleEnemy(2)"
    assert first["DefaultAlly"] is True
    assert first["DisplayStats"] == 1
    assert first["VfxIndex"] == 300
    assert first["LegacySfx"] == 0xABC
    assert first["ForDead"] is True
    assert first["DefaultCamera"] is False
    assert first["DefaultOnDead"] is True
    assert (first["ScriptId"], first["Power"], first["Elements"], first["Rate"]) == (7, 80, 3, 90)
    assert (first["Category"], first["AddStatusNo"], first["MP"], first["Type"]) == (4, 20, 6, 1)
    assert (first["Vfx2"], first["Name"]) == (0x1234, 0x0042)
    second = data["rows"][1]["values"]
    assert second["Target"] == "SingleAny(0)"
    assert second["LegacySfx"] == 0
    fields = {field["key"]: field for field in data["fields"]}
    assert fields["Target"]["kind"] == "enum"
    assert fields["Target"]["choices"] == [
        "SingleAny(0)", "SingleAlly(1)", "SingleEnemy(2)", "ManyAny(3)",
        "ManyAlly(4)", "ManyEnemy(5)", "All(6)", "AllAlly(7)",
        "AllEnemy(8)", "Random(9)", "RandomAlly(10)", "RandomEnemy(11)",
        "Everyone(12)", "Self(13)", "Automatic(14)", "Special(15)",
    ]
    assert fields["DisplayStats"]["max"] == 7 and fields["VfxIndex"]["max"] == 511
    assert fields["LegacySfx"] == {"key": "LegacySfx", "label": "Legacy sound bits",
                                   "declaredType": "UInt32", "editable": False, "kind": "stored"}


def test_scene_flag_rows_decode_and_protect_upper_bits(attack_store):
    database, _ = attack_store
    data = database.load("scene-flags")
    assert [row["name"] for row in data["rows"]] == ["B3_002 · Scene 1"]
    values = data["rows"][0]["values"]
    # 0x5555 = 0101 0101 0101 0101: even bits set, odd bits clear.
    assert values["SpecialStart"] is True and values["BackAttack"] is False
    assert values["NoGameOver"] is True and values["NoExp"] is False
    assert values["NoWinPose"] is True and values["NoRunaway"] is False
    assert values["NoNeighboring"] is True and values["NoMagical"] is False
    assert values["ReverseAttack"] is True and values["FixedCamera1"] is False
    assert values["FixedCamera2"] is True and values["AfterEvent"] is False
    assert values["OtherFlags"] == 0x5
    fields = {field["key"]: field for field in data["fields"]}
    assert fields["NoRunaway"] == {"key": "NoRunaway", "label": "No escape",
                                   "declaredType": "Boolean", "editable": True, "kind": "boolean"}
    assert fields["OtherFlags"]["editable"] is False


def test_attack_and_flag_datasets_handle_zero_counts(store):
    database, _ = store
    assert database.load("enemy-attacks")["rows"] == []
    flags = database.load("scene-flags")
    assert len(flags["rows"]) == 1
    values = flags["rows"][0]["values"]
    # Fixture header flags are 0x12: BackAttack and NoWinPose set, rest clear.
    assert values["BackAttack"] is True and values["NoWinPose"] is True
    assert values["SpecialStart"] is False and values["OtherFlags"] == 0


def test_target_enum_round_trips_all_verified_values():
    scene = battle.BattleScene("B3_002", raw16_with_attacks())
    base = scene.attack_start
    bit = next(bit for bit in battle.ATTACK_INFO_BITS if bit.key == "Target")
    for index, choice in enumerate(battle.TARGET_CHOICES):
        scene.write_bits(base, bit, choice)
        assert scene.read_bits(base, bit) == choice
        word = struct.unpack_from("<I", scene.data, base)[0]
        assert word & 0xF == index
        # Untouched bits survive every write.
        assert (word >> 17) & 0xFFF == 0xABC
        assert (word >> 31) & 1 == 1
    with pytest.raises(ValueError, match="named values"):
        scene.write_bits(base, bit, "SingleEnemy(3)")
    with pytest.raises(ValueError, match="named values"):
        scene.write_bits(base, bit, 2)


def test_attack_save_round_trip_preserves_ignored_bits(attack_store):
    database, archive_path = attack_store
    before = archive_path.read_bytes()
    data = database.load("enemy-attacks")
    row = data["rows"][0]
    saved = database.save("enemy-attacks", data["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"],
        "values": {"Target": "AllEnemy(8)", "Power": 99, "ForDead": False},
    }])
    values = saved["rows"][0]["values"]
    assert values["Target"] == "AllEnemy(8)"
    assert values["Power"] == 99 and values["ForDead"] is False
    assert values["LegacySfx"] == 0xABC and values["VfxIndex"] == 300
    assert values["DefaultOnDead"] is True  # untouched high bit survives
    assert archive_path.read_bytes() == before
    overlay = (database.project_root / database.relative("B3_002")).read_bytes()
    assert overlay[:8 + 56 + 116] == raw16_with_attacks()[:8 + 56 + 116]  # header/pattern/enemy intact
    assert overlay[8 + 56 + 116 + 16:] == raw16_with_attacks()[8 + 56 + 116 + 16:]  # attack 1 intact


def test_attack_save_rejects_bad_values(attack_store):
    database, _ = attack_store
    data = database.load("enemy-attacks")
    row = data["rows"][0]

    def attempt(values):
        return database.save("enemy-attacks", data["sceneHashes"], [{
            "scene": row["scene"], "record": row["record"], "values": values}])

    with pytest.raises(ValueError, match="named values"):
        attempt({"Target": "Everyone(99)"})
    with pytest.raises(ValueError, match="Display stats"):
        attempt({"DisplayStats": 8})
    with pytest.raises(ValueError, match="VFX index"):
        attempt({"VfxIndex": 512})
    with pytest.raises(ValueError, match="must be true or false"):
        attempt({"ForDead": 1})
    with pytest.raises(ValueError, match="read-only"):
        attempt({"LegacySfx": 0})
    with pytest.raises(ValueError, match="not editable"):
        attempt({"NoSuchField": 1})
    with pytest.raises(ValueError, match="does not belong"):
        database.save("enemy-attacks", data["sceneHashes"], [{
            "scene": row["scene"], "record": 7, "values": {"Power": 1}}])


def test_scene_flag_save_preserves_version_counts_and_upper_bits(attack_store):
    database, archive_path = attack_store
    before = archive_path.read_bytes()
    data = database.load("scene-flags")
    row = data["rows"][0]
    saved = database.save("scene-flags", data["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"],
        "values": {"SpecialStart": False, "NoRunaway": True},
    }])
    values = saved["rows"][0]["values"]
    assert values["SpecialStart"] is False and values["NoRunaway"] is True
    assert values["OtherFlags"] == 0x5 and values["BackAttack"] is False
    assert archive_path.read_bytes() == before
    overlay = (database.project_root / database.relative("B3_002")).read_bytes()
    assert overlay[:4] == raw16_with_attacks()[:4]  # version + counts intact
    assert struct.unpack_from("<H", overlay, 4)[0] == 0x5574
    assert overlay[6:] == raw16_with_attacks()[6:]  # pad + all records intact
    fresh = database.load("scene-flags")
    with pytest.raises(ValueError, match="does not belong"):
        database.save("scene-flags", fresh["sceneHashes"], [{
            "scene": row["scene"], "record": 1, "values": {"NoExp": True}}])
    with pytest.raises(ValueError, match="must be true or false"):
        database.save("scene-flags", fresh["sceneHashes"], [{
            "scene": row["scene"], "record": 0, "values": {"NoExp": 1}}])
