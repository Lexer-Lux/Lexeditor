"""Synthetic p0data1/BGI fixtures; no FF9 game bytes are committed."""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from plugins.ff9 import field_walkmesh as walkmesh


def align4(value):
    return (value + 3) & ~3


def bgi_bytes() -> bytes:
    # Memoria BGI_DEF offsets are relative to byte 4. Two 40-byte triangles
    # start at absolute 64; two 32-byte floors follow at 144; each floor
    # points at one triangle id in the trailing int32 lists.
    data = bytearray(216)
    struct.pack_into("<I", data, 0, walkmesh.BGI_MAGIC)
    struct.pack_into("<H", data, 4, len(data) - 4)
    struct.pack_into("<hh", data, 36, 0, 0)
    struct.pack_into("<HHHHHHHHHHHH", data, 40,
                     2, 60, 0, 140, 0, 140, 2, 140, 0, 212, 0, 212)

    # Triangle 0: active + all three documented pathing attributes + unknown bit 0x20.
    # Triangle 1: inactive plus unknown bit 0x40, floor 9.
    struct.pack_into("<HHhhhh", data, 64, 0xD021, 0x1234, 7, 0, 0, 0)
    struct.pack_into("<HHhhhh", data, 104, 0x40, 0x5678, 9, 0, 0, 0)

    # Floor 0: active plus unknown bit 0x40. Floor 1: inactive plus 0x80.
    for index, (flags, floor_ndx, tri_offset) in enumerate(((0x41, 7, 204), (0x80, 9, 208))):
        off = 144 + index * 32
        struct.pack_into("<HH", data, off, flags, floor_ndx)
        struct.pack_into("<HH", data, off + 28, 1, tri_offset)
    struct.pack_into("<i", data, 208, 0)
    struct.pack_into("<i", data, 212, 1)
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


def test_bgi_triangle_parser_bounds_floor_and_unknown_bits():
    triangles = walkmesh._triangle_table(bgi_bytes())
    assert [
        (t["floorNdx"], t["active"], t["alternateFootstep"], t["preventNPC"], t["preventPC"], t["otherFlags"])
        for t in triangles
    ] == [
        (7, True, True, True, True, 0x20),
        (9, False, False, False, False, 0x40),
    ]
    malformed = bytearray(bgi_bytes())
    struct.pack_into("<H", malformed, 42, 0xFFFF)
    with pytest.raises(ValueError, match="triangle table"):
        walkmesh._triangle_table(bytes(malformed))


def test_load_scopes_triangle_activity_to_one_field(store):
    database, archive_path, _project = store
    second = archive_path.with_name("p0data12.bin")
    second.write_bytes(archive("FBG_N21_TEST_MAP001_TEST_1"))
    data = database.load("field-walkmesh-triangles")
    assert len(data["scenes"]) == 2
    assert data["activeScene"] == data["scenes"][0]["value"]
    assert len(data["rows"]) == 2
    assert data["rows"][0]["values"] == {
        "Field": "FBG_N21_TEST_MAP000_TEST_0", "Triangle": 0, "Floor": 7,
        "Active": True, "AlternateFootstep": True, "PreventNPC": True, "PreventPC": True,
        "OtherFlags": 0x20,
    }
    other = data["scenes"][1]["value"]
    scoped = database.load("field-walkmesh-triangles", other)
    assert scoped["activeScene"] == other and len(scoped["rows"]) == 2
    assert {row["values"]["Field"] for row in scoped["rows"]} == {"FBG_N21_TEST_MAP001_TEST_1"}
    with pytest.raises(ValueError, match="Unknown FF9 field-walkmesh scene"):
        database.load("field-walkmesh-triangles", "not/a/scene.bgi.bytes")


def test_triangle_save_toggles_only_active_bit_and_reopens_project(store):
    database, archive_path, project = store
    archive_before = archive_path.read_bytes()
    loaded = database.load("field-walkmesh-triangles")
    row = loaded["rows"][0]
    saved = database.save("field-walkmesh-triangles", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"], "values": {"Active": False},
    }])
    assert archive_path.read_bytes() == archive_before
    target = project / row["scene"]
    before = bgi_bytes(); after = target.read_bytes()
    changed = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
    assert changed == [64]
    assert struct.unpack_from("<H", after, 64)[0] == 0xD020
    assert after[:64] == before[:64] and after[65:] == before[65:]
    assert saved["activeScene"] == row["scene"]
    assert saved["rows"][0]["source"] == "project"
    assert saved["rows"][0]["values"]["Active"] is False
    assert saved["rows"][0]["values"]["OtherFlags"] == 0x20


def test_triangle_named_pathing_flags_preserve_unknown_bits(store):
    database, archive_path, project = store
    archive_before = archive_path.read_bytes()
    loaded = database.load("field-walkmesh-triangles")
    row = loaded["rows"][0]
    saved = database.save("field-walkmesh-triangles", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"],
        "values": {"AlternateFootstep": False, "PreventNPC": False, "PreventPC": False},
    }])
    assert archive_path.read_bytes() == archive_before
    after = (project / row["scene"]).read_bytes()
    before = bgi_bytes()
    changed = [offset for offset, (left, right) in enumerate(zip(before, after)) if left != right]
    assert changed == [65]
    assert struct.unpack_from("<H", after, 64)[0] == 0x0021
    saved_row = saved["rows"][0]
    assert saved_row["values"]["Active"] is True
    assert saved_row["values"]["AlternateFootstep"] is False
    assert saved_row["values"]["PreventNPC"] is False
    assert saved_row["values"]["PreventPC"] is False
    assert saved_row["values"]["OtherFlags"] == 0x20


def test_triangle_noop_and_stale_save_guards(store):
    database, archive_path, project = store
    loaded = database.load("field-walkmesh-triangles")
    row = loaded["rows"][0]
    saved = database.save("field-walkmesh-triangles", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"], "values": {"Active": True},
    }])
    assert not (project / row["scene"]).exists()
    assert saved["rows"][0]["source"] == "vanilla"
    raw = bytearray(archive_path.read_bytes())
    marker = raw.index(struct.pack("<I", walkmesh.BGI_MAGIC))
    raw[marker + 6] ^= 1
    archive_path.write_bytes(raw)
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        database.save("field-walkmesh-triangles", loaded["sceneHashes"], [{
            "scene": row["scene"], "record": row["record"], "values": {"Active": False},
        }])


def test_walkmesh_validation_rejects_invalid_floor_triangle_reference():
    malformed = bytearray(bgi_bytes())
    struct.pack_into("<i", malformed, 208, 99)
    with pytest.raises(ValueError, match="invalid triangle"):
        walkmesh.FieldWalkmeshStore._validate_asset(bytes(malformed))


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
    assert changed == [144]
    assert struct.unpack_from("<H", after, 144)[0] == 0x40
    assert after[:144] == before[:144] and after[145:] == before[145:]
    saved_row = next(r for r in saved["rows"] if r["record"] == 0)
    assert saved_row["source"] == "project" and saved_row["values"]["Active"] is False
    assert saved_row["values"]["OtherFlags"] == 0x40



def test_noop_save_does_not_create_overlay(store):
    database, _archive, project = store
    loaded = database.load("field-walkmesh")
    row = loaded["rows"][0]
    saved = database.save("field-walkmesh", loaded["sceneHashes"], [{
        "scene": row["scene"], "record": row["record"], "values": {"Active": True},
    }])
    assert not (project / row["scene"]).exists()
    assert saved["rows"][0]["source"] == "vanilla"


def test_save_refuses_stale_vanilla_archive(store):
    database, archive_path, _project = store
    loaded = database.load("field-walkmesh")
    row = loaded["rows"][0]
    raw = bytearray(archive_path.read_bytes())
    marker = raw.index(struct.pack("<I", walkmesh.BGI_MAGIC))
    raw[marker + 6] ^= 1
    archive_path.write_bytes(raw)
    with pytest.raises(RuntimeError, match="changed outside Lexeditor"):
        database.save("field-walkmesh", loaded["sceneHashes"], [{
            "scene": row["scene"], "record": row["record"], "values": {"Active": False},
        }])

def test_save_refuses_unknown_fields_and_stale_project_source(store):
    database, _archive, project = store
    loaded = database.load("field-walkmesh")
    row = loaded["rows"][0]
    with pytest.raises(ValueError, match="Only documented FF9 walkmesh"):
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
