from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from games.ffx_x2.ffx_commands import (
    ARCHIVE_PATH, TABLES, FFXCommandError, apply_edits, apply_table_edits,
    parse_commands, payload, payload_for, table_spec,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(anim1: int, anim2: int, record_size: int = 0x60, fill: int = 0xCC) -> bytes:
    raw = bytearray([fill] * record_size)
    struct.pack_into("<HH", raw, 0x10, anim1, anim2)
    return bytes(raw)


def _table(records: list[bytes], record_size: int = 0x60,
           min_index: int = 0, trailing: bytes = b"STRINGS") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"COMMAND!"
    struct.pack_into(
        "<HHHH", header, 0x08,
        min_index, min_index + len(records) - 1,
        record_size, record_size * len(records),
    )
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_ffx_command_backward_compatibility_parses_only_proved_animation_fields():
    data = _table([_record(0x1234, 0x5678)], min_index=7, trailing=b"opaque-strings")
    row = parse_commands(data)[0]
    assert row.record_id == 7
    assert (row.animation_1, row.animation_2) == (0x1234, 0x5678)
    state = payload(data)
    assert state["table"] == "command"
    assert state["recordSize"] == 0x60
    assert state["minIndex"] == 7
    assert state["maxIndex"] == 7


@pytest.mark.parametrize("key,record_size", [
    ("command", 0x60),
    ("item", 0x60),
    ("monmagic1", 0x5C),
    ("monmagic2", 0x5C),
])
def test_ffx_animation_family_uses_proved_record_sizes_and_offsets(key: str, record_size: int):
    data = _table([
        _record(0x1234, 0x5678, record_size),
        _record(0x9ABC, 0xDEF0, record_size),
    ], record_size=record_size, min_index=0x20, trailing=b"opaque-strings")
    state = payload_for(data, key)
    assert state["table"] == key
    assert state["label"] == table_spec(key).label
    assert state["recordSize"] == record_size
    assert [(row["animation1"], row["animation2"]) for row in state["rows"]] == [
        (0x1234, 0x5678), (0x9ABC, 0xDEF0),
    ]


def test_ffx_animation_edit_changes_only_animation_ids():
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


@pytest.mark.parametrize("key,record_size", [("item", 0x60), ("monmagic1", 0x5C), ("monmagic2", 0x5C)])
def test_ffx_additional_animation_tables_preserve_all_other_bytes(key: str, record_size: int):
    original = _table([
        _record(0x1111, 0x2222, record_size, fill=0xA5),
        _record(0x3333, 0x4444, record_size, fill=0x5A),
    ], record_size=record_size, min_index=0x40, trailing=b"opaque-family-strings")
    edited = apply_table_edits(
        original, [{"id": 0x41, "animation1": 0xBEEF, "animation2": 0xCAFE}], key,
    )
    changed = {index for index, (before, after) in enumerate(zip(original, edited)) if before != after}
    record_start = 0x14 + record_size
    assert changed <= {
        record_start + 0x10, record_start + 0x11,
        record_start + 0x12, record_start + 0x13,
    }
    assert edited.endswith(b"opaque-family-strings")


def test_ffx_animation_family_rejects_wrong_record_size_duplicate_extra_fields_and_unknown_table():
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
    with pytest.raises(FFXCommandError, match="ability table"):
        table_spec("launcher")

    monmagic_wrong = _table([_record(1, 2)], record_size=0x60)
    with pytest.raises(FFXCommandError, match="0x5C-byte layout"):
        payload_for(monmagic_wrong, "monmagic1")


def test_ffx_animation_family_managed_service_saves_each_table_project_only(tmp_path: Path):
    game_root = tmp_path / "game"
    project_root = tmp_path / "project"
    theme_cache = tmp_path / "theme"
    sources = {}
    vbf_files = []
    for ordinal, (key, spec) in enumerate(TABLES.items()):
        source = _table([
            _record(0x1100 + ordinal, 0x2200 + ordinal, spec.record_size, fill=0xA0 + ordinal),
            _record(0x3300 + ordinal, 0x4400 + ordinal, spec.record_size, fill=0x50 + ordinal),
        ], record_size=spec.record_size, min_index=0x20 + ordinal * 0x10,
           trailing=f"opaque-{key}-strings".encode("ascii"))
        sources[key] = source
        vbf_files.append((spec.archive_path.removeprefix("FFX_Data/"), source))

    x_archive = game_root / "data" / "FFX_Data.vbf"
    _write_fixture_vbf(x_archive, vbf_files)
    archive_hash = hashlib.sha256(x_archive.read_bytes()).hexdigest()

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(project_root),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(theme_cache),
    }) as session:
        identity = request_json(session.url + "api/plugin")
        assert "ffx-command-animation-editor" in identity["capabilities"]
        assert "ffx-ability-animation-editor" in identity["capabilities"]

        for ordinal, (key, spec) in enumerate(TABLES.items()):
            state = request_json(session.url + f"api/ffx-commands?table={key}")
            assert state["game"] == "x"
            assert state["table"] == key
            assert state["source"] == "archive"
            assert state["archivePath"] == spec.archive_path
            assert state["recordSize"] == spec.record_size

            record_id = 0x20 + ordinal * 0x10
            edit = {"id": record_id, "animation1": 0xBEEF, "animation2": 0xCAFE}
            expected = apply_table_edits(sources[key], [edit], key)
            saved = request_json(session.url + "api/ffx-commands/save", {
                "table": key,
                "headerMd5": state["headerMd5"],
                "baselineSha256": state["baselineSha256"],
                "edits": [edit],
            })
            assert saved["saved"] == 1
            assert saved["table"] == key
            assert saved["source"] == "project"
            assert (saved["rows"][0]["animation1"], saved["rows"][0]["animation2"]) == (0xBEEF, 0xCAFE)

            target = project_root / "efl" / "x" / Path(*spec.archive_path.split("/"))
            assert target.read_bytes() == expected
            raw_archive_path = spec.archive_path.removeprefix("FFX_Data/")
            assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert hashlib.sha256(x_archive.read_bytes()).hexdigest() == archive_hash
    assert session.wait_closed()


def test_ffx_command_default_route_still_targets_command_bin(tmp_path: Path):
    source = _table([_record(0x1111, 0x2222)], min_index=0x20)
    raw_archive_path = ARCHIVE_PATH.removeprefix("FFX_Data/")
    game_root = tmp_path / "game"
    _write_fixture_vbf(game_root / "data" / "FFX_Data.vbf", [(raw_archive_path, source)])

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(tmp_path / "project"),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(tmp_path / "theme"),
    }) as session:
        state = request_json(session.url + "api/ffx-commands")
        assert state["table"] == "command"
        assert state["archivePath"] == ARCHIVE_PATH

    assert session.wait_closed()
