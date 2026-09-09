import struct

from games.ff7r.dog_whistle_commit_probe import (
    _caller_anchor_map,
    _function_string_refs,
    analyze_item_commit_caller_strings,
)
from games.ff7r.native_probe import PEImage, RuntimeFunction, Section


def _image_with_string_refs(*, callers=(0x1010,)):
    data = bytearray(0x400)
    text = Section(".text", 0x1000, 0x200, 0x000, 0x200)
    rdata = Section(".rdata", 0x2000, 0x200, 0x200, 0x200)
    runtime_functions = []

    strings = {
        0x2000: b"CommitBattleCommandItem\0",
        0x2040: b"DebugOnlyName\0",
        0x2080: "SelectItemCommand".encode("utf-16-le") + b"\0\0",
    }
    for rva, raw in strings.items():
        offset = rdata.raw_offset + (rva - rdata.virtual_address)
        data[offset:offset + len(raw)] = raw

    for ordinal, function_rva in enumerate(callers):
        function = RuntimeFunction(function_rva, function_rva + 0x40, 0x3000 + ordinal * 4)
        runtime_functions.append(function)
        for slot, target_rva in enumerate(strings):
            instruction_rva = function_rva + 4 + slot * 8
            raw_offset = text.raw_offset + (instruction_rva - text.virtual_address)
            data[raw_offset:raw_offset + 3] = b"\x48\x8D\x0D"
            displacement = target_rva - (instruction_rva + 7)
            struct.pack_into("<i", data, raw_offset + 3, displacement)

    return PEImage(
        data=bytes(data),
        machine=0x8664,
        timestamp=0x12345678,
        image_base=0x140000000,
        exception_directory_rva=0,
        exception_directory_size=0,
        sections=(text, rdata),
        runtime_functions=tuple(runtime_functions),
    )


def _native_with_shared_caller(caller=0x1010):
    return {
        "needles": [
            {
                "needle": "IsItem",
                "hits": [{
                    "leaRipXrefs": [{
                        "candidateFunctionSource": "pdata",
                        "candidateFunctionRva": 0x3000,
                        "candidateFunctionInboundCodeRefs": {
                            "refs": [{"sourceFunctionRva": caller}],
                        },
                        "candidateFunctionCodeRefs": {"refs": []},
                    }],
                }],
            },
            {
                "needle": "RequestAIPCExecuteAbility",
                "hits": [{
                    "leaRipXrefs": [{
                        "candidateFunctionSource": "pdata",
                        "candidateFunctionRva": 0x3100,
                        "candidateFunctionInboundCodeRefs": {"refs": []},
                        "candidateFunctionCodeRefs": {
                            "refs": [{
                                "targetFunctionRva": 0x3200,
                                "targetFunctionInboundCodeRefs": {
                                    "refs": [{"sourceFunctionRva": caller}],
                                },
                            }],
                        },
                    }],
                }],
            },
        ],
    }


def test_caller_anchor_map_keeps_exact_direct_and_next_hop_provenance():
    result = _caller_anchor_map(_native_with_shared_caller())
    assert result == {
        0x1010: {
            "anchorNeedles": ["IsItem", "RequestAIPCExecuteAbility"],
            "provenance": ["direct-owner-inbound", "next-hop-target-inbound"],
        },
    }


def test_padding_heuristic_anchor_owner_cannot_create_commit_caller_candidate():
    native = _native_with_shared_caller()
    native["needles"][0]["hits"][0]["leaRipXrefs"][0][
        "candidateFunctionSource"
    ] = "padding-heuristic"
    result = _caller_anchor_map(native)
    assert result[0x1010]["anchorNeedles"] == ["RequestAIPCExecuteAbility"]
    assert result[0x1010]["provenance"] == ["next-hop-target-inbound"]


def test_exact_pdata_function_scanner_decodes_ascii_and_utf16_lea_targets():
    image = _image_with_string_refs()
    result = _function_string_refs(image, 0x1010)
    texts = {row["text"]: row for row in result["refs"]}

    assert result["exactPdataFunction"] is True
    assert result["refsTruncated"] is False
    assert texts["CommitBattleCommandItem"]["encoding"] == "ascii"
    assert texts["DebugOnlyName"]["section"] == ".rdata"
    assert texts["SelectItemCommand"]["encoding"] == "utf16le"


def test_non_function_boundary_is_rejected_instead_of_guessing_bounds():
    image = _image_with_string_refs()
    result = _function_string_refs(image, 0x1014)
    assert result["exactPdataFunction"] is False
    assert result["refs"] == []


def test_shared_item_ability_caller_ranks_discovered_command_names_without_validating_hook():
    image = _image_with_string_refs()
    result = analyze_item_commit_caller_strings(image, _native_with_shared_caller())

    assert result["implementationReady"] is False
    assert result["playerItemCommandCommitValidated"] is False
    assert result["callerCandidateCount"] == 1
    assert result["exactPdataCallerCount"] == 1
    assert result["multiAnchorCallerCount"] == 1
    caller = result["callers"][0]
    assert caller["multiAnchorCaller"] is True
    assert caller["anchorNeedles"] == ["IsItem", "RequestAIPCExecuteAbility"]

    leads = {row["text"]: row for row in result["rankedReflectedNameLeads"]}
    assert "DebugOnlyName" not in leads
    assert leads["CommitBattleCommandItem"]["matchedLeadTokens"] == [
        "battle", "command", "commit", "item"
    ]
    assert leads["CommitBattleCommandItem"]["supportAnchorCount"] == 2
    assert leads["SelectItemCommand"]["matchedLeadTokens"] == [
        "command", "item", "select"
    ]
    assert "player-item-command-commit-hook-unresolved" in result["blockers"]
    assert "ranked-name-leads-require-installed-disassembly-validation" in result["blockers"]


def test_same_discovered_name_across_multiple_exact_callers_aggregates_support():
    image = _image_with_string_refs(callers=(0x1010, 0x1060))
    native = _native_with_shared_caller(0x1010)
    second = _native_with_shared_caller(0x1060)
    native["needles"].extend(second["needles"])

    result = analyze_item_commit_caller_strings(image, native)
    lead = next(
        row for row in result["rankedReflectedNameLeads"]
        if row["text"] == "CommitBattleCommandItem"
    )

    assert result["exactPdataCallerCount"] == 2
    assert lead["supportCallerCount"] == 2
    assert lead["supportAnchorCount"] == 2
    assert lead["callerFunctions"] == [0x1010, 0x1060]
    assert result["playerItemCommandCommitValidated"] is False
