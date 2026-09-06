"""Synthetic Unity archive/raw16 fixtures; no game assets are committed."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import pytest

from games.ff9 import battle_scene as battle, paths


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


def archive(scene="B3_001") -> bytes:
    info_bundle, info_text = 1001, 1002
    path = f"assets/resources/battlemap/battlescene/evt_battle_{scene}/dbfile0000.raw16.bytes"
    bundle = asset_bundle(path, info_text)
    text = text_asset("dbfile0000", raw16())
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
