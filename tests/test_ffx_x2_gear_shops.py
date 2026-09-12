from __future__ import annotations

from pathlib import Path
import struct

import pytest

from games.ffx_x2.gear_shops import (
    ARCHIVE_PATH, GearShopError, apply_edits, parse_gear_shops, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(rate: int, gear: list[int]) -> bytes:
    assert len(gear) == 16
    raw = bytearray(0x22)
    struct.pack_into("<H", raw, 0, rate)
    for slot, gear_id in enumerate(gear):
        struct.pack_into("<H", raw, 2 + slot * 2, gear_id)
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 6, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"GEARSHOP"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(records) - 1, 0x22, 0x22 * len(records))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_gear_shops_parse_fixed_inventory_slots():
    data = _table([
        _record(90, [0, 0x0101, 0x0102] + [0] * 13),
        _record(100, [0x0200] * 16),
    ])
    rows = parse_gear_shops(data)
    assert rows[0].record_id == 6
    assert rows[0].legacy_rate == 90
    assert rows[0].gear_ids[1:3] == (0x0101, 0x0102)
    assert rows[0].occupied_slots == 2
    assert payload(data)["slotCount"] == 16


def test_gear_shop_edits_preserve_unused_rate_other_slots_and_tail():
    original = _table([_record(321, list(range(16)))], min_index=12, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 12, "slots": [
        {"slot": 3, "gearId": 0xCAFE},
        {"slot": 15, "gearId": 0},
    ]}])
    row = parse_gear_shops(edited)[0]
    assert row.legacy_rate == 321
    assert row.gear_ids[3] == 0xCAFE
    assert row.gear_ids[2] == 2
    assert row.gear_ids[15] == 0
    assert edited[:0x16] == original[:0x16]
    assert edited[-6:] == b"opaque"


def test_gear_shop_rejects_wrong_record_size():
    data = bytearray(_table([_record(100, [0] * 16)]))
    struct.pack_into("<H", data, 0x0C, 0x20)
    struct.pack_into("<H", data, 0x0E, 0x20)
    with pytest.raises(GearShopError, match="record size"):
        parse_gear_shops(bytes(data))


def test_gear_shop_rejects_duplicate_slots():
    data = _table([_record(100, [0] * 16)])
    with pytest.raises(GearShopError, match="Duplicate slot"):
        apply_edits(data, [{"id": 6, "slots": [
            {"slot": 1, "gearId": 3}, {"slot": 1, "gearId": 4},
        ]}])


def test_gear_shop_managed_service_resolves_raw_vbf_and_saves_canonical_project(tmp_path: Path):
    source = _table([
        _record(90, [0x0101, 0x0102] + [0] * 14),
        _record(100, [0x0201] + [0] * 15),
    ], min_index=0x30, trailing=b"opaque-service-tail")
    raw_archive_path = ARCHIVE_PATH.removeprefix("FFX_Data/")
    game_root = tmp_path / "game"
    project_root = tmp_path / "project"
    theme_cache = tmp_path / "theme"
    _write_fixture_vbf(game_root / "data" / "FFX_Data.vbf", [(raw_archive_path, source)])

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(project_root),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(theme_cache),
    }) as session:
        state = request_json(session.url + "api/gear-shops")
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["rows"][0]["gearIds"][1] == 0x0102

        edit = {"id": 0x30, "slots": [{"slot": 1, "gearId": 0xCAFE}]}
        saved = request_json(session.url + "api/gear-shops/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["gearIds"][1] == 0xCAFE

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == apply_edits(source, [edit])
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert session.wait_closed()
