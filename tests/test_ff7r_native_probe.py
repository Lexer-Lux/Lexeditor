import struct

import pytest

from games.ff7r.native_probe import PEFormatError, probe_bytes


def fixture_pe(*, with_pdata=True, with_inbound_caller=False):
    data = bytearray(0x600)
    data[:2] = b"MZ"
    pe = 0x80
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe:pe + 4] = b"PE\0\0"
    coff = pe + 4
    struct.pack_into("<H", data, coff + 0, 0x8664)  # AMD64
    struct.pack_into("<H", data, coff + 2, 3 if with_pdata else 2)
    struct.pack_into("<I", data, coff + 4, 0x12345678)
    struct.pack_into("<H", data, coff + 16, 0xF0)
    optional = coff + 20
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<Q", data, optional + 24, 0x140000000)
    struct.pack_into("<I", data, optional + 108, 16)  # NumberOfRvaAndSizes
    if with_pdata:
        exception = optional + 112 + 3 * 8
        exception_size = 36 if with_inbound_caller else 24
        struct.pack_into("<II", data, exception, 0x3000, exception_size)

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
    if with_pdata:
        section(2, ".pdata", 0x3000, 0x500, 0x40)
        struct.pack_into("<III", data, 0x500, 0x1010, 0x1020, 0x3030)
        struct.pack_into("<III", data, 0x50C, 0x1040, 0x1050, 0x3040)
        if with_inbound_caller:
            struct.pack_into("<III", data, 0x518, 0x1060, 0x1070, 0x3050)

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
    # End the first unwind-described function with a direct call to the second
    # unwind-described function. The probe should expose this as a conservative
    # next-hop code reference.
    call_rva = 0x101B
    data[0x21B:0x220] = b"\xE8" + struct.pack("<i", 0x1040 - (call_rva + 5))
    if with_inbound_caller:
        # A third exact .pdata function directly calls the reflected-string owner.
        caller_rva = 0x1060
        data[0x260:0x265] = b"\xE8" + struct.pack("<i", 0x1010 - (caller_rva + 5))
    return bytes(data)


def test_probe_maps_pdata_function_ranges_and_byte_windows():
    result = probe_bytes(fixture_pe(), needles=["NaviMap", "FastForward"])
    assert result["machine"] == 0x8664
    assert result["machineHex"] == "0x8664"
    assert result["timestamp"] == 0x12345678
    assert result["timestampHex"] == "0x12345678"
    assert result["exceptionDirectory"] == {
        "rva": 0x3000,
        "size": 24,
        "runtimeFunctionCount": 2,
    }

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
    assert xref["candidateFunctionEndRva"] == 0x1020
    assert xref["candidateFunctionEndVa"] == 0x140001020
    assert xref["candidateFunctionSource"] == "pdata"
    assert xref["candidateFunctionUnwindInfoRva"] == 0x3030
    assert xref["candidateFunctionUnwindInfoVa"] == 0x140003030

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
    assert function["byteCount"] == 16
    function_bytes = bytes.fromhex(function["hex"])
    assert function_bytes[:7] == b"\x48\x8D\x0D" + struct.pack("<i", 0x2020 - 0x1017)
    assert function_bytes[7:11] == b"\x48\x83\xEC\x28"

    code_refs = xref["candidateFunctionCodeRefs"]
    assert code_refs["scanStartRva"] == 0x1010
    assert code_refs["scanEndRva"] == 0x1020
    assert code_refs["byteCount"] == 16
    assert code_refs["rangeTruncated"] is False
    assert code_refs["refsTruncated"] is False
    refs = code_refs["refs"]
    assert len(refs) == 1
    ref = refs[0]
    assert {
        key: ref[key]
        for key in (
            "kind", "instructionRva", "instructionVa", "targetRva", "targetVa",
            "targetFunctionRva", "targetFunctionVa", "targetFunctionEndRva",
            "targetFunctionEndVa", "targetFunctionUnwindInfoRva",
            "targetFunctionUnwindInfoVa",
        )
    } == {
        "kind": "call-rel32",
        "instructionRva": 0x101B,
        "instructionVa": 0x14000101B,
        "targetRva": 0x1040,
        "targetVa": 0x140001040,
        "targetFunctionRva": 0x1040,
        "targetFunctionVa": 0x140001040,
        "targetFunctionEndRva": 0x1050,
        "targetFunctionEndVa": 0x140001050,
        "targetFunctionUnwindInfoRva": 0x3040,
        "targetFunctionUnwindInfoVa": 0x140003040,
    }
    assert ref["targetFunctionInboundCodeRefs"]["targetFunctionRva"] == 0x1040
    assert ref["targetFunctionInboundCodeRefs"]["refs"][0]["sourceFunctionRva"] == 0x1010

    assert result["needles"][1]["hits"] == []
    assert any(".pdata" in note for note in result["notes"])
    assert any("code refs" in note for note in result["notes"])
    assert any("Inbound" in note for note in result["notes"])


def test_probe_reports_exact_pdata_inbound_callers_for_string_owner_and_next_hop():
    result = probe_bytes(fixture_pe(with_inbound_caller=True), needles=["NaviMap"])
    assert result["exceptionDirectory"]["runtimeFunctionCount"] == 3
    ascii_hit = next(hit for hit in result["needles"][0]["hits"] if hit["encoding"] == "ascii")
    xref = ascii_hit["leaRipXrefs"][0]

    inbound = xref["candidateFunctionInboundCodeRefs"]
    assert inbound["targetFunctionRva"] == 0x1010
    assert inbound["refsTruncated"] is False
    assert len(inbound["refs"]) == 1
    caller = inbound["refs"][0]
    assert caller["kind"] == "call-rel32"
    assert caller["instructionRva"] == 0x1060
    assert caller["sourceFunctionRva"] == 0x1060
    assert caller["sourceFunctionEndRva"] == 0x1070
    assert caller["sourceFunctionUnwindInfoRva"] == 0x3050
    assert caller["targetRva"] == 0x1010
    assert caller["targetFunctionRva"] == 0x1010

    next_hop = xref["candidateFunctionCodeRefs"]["refs"][0]
    next_hop_inbound = next_hop["targetFunctionInboundCodeRefs"]
    assert next_hop_inbound["targetFunctionRva"] == 0x1040
    assert any(
        ref["sourceFunctionRva"] == 0x1010 and ref["instructionRva"] == 0x101B
        for ref in next_hop_inbound["refs"]
    )


def test_probe_falls_back_to_padding_when_pdata_is_unavailable():
    result = probe_bytes(fixture_pe(with_pdata=False), needles=["NaviMap"])
    assert result["exceptionDirectory"]["runtimeFunctionCount"] == 0
    xref = next(
        hit for hit in result["needles"][0]["hits"] if hit["encoding"] == "ascii"
    )["leaRipXrefs"][0]
    assert xref["candidateFunctionRva"] == 0x1010
    assert xref["candidateFunctionEndRva"] is None
    assert xref["candidateFunctionSource"] == "padding-heuristic"
    assert xref["candidateFunctionUnwindInfoRva"] is None
    assert xref["candidateFunctionCodeRefs"] is None
    assert xref["candidateFunctionInboundCodeRefs"] is None
    assert xref["candidateFunctionBytes"]["byteCount"] == 64


def test_probe_correlates_multiple_string_targets_in_one_text_scan():
    data = bytearray(fixture_pe(with_pdata=False))
    data[0x440:0x440 + len(b"FastForward\0")] = b"FastForward\0"
    data[0x228:0x230] = b"\xCC" * 8
    displacement = 0x2040 - 0x1037
    data[0x230:0x237] = b"\x48\x8D\x15" + struct.pack("<i", displacement)

    result = probe_bytes(bytes(data), needles=["NaviMap", "FastForward"])
    instructions = {}
    for entry in result["needles"]:
        ascii_hit = next(hit for hit in entry["hits"] if hit["encoding"] == "ascii")
        instructions[entry["needle"]] = ascii_hit["leaRipXrefs"][0]["instructionRva"]

    assert instructions == {"NaviMap": 0x1010, "FastForward": 0x1030}


def test_probe_scans_lea_at_last_possible_text_offset():
    data = bytearray(fixture_pe(with_pdata=False))
    instruction_rva = 0x10F9
    displacement = 0x2020 - (instruction_rva + 7)
    data[0x2F9:0x300] = b"\x48\x8D\x0D" + struct.pack("<i", displacement)

    result = probe_bytes(bytes(data), needles=["NaviMap"])
    ascii_hit = next(
        hit for hit in result["needles"][0]["hits"] if hit["encoding"] == "ascii"
    )
    assert any(xref["instructionRva"] == instruction_rva for xref in ascii_hit["leaRipXrefs"])


def test_probe_rejects_non_pe_and_truncated_images():
    with pytest.raises(PEFormatError):
        probe_bytes(b"not a pe", needles=[])

    truncated = bytearray(0x100)
    truncated[:2] = b"MZ"
    struct.pack_into("<I", truncated, 0x3C, 0xF0)
    with pytest.raises(PEFormatError):
        probe_bytes(bytes(truncated), needles=[])
