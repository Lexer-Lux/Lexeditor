from __future__ import annotations

from pathlib import Path
import struct

import pytest

from games.ffx_x2.auto_ability_prices import (
    ARCHIVE_PATH, AutoAbilityPriceError, apply_edits, parse_auto_ability_prices, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _table(prices: list[int], min_index: int = 0, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"ARMSRATE"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(prices) - 1, 4, 4 * len(prices))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(struct.pack("<I", price) for price in prices) + trailing


def test_auto_ability_prices_map_ordinal_to_0x8000_ids():
    data = _table([1000, 2000, 3000], min_index=9)
    rows = parse_auto_ability_prices(data)
    assert [row.record_id for row in rows] == [9, 10, 11]
    assert [row.ability_id for row in rows] == [0x8000, 0x8001, 0x8002]
    assert [row.gil_price for row in rows] == [1000, 2000, 3000]
    assert payload(data)["abilityBase"] == 0x8000


def test_auto_ability_price_edit_changes_only_selected_u32():
    original = _table([100, 200, 300], min_index=2, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 3, "gilPrice": 0x12345678}])
    rows = parse_auto_ability_prices(edited)
    assert [row.gil_price for row in rows] == [100, 0x12345678, 300]
    assert edited[:0x18] == original[:0x18]
    assert edited[0x1C:] == original[0x1C:]
    assert edited[-6:] == b"opaque"


def test_auto_ability_prices_reject_wrong_record_size_and_duplicate():
    data = bytearray(_table([100]))
    struct.pack_into("<H", data, 0x0C, 2)
    struct.pack_into("<H", data, 0x0E, 2)
    with pytest.raises(AutoAbilityPriceError, match="record size"):
        parse_auto_ability_prices(bytes(data))

    valid = _table([100])
    with pytest.raises(AutoAbilityPriceError, match="Duplicate"):
        apply_edits(valid, [
            {"id": 0, "gilPrice": 10}, {"id": 0, "gilPrice": 20},
        ])


def test_auto_ability_price_service_saves_canonical_project(tmp_path: Path):
    source = _table([1000, 2000], min_index=4, trailing=b"opaque-service-tail")
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
        state = request_json(session.url + "api/auto-ability-prices")
        assert state["source"] == "archive"
        assert state["rows"][0]["abilityId"] == 0x8000
        edit = {"id": 4, "gilPrice": 7777}
        saved = request_json(session.url + "api/auto-ability-prices/save", {
            "headerMd5": state["headerMd5"], "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["source"] == "project"
        assert saved["rows"][0]["gilPrice"] == 7777
        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == apply_edits(source, [edit])
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert session.wait_closed()
