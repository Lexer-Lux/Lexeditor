from __future__ import annotations

from pathlib import Path
import struct

import pytest

from games.ffx_x2.ctb_base import ARCHIVE_PATH, CtbBaseError, apply_edits, parse_ctb_base, payload
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _table(rows: list[tuple[int, int]], min_index: int = 0, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"CTBBASE!"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(rows) - 1, 2, 2 * len(rows))
    header[0x10:0x14] = b"KEEP"
    records = bytes(value for row in rows for value in row)
    return bytes(header) + records + trailing


def test_ctb_base_maps_agility_and_icv_range():
    data = _table([(10, 3), (20, 7)], min_index=4)
    rows = parse_ctb_base(data)
    assert rows[0].record_id == 4
    assert rows[0].agility == 5
    assert rows[0].tick_speed == 10
    assert rows[0].icv_bonus == 3
    assert rows[0].min_icv == 27
    assert rows[0].max_icv == 30
    assert payload(data)["recordSize"] == 2


def test_ctb_edit_changes_only_selected_two_byte_record():
    original = _table([(10, 3), (20, 7), (30, 9)], min_index=1, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 2, "tickSpeed": 44, "icvBonus": 11}])
    rows = parse_ctb_base(edited)
    assert [(row.tick_speed, row.icv_bonus) for row in rows] == [(10, 3), (44, 11), (30, 9)]
    assert edited[:0x16] == original[:0x16]
    assert edited[0x18:] == original[0x18:]
    assert edited[-6:] == b"opaque"


def test_ctb_base_rejects_wrong_record_size():
    data = bytearray(_table([(10, 3)]))
    struct.pack_into("<H", data, 0x0C, 4)
    struct.pack_into("<H", data, 0x0E, 4)
    data[0x14:0x16] = b"\x00\x00"
    with pytest.raises(CtbBaseError, match="record size"):
        parse_ctb_base(bytes(data))


def test_ctb_base_rejects_duplicate_and_out_of_range_edits():
    data = _table([(10, 3)])
    with pytest.raises(CtbBaseError, match="Duplicate"):
        apply_edits(data, [
            {"id": 0, "tickSpeed": 10, "icvBonus": 3},
            {"id": 0, "tickSpeed": 11, "icvBonus": 4},
        ])
    with pytest.raises(CtbBaseError, match="Tick speed"):
        apply_edits(data, [{"id": 0, "tickSpeed": 256, "icvBonus": 3}])


def test_ctb_managed_service_resolves_raw_vbf_and_saves_canonical_project(tmp_path: Path):
    source = _table([(10, 3), (20, 7)], min_index=4, trailing=b"opaque-service-tail")
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
        state = request_json(session.url + "api/ctb-base")
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["rows"][0] == {
            "id": 4, "agility": 5, "tickSpeed": 10, "icvBonus": 3,
            "minIcv": 27, "maxIcv": 30,
        }

        edit = {"id": 4, "tickSpeed": 12, "icvBonus": 5}
        saved = request_json(session.url + "api/ctb-base/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["tickSpeed"] == 12
        assert saved["rows"][0]["icvBonus"] == 5
        assert saved["rows"][0]["minIcv"] == 31
        assert saved["rows"][0]["maxIcv"] == 36

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == apply_edits(source, [edit])
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert session.wait_closed()
