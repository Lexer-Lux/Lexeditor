"""Synthetic p0data1/BGI fixtures; no FF9 game bytes are committed."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from games.ff9 import field_walkmesh as walkmesh


def align4(value):
    return (value + 3) & ~3


def bgi_bytes() -> bytes:
    # Header offsets follow Memoria's BGI_DEF.ReadData. Two 32-byte floors start
    # at relative offset 60 (absolute byte 64); each points at one triangle id.
    data = bytearray(136)
    struct.pack_into("<I", data, 0, walkmesh.BGI_MAGIC)
    struct.pack_into("<H", data, 4, len(data) - 4)
    struct.pack_into("<hh", data, 36, 0, 0)
    struct.pack_into("<HHHHHHHHHHHH", data, 40,
                     0, 60, 0, 60, 0, 60, 2, 60, 0, 124, 0, 124)
    # Floor 0: active plus unknown bit 0x40. Floor 1: inactive plus 0x80.
    for index, (flags, floor_ndx, tri_offset) in enumerate(((0x41, 7, 124), (0x80, 9, 128))):
        off = 64 + index * 32
        struct.pack_into("<HH", data, off, flags, floor_ndx)
        struct.pack_into("<HH", data, off + 28, 1, tri_offset)
    struct.pack_into("<i", data, 128, 123)
    struct.pack_into("<i", data, 132, 456)
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


def archive(folder="FBG_N21_TEST_MAP000_TEST_0") -> bytes:
    info_bundle, info_text = 3001, 3002
    path = f"assets/resources/FieldMaps/{folder}/{folder}.bgi.bytes"
    bundle = asset_bundle(path, info_text)
    text = text_asset(folder, bgi_bytes())
    prefix = bytearray()
    prefix += struct.pack(">IIIII", 0, 0, 0x0F, 100, 0)
    prefix += b"5.6.7f1\0"
    prefix += struct.pack("<I", 0) + b"\0" + struct.pack("<I", 0) + struct.pack("<I", 2)
    prefix += b"\0" * (align4(len(prefix)) - len(prefix))
    prefix += struct.pack("<qIIIII", info_bundle, 0, len(bundle), 142, 0, 0)
    prefix += struct.pack("<qIIIII", info_text, len(bundle), len(text), 49, 0, 0)
    assert len(prefix) == 100
    return bytes(prefix) + bundle + text


@pytest.fixture
def store(tmp_path):
    game, project = tmp_path / "game", tmp_path / "project"
    source = game / "StreamingAssets" / "p0data11.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(archive())
    return walkmesh.FieldWalkmeshStore(game, project), source, project


def test_bgi_floor_parser_bounds_and_unknown_bits():
    floors = walkmesh._floor_table(bgi_bytes())
    assert [(f["floorNdx"], f["active"], f["otherFlags"], f["triangleCount"]) for f in floors] == [
        (7, True, 0x40, 1), (9, False, 0x80, 1),
    ]
    with pytest.raises(ValueError):
        walkmesh._floor_table(bgi_bytes()[:70])


def test_load_lists_floor_activity_from_p0data1(store):
    database, _archive, _project = store
    data = database.load("field-walkmesh")
    assert len(data["rows"]) == 2
    assert data["rows"][0]["values"] == {
        "Field": "FBG_N21_TEST_MAP000_TEST_0", "Floor": 7,
        "Active": True, "Triangles": 1, "OtherFlags": 0x40,
    }
    assert data["rows"][1]["values"]["Active"] is False
    assert data["sceneHashes"]


def test_save_toggles_only_active_bit_and_reopens_project(store):
    database, archive_path, project = store
    archive_before = archive_path.read_bytes()
    loaded = database.load("field-walkmesh")
    row = loaded["rows"][0]
    saved = database.save("field-walkmesh", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"], "values": {"Active": False},
    }])
    assert archive_path.read_bytes() == archive_before
    target = project / row["scene"]
    assert target.is_file()
    before = bgi_bytes(); after = target.read_bytes()
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert changed == [64]
    assert struct.unpack_from("<H", after, 64)[0] == 0x40
    assert after[65:] == before[65:]
    saved_row = next(r for r in saved["rows"] if r["record"] == 0)
    assert saved_row["source"] == "project" and saved_row["values"]["Active"] is False
    assert saved_row["values"]["OtherFlags"] == 0x40


def test_save_refuses_unknown_fields_and_stale_project_source(store):
    database, _archive, project = store
    loaded = database.load("field-walkmesh")
    row = loaded["rows"][0]
    with pytest.raises(ValueError, match="Only FF9 walkmesh"):
        database.save("field-walkmesh", loaded["sceneHashes"], [{
            "scene": row["scene"], "record": 0, "values": {"Triangles": 9},
        }])
    database.save("field-walkmesh", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": 0, "values": {"Active": False},
    }])
    current = database.load("field-walkmesh")
    target = project / row["scene"]
    target.write_bytes(target.read_bytes() + b"external")
    with pytest.raises((RuntimeError, ValueError)):
        database.save("field-walkmesh", current["sceneHashes"], [{
            "scene": row["scene"], "record": 0, "values": {"Active": True},
        }])
