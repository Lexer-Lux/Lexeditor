import struct

import pytest

from games.ff7r.native_probe import PEFormatError, probe_bytes


def fixture_pe():
    data = bytearray(0x500)
    data[:2] = b"MZ"
    pe = 0x80
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    struct.pack_into("<H", data, coff + 0, 0x8664)  # AMD64
    struct.pack_into("<H", data, coff + 2, 2)
    struct.pack_into("<I", data, coff + 4, 0x12345678)
    struct.pack_into("<H", data, coff + 16, 0xF0)
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)

    sections = optional + 0xF0

    def section(index, name, rva, raw_offset, size):
        offset = sections + index * 40
        data[offset:offset + 8] = name.encode("ascii").ljust(8, b"\0")
        struct.pack_into("<I", data, offset + 8, size)
        struct.pack_into("<I", data, offset + 12, rva)
        struct.pack_into("<I", data, offset + 16, size)
        struct.pack_into("<I", data, offset + 20, raw_offset)

    section(0, ".text", 0x1000, 0x200, 0x100)
    section(1, ".rdata", 0x2000, 0x400, 0x100)

    # String at .rdata+0x20 => RVA 0x2020.
    data[0x420:0x420 + len(b"NaviMap\0")] = b"NaviMap\0"

    # Current-build probe only claims this common RIP-relative LEA shape.
    # LEA starts at RVA 0x1010 and ends at 0x1017.
    data[0x208:0x210] = b"\xCC" * 8
    displacement = 0x2020 - 0x1017
    data[0x210:0x217] = b"\x48\x8D\x0D" + struct.pack("<i", displacement)
    # Give the candidate function a recognizable trailing byte sequence so the
    # raw function window proves it is reading the executable bytes, not merely
    # echoing the string/xref metadata.
    data[0x217:0x21B] = b"\x48\x83\xEC\x28"
    return bytes(data)


def test_probe_maps_current_pe_timestamp_strings_xrefs_and_byte_windows():
    result = probe_bytes(fixture_pe(), needles=["NaviMap", "FastForward"])
    assert result["timestamp"] == 0x12345678
    assert result["timestampHex"] == "0x12345678"
    navimap = result["needles"][0]
    assert navimap["needle"] == "NaviMap"
    ascii_hit = next(hit for hit in navimap["hits"] if hit["encoding"] == "ascii")
    assert ascii_hit["rva"] == 0x2020
    assert ascii_hit["va"] == 0x140002020
    assert len(ascii_hit["leaRipXrefs"]) == 1
    xref = ascii_hit["leaRipXrefs"][0]
    assert xref["instructionRva"] == 0x1010
    assert xref["instructionVa"] == 0x140001010
    assert xref["candidateFunctionRva"] == 0x1010
    assert xref["candidateFunctionVa"] == 0x140001010

    context = xref["xrefContext"]
    assert context["section"] == ".text"
    assert context["startRva"] == 0x1000
    assert context["focusRva"] == 0x1010
    assert context["focusOffset"] == 16
    assert context["byteCount"] == 48
    context_bytes = bytes.fromhex(context["hex"])
    assert context_bytes[8:16] == b"\xCC" * 8
    assert context_bytes[16:23] == b"\x48\x8D\x0D" + struct.pack("<i", 0x2020 - 0x1017)

    function = xref["candidateFunctionBytes"]
    assert function["startRva"] == 0x1010
    assert function["focusOffset"] == 0
    assert function["byteCount"] == 64
    function_bytes = bytes.fromhex(function["hex"])
    assert function_bytes[:7] == b"\x48\x8D\x0D" + struct.pack("<i", 0x2020 - 0x1017)
    assert function_bytes[7:11] == b"\x48\x83\xEC\x28"

    assert result["needles"][1]["hits"] == []
    assert any("byte windows" in note for note in result["notes"])


def test_probe_rejects_non_pe_and_truncated_images():
    with pytest.raises(PEFormatError):
        probe_bytes(b"not a pe", needles=[])

    truncated = bytearray(0x100)
    truncated[:2] = b"MZ"
    struct.pack_into("<I", truncated, 0x3C, 0xF0)
    with pytest.raises(PEFormatError):
        probe_bytes(bytes(truncated), needles=[])
