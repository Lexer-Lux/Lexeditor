from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from games.ffx_x2.ffx_player_stats import (
    ARCHIVE_PATH, FFXPlayerStatsError, RECORD_SIZE, apply_edits, parse_player_stats, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(*, hp: int, mp: int, stats: tuple[int, ...], fill: int = 0xCC) -> bytes:
    assert len(stats) == 8
    raw = bytearray([fill] * RECORD_SIZE)
    raw[0:4] = b"NAME"  # text metadata remains opaque/read-only
    struct.pack_into("<II", raw, 0x04, hp, mp)
    raw[0x0C:0x14] = bytes(stats)
    raw[0x14:0x18] = b"AP??"  # first disputed/later field stays opaque
    raw[0x90:0x94] = b"TAIL"
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 0, trailing: bytes = b"PLAYER-STRINGS") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"PLYSAVE!"
    struct.pack_into(
        "<HHHH", header, 0x08,
        min_index, min_index + len(records) - 1,
        RECORD_SIZE, RECORD_SIZE * len(records),
    )
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def _edit(record_id: int, hp: int = 9999, mp: int = 999) -> dict:
    return {
        "id": record_id,
        "baseHp": hp,
        "baseMp": mp,
        "strength": 11,
        "defense": 12,
        "magic": 13,
        "magicDefense": 14,
        "agility": 15,
        "luck": 16,
        "evasion": 17,
        "accuracy": 18,
    }


def test_ffx_player_stats_parses_only_independently_agreed_base_prefix():
    data = _table([
        _record(hp=520, mp=12, stats=(5, 6, 7, 8, 9, 10, 11, 12)),
    ], min_index=3)
    row = parse_player_stats(data)[0]
    assert row.record_id == 3
    assert row.base_hp == 520
    assert row.base_mp == 12
    assert (row.strength, row.defense, row.magic, row.magic_defense) == (5, 6, 7, 8)
    assert (row.agility, row.luck, row.evasion, row.accuracy) == (9, 10, 11, 12)
    state = payload(data)
    assert state["recordSize"] == 0x94
    assert state["rows"][0]["baseHp"] == 520
    assert "currentHp" not in state["rows"][0]
    assert "totalAp" not in state["rows"][0]


def test_ffx_player_stats_edit_changes_only_offsets_04_through_13_of_selected_record():
    original = _table([
        _record(hp=520, mp=12, stats=(5, 6, 7, 8, 9, 10, 11, 12), fill=0xA5),
        _record(hp=1000, mp=100, stats=(20, 21, 22, 23, 24, 25, 26, 27), fill=0x5A),
    ], min_index=4, trailing=b"opaque-player-tail")
    edited = apply_edits(original, [_edit(4)])
    rows = parse_player_stats(edited)
    assert rows[0].base_hp == 9999
    assert rows[0].base_mp == 999
    assert (rows[0].strength, rows[0].accuracy) == (11, 18)
    assert rows[1].base_hp == 1000

    record_start = 0x14
    changed = {index for index, (before, after) in enumerate(zip(original, edited)) if before != after}
    assert changed <= {record_start + offset for offset in range(0x04, 0x14)}
    assert edited[record_start:record_start + 0x04] == original[record_start:record_start + 0x04]
    assert edited[record_start + 0x14:] == original[record_start + 0x14:]
    assert edited.endswith(b"opaque-player-tail")


def test_ffx_player_stats_rejects_wrong_size_ranges_duplicates_and_extra_fields():
    valid = _table([_record(hp=1, mp=2, stats=(1, 2, 3, 4, 5, 6, 7, 8))])
    wrong = bytearray(valid)
    struct.pack_into("<HH", wrong, 0x0C, 0x93, 0x93)
    with pytest.raises(FFXPlayerStatsError, match="record size"):
        payload(bytes(wrong))

    bad_stat = _edit(0)
    bad_stat["strength"] = 256
    with pytest.raises(FFXPlayerStatsError, match="Strength must be between 0 and 255"):
        apply_edits(valid, [bad_stat])

    bad_hp = _edit(0)
    bad_hp["baseHp"] = 0x100000000
    with pytest.raises(FFXPlayerStatsError, match="Base HP must be between"):
        apply_edits(valid, [bad_hp])

    with pytest.raises(FFXPlayerStatsError, match="Duplicate"):
        apply_edits(valid, [_edit(0), _edit(0, hp=1, mp=2)])

    extra = _edit(0)
    extra["currentHp"] = 1234
    with pytest.raises(FFXPlayerStatsError, match="contain only"):
        apply_edits(valid, [extra])


def test_ffx_player_stats_managed_save_is_project_only_and_vbf_immutable(tmp_path: Path):
    source = _table([
        _record(hp=520, mp=12, stats=(5, 6, 7, 8, 9, 10, 11, 12), fill=0xA5),
        _record(hp=1000, mp=100, stats=(20, 21, 22, 23, 24, 25, 26, 27), fill=0x5A),
    ], min_index=0x10, trailing=b"opaque-live-player-tail")
    raw_archive_path = ARCHIVE_PATH.removeprefix("FFX_Data/")
    game_root = tmp_path / "game"
    project_root = tmp_path / "project"
    theme_cache = tmp_path / "theme"
    archive = game_root / "data" / "FFX_Data.vbf"
    _write_fixture_vbf(archive, [(raw_archive_path, source)])
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()

    with FFXX2Session({
        "LEXEDITOR_FFX_X2_ROOT": str(game_root),
        "LEXEDITOR_FFX_X2_PROJECT": str(project_root),
        "LEXEDITOR_FFX_X2_THEME_CACHE": str(theme_cache),
    }) as session:
        identity = request_json(session.url + "api/plugin")
        assert "ffx-player-base-stats-editor" in identity["capabilities"]

        state = request_json(session.url + "api/ffx-player-stats")
        assert state["game"] == "x"
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["recordSize"] == RECORD_SIZE
        assert state["rows"][0]["baseHp"] == 520

        edit = _edit(0x10)
        expected = apply_edits(source, [edit])
        saved = request_json(session.url + "api/ffx-player-stats/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["baseHp"] == 9999

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == expected
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_hash
    assert session.wait_closed()
