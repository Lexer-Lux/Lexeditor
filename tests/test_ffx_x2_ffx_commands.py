from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from games.ffx_x2.ffx_commands import (
    ARCHIVE_PATH, FFXCommandError, apply_edits, parse_commands, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(anim1: int, anim2: int, fill: int = 0xCC) -> bytes:
    raw = bytearray([fill] * 0x60)
    struct.pack_into("<HH", raw, 0x10, anim1, anim2)
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 0, trailing: bytes = b"STRINGS") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"COMMAND!"
    struct.pack_into("<HHHH", header, 0x08, min_index, min_index + len(records) - 1, 0x60, 0x60 * len(records))
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_ffx_command_parses_only_proved_animation_fields():
    data = _table([_record(0x1234, 0x5678)], min_index=7, trailing=b"opaque-strings")
    row = parse_commands(data)[0]
    assert row.record_id == 7
    assert (row.animation_1, row.animation_2) == (0x1234, 0x5678)
    state = payload(data)
    assert state["recordSize"] == 0x60
    assert state["minIndex"] == 7
    assert state["maxIndex"] == 7


def test_ffx_command_edit_changes_only_animation_ids():
    original = _table([
        _record(0x1111, 0x2222, fill=0xA5),
        _record(0x3333, 0x4444, fill=0x5A),
    ], min_index=4, trailing=b"opaque-command-strings")
    edited = apply_edits(original, [{"id": 4, "animation1": 0xBEEF, "animation2": 0xCAFE}])
    rows = parse_commands(edited)
    assert (rows[0].animation_1, rows[0].animation_2) == (0xBEEF, 0xCAFE)
    assert (rows[1].animation_1, rows[1].animation_2) == (0x3333, 0x4444)

    record_start = 0x14
    assert edited[:record_start + 0x10] == original[:record_start + 0x10]
    assert edited[record_start + 0x14:] == original[record_start + 0x14:]
    assert edited.endswith(b"opaque-command-strings")


def test_ffx_command_rejects_wrong_record_size_duplicate_and_extra_fields():
    wrong = bytearray(_table([_record(1, 2)]))
    struct.pack_into("<HH", wrong, 0x0C, 0x5C, 0x5C)
    with pytest.raises(FFXCommandError, match="record size"):
        parse_commands(bytes(wrong))

    valid = _table([_record(1, 2)])
    with pytest.raises(FFXCommandError, match="Duplicate"):
        apply_edits(valid, [
            {"id": 0, "animation1": 1, "animation2": 2},
            {"id": 0, "animation1": 3, "animation2": 4},
        ])
    with pytest.raises(FFXCommandError, match="only id"):
        apply_edits(valid, [{"id": 0, "animation1": 1, "animation2": 2, "power": 255}])


def test_ffx_command_managed_service_saves_project_only(tmp_path: Path):
    source = _table([
        _record(0x1111, 0x2222, fill=0xA5),
        _record(0x3333, 0x4444, fill=0x5A),
    ], min_index=0x20, trailing=b"opaque-command-strings")
    raw_archive_path = ARCHIVE_PATH.removeprefix("FFX_Data/")
    game_root = tmp_path / "game"
    project_root = tmp_path / "project"
    theme_cache = tmp_path / "theme"
    x_archive = game_root / "data" / "FFX_Data.vbf"
    _write_fixture_vbf(x_archive, [(raw_archive_path, source)])
    archive_hash = hashlib.sha256(x_archive.read_bytes()).hexdigest()

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(project_root),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(theme_cache),
    }) as session:
        state = request_json(session.url + "api/ffx-commands")
        assert state["game"] == "x"
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["rows"][0]["animation1"] == 0x1111

        edit = {"id": 0x20, "animation1": 0xBEEF, "animation2": 0xCAFE}
        expected = apply_edits(source, [edit])
        saved = request_json(session.url + "api/ffx-commands/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert (saved["rows"][0]["animation1"], saved["rows"][0]["animation2"]) == (0xBEEF, 0xCAFE)

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == expected
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert hashlib.sha256(x_archive.read_bytes()).hexdigest() == archive_hash
    assert session.wait_closed()
