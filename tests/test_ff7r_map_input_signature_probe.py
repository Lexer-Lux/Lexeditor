from __future__ import annotations

import struct

from games.ff7r.map_input_signature_probe import (
    MAP_CONTROL_SIGNATURE,
    RAW_INPUT_REGISTRATION_SIGNATURE,
    probe_public_map_input_signatures,
)


def _fixture_pe(*, map_control=True, raw_input=True) -> bytes:
    data = bytearray(0x600)
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
    struct.pack_into("<II", data, exception, 0x3000, 24)

    sections = optional + 0xF0

    def section(index, name, rva, raw_offset, size):
        offset = sections + index * 40
        data[offset:offset + 8] = name.encode("ascii").ljust(8, b"\0")
        struct.pack_into("<I", data, offset + 8, size)
        struct.pack_into("<I", data, offset + 12, rva)
        struct.pack_into("<I", data, offset + 16, size)
        struct.pack_into("<I", data, offset + 20, raw_offset)

    section(0, ".text", 0x1000, 0x200, 0x200)
    section(1, ".pdata", 0x3000, 0x500, 0x40)
    struct.pack_into("<III", data, 0x500, 0x1010, 0x1080, 0x3030)
    struct.pack_into("<III", data, 0x50C, 0x1100, 0x1180, 0x3040)

    if map_control:
        start = 0x220
        data[start:start + len(MAP_CONTROL_SIGNATURE)] = MAP_CONTROL_SIGNATURE
    if raw_input:
        start = 0x310
        data[start:start + len(RAW_INPUT_REGISTRATION_SIGNATURE)] = RAW_INPUT_REGISTRATION_SIGNATURE
    return bytes(data)


def test_public_map_and_raw_input_signatures_are_found_but_rejected_as_map_button_authority(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(_fixture_pe())

    result = probe_public_map_input_signatures(exe)

    assert result["scanError"] == ""
    assert result["mapControl"]["matchCount"] == 1
    assert result["mapControl"]["matches"][0]["rva"] == 0x1020
    assert result["mapControl"]["matches"][0]["pdataFunctionRva"] == 0x1010
    assert result["mapControl"]["classification"] == "full-screen-map-controller"
    assert result["mapControl"]["mapButtonAuthority"] is False
    assert "MapHook.cpp" in result["mapControl"]["provenance"]

    assert result["rawInputRegistration"]["matchCount"] == 1
    assert result["rawInputRegistration"]["matches"][0]["rva"] == 0x1110
    assert result["rawInputRegistration"]["matches"][0]["pdataFunctionRva"] == 0x1100
    assert result["rawInputRegistration"]["classification"] == "raw-input-device-registration"
    assert result["rawInputRegistration"]["mapButtonAuthority"] is False
    assert "InputManager.cpp" in result["rawInputRegistration"]["provenance"]


def test_each_public_signature_is_independently_optional(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(_fixture_pe(map_control=True, raw_input=False))
    result = probe_public_map_input_signatures(exe)
    assert result["mapControl"]["matchCount"] == 1
    assert result["rawInputRegistration"]["matchCount"] == 0
    assert result["rawInputRegistration"]["mapButtonAuthority"] is False

    exe.write_bytes(_fixture_pe(map_control=False, raw_input=True))
    result = probe_public_map_input_signatures(exe)
    assert result["mapControl"]["matchCount"] == 0
    assert result["rawInputRegistration"]["matchCount"] == 1
    assert result["mapControl"]["mapButtonAuthority"] is False


def test_invalid_executable_fails_closed_without_changing_semantic_classification(tmp_path):
    exe = tmp_path / "ff7remake_.exe"
    exe.write_bytes(b"not a PE")

    result = probe_public_map_input_signatures(exe)

    assert result["scanError"]
    assert result["mapControl"]["matchCount"] == 0
    assert result["mapControl"]["classification"] == "full-screen-map-controller"
    assert result["mapControl"]["mapButtonAuthority"] is False
    assert result["rawInputRegistration"]["matchCount"] == 0
    assert result["rawInputRegistration"]["classification"] == "raw-input-device-registration"
    assert result["rawInputRegistration"]["mapButtonAuthority"] is False
