import struct

from games.ff7r.native_probe import PEImage, RuntimeFunction, Section
from games.ff7r.sprint_authority_probe import (
    _candidate_functions,
    analyze_sprint_authority_strings,
)


def _assessment():
    return {
        "nativeFunctionClusters": [
            {
                "functionRva": 0x1010,
                "families": ["dash-scale", "root-motion"],
                "crossFamily": True,
                "allThreeFamilies": False,
                "directNeedles": [],
                "nextHopNeedles": ["DashRootMotionTranslationScale", "RootMotionScale"],
                "registrationCollisionRisk": False,
            },
            {
                "functionRva": 0x1060,
                "families": ["dash-scale", "dash-state"],
                "crossFamily": True,
                "allThreeFamilies": False,
                "directNeedles": ["DashRootMotionTranslationScale", "RunToDashBlendInputThreshold"],
                "nextHopNeedles": [],
                "registrationCollisionRisk": True,
            },
            {
                "functionRva": 0x10B0,
                "families": ["root-motion"],
                "crossFamily": False,
                "allThreeFamilies": False,
                "directNeedles": ["RootMotionScale"],
                "nextHopNeedles": [],
                "registrationCollisionRisk": False,
            },
        ],
        "nativeFunctionCorrelations": {
            "dashToAnimationRootMotion": [0x2000],
            "dashToAnimationRootMotionCallers": [0x1010, 0x1100],
            "dashScaleToBehaviorStateCallers": [0x1010],
        },
    }


def _image():
    data = bytearray(0x800)
    text = Section(".text", 0x1000, 0x300, 0x000, 0x300)
    rdata = Section(".rdata", 0x2000, 0x300, 0x300, 0x300)
    functions = (
        RuntimeFunction(0x1010, 0x1050, 0x3000),
        RuntimeFunction(0x1060, 0x10A0, 0x3004),
        RuntimeFunction(0x1100, 0x1140, 0x3008),
    )
    strings = {
        0x2000: b"PlayerSprintVelocity\0",
        0x2040: b"DebugOnlyName\0",
        0x2080: b"MovementSpeed\0",
        0x20C0: b"MaxWalkSpeed\0",
        0x2100: b"RootMotionScale\0",
    }
    for rva, raw in strings.items():
        offset = rdata.raw_offset + (rva - rdata.virtual_address)
        data[offset:offset + len(raw)] = raw

    refs = {
        0x1010: (0x2000, 0x2040, 0x2100),
        0x1060: (0x2080,),
        0x1100: (0x2000, 0x20C0),
    }
    for function_rva, targets in refs.items():
        for slot, target_rva in enumerate(targets):
            instruction_rva = function_rva + 4 + slot * 8
            raw_offset = text.raw_offset + (instruction_rva - text.virtual_address)
            data[raw_offset:raw_offset + 3] = b"\x48\x8D\x0D"
            struct.pack_into(
                "<i",
                data,
                raw_offset + 3,
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


def test_candidate_functions_use_only_cross_family_clusters_and_caller_correlations():
    result = _candidate_functions(_assessment())

    assert sorted(result) == [0x1010, 0x1060, 0x1100]
    assert result[0x1010]["preferredManualLead"] is True
    assert result[0x1010]["origins"] == [
        "common-inbound:dashScaleToBehaviorStateCallers",
        "common-inbound:dashToAnimationRootMotionCallers",
        "cross-family-function-cluster",
    ]
    assert result[0x1060]["registrationCollisionRisk"] is True
    assert result[0x1060]["preferredManualLead"] is False
    assert result[0x1100]["origins"] == [
        "common-inbound:dashToAnimationRootMotionCallers"
    ]
    assert 0x10B0 not in result
    assert 0x2000 not in result


def test_authority_string_discovery_ranks_velocity_and_speed_without_validating_hook():
    result = analyze_sprint_authority_strings(_image(), _assessment())

    assert result["implementationReady"] is False
    assert result["sprintSpeedAuthorityValidated"] is False
    assert result["candidateFunctionCount"] == 3
    assert result["exactPdataCandidateFunctionCount"] == 3
    assert result["preferredManualCandidateCount"] == 1

    leads = {row["text"]: row for row in result["rankedAuthorityLeads"]}
    assert "DebugOnlyName" not in leads
    assert "RootMotionScale" not in leads
    assert leads["PlayerSprintVelocity"]["matchedAuthorityTokens"] == [
        "sprint", "velocity"
    ]
    assert leads["PlayerSprintVelocity"]["supportFunctionCount"] == 2
    assert leads["PlayerSprintVelocity"]["preferredSupportCount"] == 1
    assert leads["MovementSpeed"]["matchedAuthorityTokens"] == [
        "move", "movement", "movementspeed", "speed"
    ]
    assert leads["MaxWalkSpeed"]["matchedAuthorityTokens"] == [
        "maxwalkspeed", "speed"
    ]
    assert "authoritative-player-sprint-speed-path-unvalidated" in result["blockers"]
    assert "candidate-authority-names-require-installed-disassembly-validation" in result["blockers"]


def test_registration_collision_string_remains_visible_but_not_preferred():
    result = analyze_sprint_authority_strings(_image(), _assessment())
    function = next(row for row in result["functions"] if row["functionRva"] == 0x1060)
    assert function["registrationCollisionRisk"] is True
    assert function["preferredManualLead"] is False
    assert any(row["text"] == "MovementSpeed" for row in function["rankedStringRefs"])
    assert result["sprintSpeedAuthorityValidated"] is False
