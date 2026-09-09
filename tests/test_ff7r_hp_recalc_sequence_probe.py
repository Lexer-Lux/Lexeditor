import struct

from games.ff7r.hp_recalc_sequence_probe import analyze_hp_recalc_call_sequences
from games.ff7r.native_probe import PEImage, RuntimeFunction, Section


def _assessment(*, collision=False):
    status_target = 0x1500 if collision else 0x1100
    max_write_target = 0x1500 if collision else 0x1250
    return {
        "functionEvidence": {
            "BPGetPlayerStatus": {
                "expandedPdataFunctions": [status_target],
                "expandedInboundCallerFunctions": [0x1000],
            },
            "BPGetPlayerStatusWithEquipment": {
                "expandedPdataFunctions": [],
                "expandedInboundCallerFunctions": [],
            },
            "BPGetPlayerStatusWithMateria": {
                "expandedPdataFunctions": [],
                "expandedInboundCallerFunctions": [],
            },
            "BPGetPlayerHPMax": {
                "expandedPdataFunctions": [0x1150],
                "expandedInboundCallerFunctions": [0x1000],
            },
            "GetCharaHPMax": {
                "expandedPdataFunctions": [],
                "expandedInboundCallerFunctions": [],
            },
            "BPGetPlayerHP": {
                "expandedPdataFunctions": [0x1200],
                "expandedInboundCallerFunctions": [0x1000, 0x1400],
            },
            "GetCharaHP": {
                "expandedPdataFunctions": [],
                "expandedInboundCallerFunctions": [],
            },
            "BPSetPlayerHPMax": {
                "expandedPdataFunctions": [max_write_target],
                "expandedInboundCallerFunctions": [0x1000, 0x1400],
            },
            "BPSetPlayerHP": {
                "expandedPdataFunctions": [0x1300],
                "expandedInboundCallerFunctions": [0x1000, 0x1400],
            },
        },
    }


def _call(data: bytearray, text: Section, instruction_rva: int, target_rva: int):
    offset = text.raw_offset + (instruction_rva - text.virtual_address)
    data[offset] = 0xE8
    struct.pack_into("<i", data, offset + 1, target_rva - (instruction_rva + 5))


def _image(*, collision=False):
    data = bytearray(0x900)
    text = Section(".text", 0x1000, 0x800, 0x000, 0x800)
    targets = [0x1150, 0x1200, 0x1300]
    if collision:
        targets.append(0x1500)
    else:
        targets.extend([0x1100, 0x1250])
    functions = [
        RuntimeFunction(0x1000, 0x1060, 0x3000),
        RuntimeFunction(0x1400, 0x1440, 0x3004),
    ]
    functions.extend(
        RuntimeFunction(rva, rva + 0x30, 0x3100 + index * 4)
        for index, rva in enumerate(targets)
    )

    status_target = 0x1500 if collision else 0x1100
    max_write_target = 0x1500 if collision else 0x1250
    # Full composed-status/max/current transaction candidate.
    _call(data, text, 0x1004, status_target)
    _call(data, text, 0x100C, 0x1150)
    _call(data, text, 0x1014, 0x1200)
    _call(data, text, 0x101C, max_write_target)
    _call(data, text, 0x1024, 0x1300)
    # Partial clamp/write neighborhood, deliberately missing composed status.
    _call(data, text, 0x1404, 0x1200)
    _call(data, text, 0x140C, max_write_target)
    _call(data, text, 0x1414, 0x1300)

    # PE .pdata entries are sorted by function RVA. PEImage.runtime_function_for_rva
    # intentionally uses binary search, so the synthetic fixture must preserve that
    # real-format invariant too.
    functions.sort(key=lambda row: row.begin_rva)
    return PEImage(
        data=bytes(data),
        machine=0x8664,
        timestamp=0x12345678,
        image_base=0x140000000,
        exception_directory_rva=0,
        exception_directory_size=0,
        sections=(text,),
        runtime_functions=tuple(functions),
    )


def test_full_exact_caller_transaction_is_ranked_without_validating_authority():
    result = analyze_hp_recalc_call_sequences(_image(), _assessment())

    assert result["implementationReady"] is False
    assert result["authoritativeMaxHPRecalculationValidated"] is False
    assert result["playableOnlyScopeValidated"] is False
    assert result["finalComposedValueValidated"] is False
    assert result["currentHPClampSemanticsValidated"] is False
    assert result["candidateCallerCount"] == 2
    assert result["preferredRecalculationLeadCount"] == 1
    assert result["fullRecalcClampNeighborhoodCount"] == 1

    preferred = result["preferredRecalculationLeads"][0]
    assert preferred["functionRva"] == 0x1000
    assert preferred["statusThenMaxWrite"] is True
    assert preferred["maxReadThenMaxWrite"] is True
    assert preferred["currentReadThenCurrentWrite"] is True
    assert preferred["currentClampNeighborhood"] is True
    assert preferred["fullRecalcClampNeighborhood"] is True
    assert preferred["multiRoleTargetCollisionInCalls"] is False
    assert preferred["preferredRecalculationLead"] is True
    assert preferred["observedCallRoles"] == [
        "composed-status", "current-read", "current-write", "max-read", "max-write"
    ]


def test_partial_write_clamp_caller_remains_visible_but_not_preferred():
    result = analyze_hp_recalc_call_sequences(_image(), _assessment())
    partial = next(
        row for row in result["candidateCallerEvidence"]
        if row["functionRva"] == 0x1400
    )

    assert partial["observedCallRoles"] == ["current-read", "current-write", "max-write"]
    assert partial["currentClampNeighborhood"] is True
    assert partial["statusThenMaxWrite"] is False
    assert partial["fullRecalcClampNeighborhood"] is False
    assert partial["preferredRecalculationLead"] is False
    assert result["currentHPClampSemanticsValidated"] is False


def test_multi_role_target_collision_blocks_preferred_transaction_promotion():
    result = analyze_hp_recalc_call_sequences(
        _image(collision=True), _assessment(collision=True)
    )

    assert result["multiRoleTargetFunctions"] == {
        0x1500: ["composed-status", "max-write"],
    }
    full = next(
        row for row in result["candidateCallerEvidence"]
        if row["functionRva"] == 0x1000
    )
    assert full["fullRecalcClampNeighborhood"] is True
    assert full["multiRoleTargetCollisionInCalls"] is True
    assert full["preferredRecalculationLead"] is False
    assert result["preferredRecalculationLeadCount"] == 0
    assert result["authoritativeMaxHPRecalculationValidated"] is False


def test_no_multi_role_caller_fails_closed():
    assessment = _assessment()
    for row in assessment["functionEvidence"].values():
        row["expandedInboundCallerFunctions"] = []
    result = analyze_hp_recalc_call_sequences(_image(), assessment)

    assert result["candidateCallerCount"] == 0
    assert result["candidateCallerEvidence"] == []
    assert result["preferredRecalculationLeads"] == []
    assert "authoritative-max-hp-recalculation-interception-unvalidated" in result["blockers"]
