import struct

from games.ff7r.atb_dodge_transition_probe import analyze_dodge_atb_call_sequences
from games.ff7r.native_probe import PEImage, RuntimeFunction, Section


def _assessment(*, common=True):
    dodge_callers = [0x1000, 0x1300] if common else [0x1000]
    atb_callers = [0x1000, 0x1300] if common else [0x1400]
    return {
        "runtimeResearch": {
            "nativeFunctionEvidence": {
                "IsDodge": {
                    "expandedPdataFunctions": [0x1100],
                    "expandedInboundCallerFunctions": dodge_callers,
                },
                "IsDodgeInvincible": {
                    "expandedPdataFunctions": [],
                    "expandedInboundCallerFunctions": [],
                },
                "SetATB": {
                    "expandedPdataFunctions": [0x1200],
                    "expandedInboundCallerFunctions": atb_callers,
                },
                "SetATBAll": {
                    "expandedPdataFunctions": [],
                    "expandedInboundCallerFunctions": [],
                },
                "ForceUpdateATBGauge": {
                    "expandedPdataFunctions": [],
                    "expandedInboundCallerFunctions": [],
                },
            },
        },
    }


def _call(data: bytearray, text: Section, instruction_rva: int, target_rva: int):
    offset = text.raw_offset + (instruction_rva - text.virtual_address)
    data[offset] = 0xE8
    struct.pack_into("<i", data, offset + 1, target_rva - (instruction_rva + 5))


def _image():
    data = bytearray(0x500)
    text = Section(".text", 0x1000, 0x400, 0x000, 0x400)
    functions = (
        RuntimeFunction(0x1000, 0x1040, 0x3000),
        RuntimeFunction(0x1100, 0x1140, 0x3004),
        RuntimeFunction(0x1200, 0x1240, 0x3008),
        RuntimeFunction(0x1300, 0x1340, 0x300C),
        RuntimeFunction(0x1400, 0x1440, 0x3010),
    )

    # Preferred lead: IsDodge call, recognizable conditional branch, then SetATB.
    _call(data, text, 0x1004, 0x1100)
    branch_offset = 0x100B - text.virtual_address
    data[branch_offset:branch_offset + 2] = b"\x74\x05"  # JE rel8
    _call(data, text, 0x1010, 0x1200)

    # Common caller but reverse order: never promoted as a dodge->ATB transition lead.
    _call(data, text, 0x1304, 0x1200)
    _call(data, text, 0x1310, 0x1100)

    return PEImage(
        data=bytes(data),
        machine=0x8664,
        timestamp=0x12345678,
        image_base=0x140000000,
        exception_directory_rva=0,
        exception_directory_size=0,
        sections=(text,),
        runtime_functions=functions,
    )


def test_common_callers_report_exact_dodge_and_set_atb_call_order():
    result = analyze_dodge_atb_call_sequences(_image(), _assessment())

    assert result["implementationReady"] is False
    assert result["dodgeTransitionValidated"] is False
    assert result["oncePerDodgeEdgeValidated"] is False
    assert result["atbSubtractionSemanticsValidated"] is False
    assert result["dodgeTargetFunctions"] == [0x1100]
    assert result["atbSetTargetFunctions"] == [0x1200]
    assert result["commonCallers"] == [0x1000, 0x1300]
    assert result["sequencePairCount"] == 2

    by_caller = {row["callerFunctionRva"]: row for row in result["sequencePairs"]}
    preferred = by_caller[0x1000]
    assert preferred["atbCallAfterDodgeCall"] is True
    assert preferred["conditionalBranchBetween"] is True
    assert preferred["preferredTransitionLead"] is True
    assert preferred["conditionalBranches"][0]["encoding"] == "jcc-rel8"

    reverse = by_caller[0x1300]
    assert reverse["atbCallAfterDodgeCall"] is False
    assert reverse["conditionalBranchBetween"] is False
    assert reverse["preferredTransitionLead"] is False
    assert result["preferredTransitionLeadCount"] == 1
    assert result["dodgeTransitionValidated"] is False


def test_no_common_exact_caller_fails_closed_without_sequence_guessing():
    result = analyze_dodge_atb_call_sequences(_image(), _assessment(common=False))

    assert result["commonCallerCount"] == 0
    assert result["commonCallers"] == []
    assert result["callerEvidence"] == []
    assert result["sequencePairs"] == []
    assert result["preferredTransitionLeadCount"] == 0
    assert result["oncePerDodgeEdgeValidated"] is False


def test_sequence_lead_never_claims_subtraction_direction_units_or_edge_timing():
    result = analyze_dodge_atb_call_sequences(_image(), _assessment())
    assert result["preferredTransitionLeadCount"] == 1
    assert result["atbSubtractionSemanticsValidated"] is False
    assert result["oncePerDodgeEdgeValidated"] is False
    assert "dodge-atb-subtraction-semantics-unvalidated" in result["blockers"]
    assert "candidate-dodge-atb-call-sequence-requires-installed-disassembly-validation" in result["blockers"]
