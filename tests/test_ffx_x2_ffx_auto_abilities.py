from __future__ import annotations

import hashlib
from pathlib import Path
import struct

import pytest

from games.ffx_x2.ffx_auto_abilities import (
    ARCHIVE_PATH, ELEMENT_MASK, FFXAutoAbilityError, RECORD_SIZE,
    apply_edits, parse_auto_abilities, payload,
)
from games.ffx_x2.plugin import FFXX2Session, _write_fixture_vbf
from service_session import request_json


def _record(*, strike: int, absorb: int, immune: int, resist: int, weak: int,
            fill: int = 0xCC) -> bytes:
    raw = bytearray([fill] * RECORD_SIZE)
    raw[0x10] = 0xA7  # SOS byte remains opaque/read-only.
    raw[0x11] = strike
    raw[0x12] = absorb
    raw[0x13] = immune
    raw[0x14] = resist
    raw[0x15] = weak
    raw[0x68] = 0xD3  # Deliberately preserve a field whose semantics are not exposed here.
    return bytes(raw)


def _table(records: list[bytes], min_index: int = 0, trailing: bytes = b"AUTO-ABILITY-STRINGS") -> bytes:
    header = bytearray(0x14)
    header[:8] = b"AABILITY"
    struct.pack_into(
        "<HHHH", header, 0x08,
        min_index, min_index + len(records) - 1,
        RECORD_SIZE, RECORD_SIZE * len(records),
    )
    header[0x10:0x14] = b"KEEP"
    return bytes(header) + b"".join(records) + trailing


def test_ffx_auto_ability_parses_only_known_low_element_bits():
    data = _table([
        _record(strike=0xA1, absorb=0x42, immune=0xE4, resist=0x88, weak=0xD0),
    ], min_index=7)
    row = parse_auto_abilities(data)[0]
    assert row.record_id == 7
    assert (row.strike, row.absorb, row.immune, row.resist, row.weak) == (1, 2, 4, 8, 16)
    assert row.unknown_bits == (0xA0, 0x40, 0xE0, 0x80, 0xC0)

    state = payload(data)
    assert state["recordSize"] == 0x6C
    assert state["elementMask"] == ELEMENT_MASK
    assert state["rows"][0]["abilityId"] == 0x8000
    assert [element["label"] for element in state["elements"]] == ["Fire", "Ice", "Thunder", "Water", "Holy"]


def test_ffx_auto_ability_edit_preserves_unknown_bits_and_every_other_byte():
    original = _table([
        _record(strike=0xA1, absorb=0x42, immune=0xE4, resist=0x88, weak=0xD0, fill=0x5A),
        _record(strike=0x61, absorb=0x82, immune=0xA4, resist=0xC8, weak=0xF0, fill=0xA5),
    ], min_index=4, trailing=b"opaque-auto-ability-strings")

    edited = apply_edits(original, [{
        "id": 4,
        "strike": 0x1F,
        "absorb": 0,
        "immune": 0x03,
        "resist": 0x14,
        "weak": 0x0A,
    }])

    first = parse_auto_abilities(edited)[0]
    assert (first.strike, first.absorb, first.immune, first.resist, first.weak) == (0x1F, 0, 3, 0x14, 0x0A)
    record_start = 0x14
    for field_offset in range(0x11, 0x16):
        assert edited[record_start + field_offset] & 0xE0 == original[record_start + field_offset] & 0xE0

    changed = {index for index, (before, after) in enumerate(zip(original, edited)) if before != after}
    assert changed <= {record_start + offset for offset in range(0x11, 0x16)}
    assert edited[record_start + 0x10] == original[record_start + 0x10]
    assert edited[record_start + 0x68] == original[record_start + 0x68]
    assert edited[0x14 + RECORD_SIZE:] == original[0x14 + RECORD_SIZE:]
    assert edited.endswith(b"opaque-auto-ability-strings")


def test_ffx_auto_ability_rejects_wrong_size_invalid_masks_duplicate_and_extra_fields():
    valid = _table([_record(strike=1, absorb=2, immune=4, resist=8, weak=16)])

    wrong = bytearray(valid)
    struct.pack_into("<HH", wrong, 0x0C, 0x6B, 0x6B)
    with pytest.raises(FFXAutoAbilityError, match="record size"):
        payload(bytes(wrong))

    with pytest.raises(FFXAutoAbilityError, match="between 0 and 31"):
        apply_edits(valid, [{"id": 0, "strike": 32, "absorb": 0, "immune": 0, "resist": 0, "weak": 0}])
    with pytest.raises(FFXAutoAbilityError, match="Duplicate"):
        apply_edits(valid, [
            {"id": 0, "strike": 1, "absorb": 2, "immune": 4, "resist": 8, "weak": 16},
            {"id": 0, "strike": 0, "absorb": 0, "immune": 0, "resist": 0, "weak": 0},
        ])
    with pytest.raises(FFXAutoAbilityError, match="only id"):
        apply_edits(valid, [{
            "id": 0, "strike": 1, "absorb": 2, "immune": 4, "resist": 8, "weak": 16,
            "icon": 7,
        }])


def test_ffx_auto_ability_managed_save_is_canonical_and_vbf_immutable(tmp_path: Path):
    source = _table([
        _record(strike=0xA1, absorb=0x42, immune=0xE4, resist=0x88, weak=0xD0, fill=0xA5),
        _record(strike=0x61, absorb=0x82, immune=0xA4, resist=0xC8, weak=0xF0, fill=0x5A),
    ], min_index=0x30, trailing=b"opaque-live-strings")
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
        assert "ffx-auto-ability-elements-editor" in identity["capabilities"]

        state = request_json(session.url + "api/ffx-auto-abilities")
        assert state["game"] == "x"
        assert state["source"] == "archive"
        assert state["archivePath"] == ARCHIVE_PATH
        assert state["recordSize"] == RECORD_SIZE
        assert state["rows"][0]["strike"] == 1
        assert state["rows"][0]["unknownBits"]["strike"] == 0xA0

        edit = {"id": 0x30, "strike": 0x1F, "absorb": 0, "immune": 3, "resist": 0x14, "weak": 0x0A}
        expected = apply_edits(source, [edit])
        saved = request_json(session.url + "api/ffx-auto-abilities/save", {
            "headerMd5": state["headerMd5"],
            "baselineSha256": state["baselineSha256"],
            "edits": [edit],
        })
        assert saved["saved"] == 1
        assert saved["source"] == "project"
        assert saved["rows"][0]["strike"] == 0x1F

        target = project_root / "efl" / "x" / Path(*ARCHIVE_PATH.split("/"))
        assert target.read_bytes() == expected
        assert not (project_root / "efl" / "x" / Path(*raw_archive_path.split("/"))).exists()

    assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_hash
    assert session.wait_closed()
