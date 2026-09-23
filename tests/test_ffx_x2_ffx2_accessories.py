from __future__ import annotations

from pathlib import Path
import struct

import pytest

from games.ffx_x2.ffx2_accessories import (
    ARCHIVE_PATH, FFX2AccessoryError, apply_edits, parse_accessories, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(name_offset: int, name_key: int, help_offset: int, help_key: int,
            icon: int, abilities: list[int], price: int, fill: int = 0xCC) -> bytes:
    assert len(abilities) == 4
    raw = bytearray([fill] * 0x54)
    struct.pack_into("<HHHH", raw, 0x00, name_offset, name_key, help_offset, help_key)
    raw[0x0B] = icon
    for slot, ability_id in enumerate(abilities):
        struct.pack_into("<H", raw, 0x18 + slot * 2, ability_id)
    struct.pack_into("<I", raw, 0x20, price)
    return bytes(raw)


def _table(records: list[bytes], trailing: bytes = b"STRINGS") -> bytes:
    header = bytearray(0x20)
    header[:0x0C] = b"X2ACCESSORY!"
    struct.pack_into("<IIII", header, 0x0C, 0, len(records) - 1, 0x54, 0x54 * len(records))
    struct.pack_into("<I", header, 0x1C, 0x20)
    return bytes(header) + b"".join(records) + trailing


def test_ffx2_accessory_parses_proved_base_fields():
    data = _table([_record(0x10, 0x11, 0x20, 0x21, 7, [0x8001, 0x8002, 0, 0x8004], 12345)])
    row = parse_accessories(data)[0]
    assert row.record_id == 0
    assert (row.name_offset, row.name_key) == (0x10, 0x11)
    assert (row.help_offset, row.help_key) == (0x20, 0x21)
    assert row.icon == 7
    assert row.ability_ids == (0x8001, 0x8002, 0, 0x8004)
    assert row.price == 12345
    assert payload(data)["recordSize"] == 0x54


def test_ffx2_accessory_edit_changes_only_selected_abilities_and_price():
    original = _table([
        _record(0x10, 0x11, 0x20, 0x21, 7, [0x8001, 0x8002, 0x8003, 0x8004], 5000, fill=0xA5),
        _record(0x30, 0x31, 0x40, 0x41, 8, [0x8101, 0x8102, 0x8103, 0x8104], 6000, fill=0x5A),
    ], trailing=b"opaque-accessory-strings")
    edit = {"id": 0, "price": 99999, "abilities": [
        {"slot": 1, "abilityId": 0xBEEF},
        {"slot": 3, "abilityId": 0},
    ]}
    edited = apply_edits(original, [edit])
    rows = parse_accessories(edited)
    assert rows[0].price == 99999
    assert rows[0].ability_ids == (0x8001, 0xBEEF, 0x8003, 0)
    assert rows[1].price == 6000

    first = 0x20
    mutable = set(range(first + 0x18 + 2, first + 0x18 + 4))
    mutable.update(range(first + 0x18 + 6, first + 0x18 + 8))
    mutable.update(range(first + 0x20, first + 0x24))
    for offset, (before, after) in enumerate(zip(original, edited)):
        if offset not in mutable:
            assert after == before
    assert edited.endswith(b"opaque-accessory-strings")


def test_ffx2_accessory_rejects_unproved_header_or_record_shape():
    wrong_origin = bytearray(_table([_record(1, 2, 3, 4, 5, [0] * 4, 10)]))
    struct.pack_into("<I", wrong_origin, 0x0C, 1)
    struct.pack_into("<I", wrong_origin, 0x10, 1)
    with pytest.raises(FFX2AccessoryError, match="record zero"):
        parse_accessories(bytes(wrong_origin))

    wrong_size = bytearray(_table([_record(1, 2, 3, 4, 5, [0] * 4, 10)]))
    struct.pack_into("<I", wrong_size, 0x14, 0x50)
    struct.pack_into("<I", wrong_size, 0x18, 0x50)
    with pytest.raises(FFX2AccessoryError, match="record size"):
        parse_accessories(bytes(wrong_size))


def test_ffx2_accessory_rejects_duplicate_slots_and_empty_edits():
    data = _table([_record(1, 2, 3, 4, 5, [0] * 4, 10)])
    with pytest.raises(FFX2AccessoryError, match="Duplicate ability slot"):
        apply_edits(data, [{"id": 0, "abilities": [
            {"slot": 2, "abilityId": 3}, {"slot": 2, "abilityId": 4},
        ]}])
    with pytest.raises(FFX2AccessoryError, match="no writable edits"):
        apply_edits(data, [{"id": 0}])


def test_ffx2_accessory_managed_service_saves_canonical_x2_project(tmp_path: Path):
    source = _table([
        _record(0x10, 0x11, 0x20, 0x21, 7, [0x8001, 0x8002, 0, 0], 5000),
        _record(0x30, 0x31, 0x40, 0x41, 8, [0x8101, 0, 0, 0], 6000),
    ], trailing=b"opaque-service-strings")
    raw_archive_path = ARCHIVE_PATH.removeprefix("FFX2_Data/")
    game_root = tmp_path / "game"
    project_root = tmp_path / "project"
    theme_cache = tmp_path / "theme"
    _write_fixture_vbf(game_root / "data" / "FFX2_Data.vbf", [(raw_archive_path, source)])

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(project_root),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(theme_cache),
    }) as session:
        state = request_json(session.url + "api/ffx2-accessories")
        assert state["game"] == "x2"
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["rows"][0]["price"] == 5000

        edit = {"id": 0, "price": 77777, "abilities": [{"slot": 1, "abilityId": 0xCAFE}]}
        saved = request_json(session.url + "api/ffx2-accessories/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["price"] == 77777
        assert saved["rows"][0]["abilityIds"][1] == 0xCAFE

        target = project_root / "efl" / "x2" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == apply_edits(source, [edit])
        assert not (project_root / "efl" / "x2" / Path(*raw_archive_path.split("/"))).exists()

    assert session.wait_closed()
