from __future__ import annotations

from pathlib import Path
import struct

import pytest

from games.ffx_x2.mix_table import ARCHIVE_PATH, MixTableError, apply_edits, parse_mix_table, payload
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(values: dict[int, int]) -> bytes:
    raw = bytearray(0xE0)
    for partner, result in values.items():
        struct.pack_into("<H", raw, partner * 2, result)
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 0, trailing: bytes = b"TAIL") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"MIXTABLE"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(records) - 1, 0xE0, 0xE0 * len(records))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_mix_table_maps_origin_and_partner_command_ids():
    data = _table([
        _record({0: 0x3001, 5: 0x3002}),
        _record({1: 0x3003}),
    ], min_index=7)
    rows = parse_mix_table(data)
    assert rows[0].record_id == 7
    assert rows[0].origin_command_id == 0x2000
    assert rows[0].result_command_ids[0] == 0x3001
    assert rows[0].result_command_ids[5] == 0x3002
    assert rows[0].defined_results == 2
    state = payload(data)
    assert state["partnerCount"] == 0x70
    assert state["commandBase"] == 0x2000


def test_mix_edit_changes_only_selected_result_slots():
    original = _table([_record({0: 0x3001, 1: 0x3002, 2: 0x3003})], min_index=4, trailing=b"opaque")
    edited = apply_edits(original, [{"id": 4, "results": [
        {"partner": 1, "resultCommandId": 0xBEEF},
        {"partner": 3, "resultCommandId": 0xCAFE},
    ]}])
    row = parse_mix_table(edited)[0]
    assert row.result_command_ids[:4] == (0x3001, 0xBEEF, 0x3003, 0xCAFE)
    assert edited[:0x16] == original[:0x16]
    assert edited[0x1C:] == original[0x1C:]
    assert edited[-6:] == b"opaque"


def test_mix_table_rejects_wrong_record_size():
    data = bytearray(_table([_record({})]))
    struct.pack_into("<H", data, 0x0C, 0xDE)
    struct.pack_into("<H", data, 0x0E, 0xDE)
    with pytest.raises(MixTableError, match="record size"):
        parse_mix_table(bytes(data))


def test_mix_table_rejects_duplicate_partners_and_out_of_range_values():
    data = _table([_record({})])
    with pytest.raises(MixTableError, match="Duplicate partner"):
        apply_edits(data, [{"id": 0, "results": [
            {"partner": 2, "resultCommandId": 3},
            {"partner": 2, "resultCommandId": 4},
        ]}])
    with pytest.raises(MixTableError, match="Mix partner"):
        apply_edits(data, [{"id": 0, "results": [{"partner": 112, "resultCommandId": 3}]}])


def test_mix_managed_service_resolves_raw_vbf_and_saves_canonical_project(tmp_path: Path):
    source = _table([
        _record({0: 0x3001, 5: 0x3002}),
        _record({1: 0x3003}),
    ], min_index=0x20, trailing=b"opaque-service-tail")
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
        state = request_json(session.url + "api/mix-table")
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["rows"][0]["originCommandId"] == 0x2000
        assert state["rows"][0]["resultCommandIds"][5] == 0x3002

        edit = {"id": 0x20, "results": [{"partner": 5, "resultCommandId": 0xBEEF}]}
        saved = request_json(session.url + "api/mix-table/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["resultCommandIds"][5] == 0xBEEF

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == apply_edits(source, [edit])
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert session.wait_closed()
