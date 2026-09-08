from __future__ import annotations

import struct

from games.ff7r.movement_signature_probe import (
    JOYSTICK_MOVEMENT_SIGNATURE,
    probe_public_joystick_movement_signature,
)
from games.ff7r.sprint_probe import assess_sprint_evidence


def _fixture_pe(*, include_signature: bool = True) -> bytes:
    data = bytearray(0x500)
    data[:2] = b"MZ"
    pe = 0x80
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    struct.pack_into("<H", data, coff + 0, 0x8664)
    struct.pack_into("<H", data, coff + 2, 2)
    struct.pack_into("<I", data, coff + 4, 0x12345678)
    struct.pack_into("<H", data, coff + 16, 0xF0)
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<I", data, optional + 108, 16)
    exception = optional + 112 + 3 * 8
    struct.pack_into("<II", data, exception, 0x3000, 12)

    sections = optional + 0xF0

    def section(index: int, name: str, rva: int, raw_offset: int, size: int) -> None:
        offset = sections + index * 40
        data[offset:offset + 8] = name.encode("ascii").ljust(8, b"\0")
        struct.pack_into("<I", data, offset + 8, size)
        struct.pack_into("<I", data, offset + 12, rva)
        struct.pack_into("<I", data, offset + 16, size)
        struct.pack_into("<I", data, offset + 20, raw_offset)

    section(0, ".text", 0x1000, 0x200, 0x100)
    section(1, ".pdata", 0x3000, 0x400, 0x40)
    struct.pack_into("<III", data, 0x400, 0x1010, 0x1060, 0x3030)

    if include_signature:
        start = 0x220
        data[start:start + len(JOYSTICK_MOVEMENT_SIGNATURE)] = JOYSTICK_MOVEMENT_SIGNATURE
    return bytes(data)


def test_public_joystick_signature_is_found_but_never_classified_as_sprint_speed(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(_fixture_pe())

    result = probe_public_joystick_movement_signature(exe)

    assert result["matchCount"] == 1
    assert result["matches"] == [{
        "fileOffset": 0x220,
        "rva": 0x1020,
        "va": 0x140001020,
        "pdataFunctionRva": 0x1010,
        "pdataFunctionEndRva": 0x1060,
    }]
    assert result["classification"] == "raw-joystick-input-post-fetch"
    assert result["sprintSpeedAuthority"] is False
    assert "TheUnlocked/ff7r-kbm-hook" in result["provenance"]


def test_missing_public_joystick_signature_is_reported_without_guessing(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(_fixture_pe(include_signature=False))

    result = probe_public_joystick_movement_signature(exe)

    assert result["matchCount"] == 0
    assert result["matches"] == []
    assert result["scanError"] == ""
    assert result["sprintSpeedAuthority"] is False


def test_bad_executable_fails_closed_as_input_reference_only(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(b"not a PE")

    result = probe_public_joystick_movement_signature(exe)

    assert result["matchCount"] == 0
    assert result["scanError"]
    assert result["classification"] == "raw-joystick-input-post-fetch"
    assert result["sprintSpeedAuthority"] is False


def test_better_sprint_assessment_exposes_signature_but_rejects_it_as_authority():
    movement = {
        "matchCount": 1,
        "matches": [{"rva": 0x1020}],
        "classification": "raw-joystick-input-post-fetch",
        "sprintSpeedAuthority": False,
    }

    result = assess_sprint_evidence(
        {"needles": []},
        [],
        movement_signature=movement,
    )

    assert result["publicJoystickMovementSignaturePresent"] is True
    assert result["publicJoystickMovementRejectedAsSprintAuthority"] is True
    assert result["publicJoystickMovementSignature"] == movement
    assert result["implementationReady"] is False
    assert "authoritative-player-sprint-speed-path-unvalidated" in result["blockers"]
    assert any("raw joystick" in note for note in result["notes"])
