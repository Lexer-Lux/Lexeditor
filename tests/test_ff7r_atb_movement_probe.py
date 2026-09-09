import struct

from games.ff7r.atb_movement_probe import correlate_atb_movement_evidence
from games.ff7r.native_probe import PEImage, RuntimeFunction, Section


def _atb():
    return {
        "runtimeResearch": {
            "nativeFunctionEvidence": {
                "SetATB": {
                    "expandedPdataFunctions": [0x1100],
                    "expandedInboundCallerFunctions": [0x1200],
                },
                "ATBValue": {
                    "expandedPdataFunctions": [0x1300],
                    "expandedInboundCallerFunctions": [0x1400],
                },
                "GetATB": {
                    "expandedPdataFunctions": [],
                    "expandedInboundCallerFunctions": [],
                },
                "GetATBMax": {
                    "expandedPdataFunctions": [],
                    "expandedInboundCallerFunctions": [],
                },
            },
        },
    }


def _sprint():
    return {
        "nativeFunctionEvidence": {
            "DashRootMotionTranslationScale": {
                "expandedPdataFunctions": [0x1100],
                "expandedInboundCallerFunctions": [0x1500],
            },
            "RunSwitchBehaviorDashInputBlockTime": {
                "expandedPdataFunctions": [0x1600],
                "expandedInboundCallerFunctions": [0x1400],
            },
        },
    }


def _image():
    data = bytearray(0x600)
    text = Section(".text", 0x1000, 0x500, 0x000, 0x500)
    rdata = Section(".rdata", 0x2000, 0x100, 0x500, 0x100)
    functions = (
        RuntimeFunction(0x1100, 0x1140, 0x3000),
        RuntimeFunction(0x1400, 0x1440, 0x3004),
    )
    strings = {
        0x2000: b"MovementState\0",
        0x2020: b"PlayerVelocity\0",
        0x2040: b"ATBValue\0",
        0x2060: b"DebugOnly\0",
    }
    for rva, raw in strings.items():
        offset = rdata.raw_offset + (rva - rdata.virtual_address)
        data[offset:offset + len(raw)] = raw

    refs = {
        0x1100: (0x2000,),
        0x1400: (0x2020, 0x2040, 0x2060),
    }
    for function_rva, targets in refs.items():
        for slot, target_rva in enumerate(targets):
            instruction_rva = function_rva + 4 + slot * 8
            raw_offset = text.raw_offset + (instruction_rva - text.virtual_address)
            data[raw_offset:raw_offset + 3] = b"\x48\x8D\x0D"
            struct.pack_into(
                "<i", data, raw_offset + 3,
                target_rva - (instruction_rva + 7),
            )

    return PEImage(
        data=bytes(data),
        machine=0x8664,
        timestamp=0x12345678,
        image_base=0x140000000,
        exception_directory_rva=0,
        exception_directory_size=0,
        sections=(text, rdata),
        runtime_functions=functions,
    )


def test_bridge_reports_exact_shared_function_and_shared_caller_separately():
    result = correlate_atb_movement_evidence(_atb(), _sprint())

    assert result["implementationReady"] is False
    assert result["movementPredicateValidated"] is False
    assert result["movementToATBAccumulatorLinkValidated"] is False
    assert result["sharedFunctions"] == [0x1100]
    assert result["sharedInboundCallers"] == [0x1400]
    assert result["bridgeFunctions"] == [0x1100, 0x1400]
    assert result["sharedFunctionCount"] == 1
    assert result["sharedInboundCallerCount"] == 1
    assert result["rankedMovementNameLeads"] == []
    assert "authoritative-player-movement-predicate-unvalidated" in result["blockers"]


def test_bridge_string_scan_ranks_only_names_from_exact_shared_neighborhoods():
    result = correlate_atb_movement_evidence(_atb(), _sprint(), image=_image())

    assert result["bridgeFunctionCount"] == 2
    rows = {row["functionRva"]: row for row in result["bridgeFunctionEvidence"]}
    assert rows[0x1100]["origins"] == ["shared-function"]
    assert rows[0x1400]["origins"] == ["shared-inbound-caller"]
    assert all(row["exactPdataFunction"] for row in rows.values())

    names = {row["text"]: row for row in result["rankedMovementNameLeads"]}
    assert "MovementState" in names
    assert names["MovementState"]["matchedMovementTokens"] == ["movement"]
    assert "PlayerVelocity" in names
    assert names["PlayerVelocity"]["matchedMovementTokens"] == ["velocity"]
    assert "ATBValue" not in names  # existing anchor, not a discovery lead
    assert "DebugOnly" not in names
    assert result["movementPredicateValidated"] is False
    assert result["movementToATBAccumulatorLinkValidated"] is False


def test_no_overlap_stays_empty_and_never_infers_movement_from_sprint_presence():
    sprint = {
        "nativeFunctionEvidence": {
            "DashRootMotionTranslationScale": {
                "expandedPdataFunctions": [0x1700],
                "expandedInboundCallerFunctions": [0x1800],
            },
        },
    }
    result = correlate_atb_movement_evidence(_atb(), sprint)

    assert result["sharedFunctions"] == []
    assert result["sharedInboundCallers"] == []
    assert result["bridgeFunctions"] == []
    assert result["movementPredicateValidated"] is False
    assert result["implementationReady"] is False
