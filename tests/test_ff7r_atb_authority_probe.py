import struct

from games.ff7r.atb_authority_probe import (
    _candidate_functions,
    _function_float_refs,
    analyze_atb_authority_refs,
)
from games.ff7r.native_probe import PEImage, RuntimeFunction, Section


def _assessment():
    return {
        "runtimeResearch": {
            "nativeFunctionClusters": [
                {
                    "functionRva": 0x1010,
                    "families": ["accumulator", "speed"],
                    "crossFamily": True,
                    "directNeedles": [],
                    "nextHopNeedles": ["ATBValue", "BPGetPlayerDexterity"],
                    "registrationCollisionRisk": False,
                },
                {
                    "functionRva": 0x1060,
                    "families": ["attack-event", "hit-modifier"],
                    "crossFamily": True,
                    "directNeedles": ["HitBonusATBRecoverAdd", "NormalAttackHitSuccess"],
                    "nextHopNeedles": [],
                    "registrationCollisionRisk": True,
                },
            ],
            "nativeFunctionCorrelations": {
                "speedToAccumulator": [0x1010],
                "dodgeToSetATBCallers": [0x10B0],
            },
            "nativeFunctionEvidence": {
                "SetATB": {
                    "expandedPdataFunctions": [0x1100],
                },
                "GetATB": {
                    "expandedPdataFunctions": [0x1150],
                },
                "ATBValue": {
                    "expandedPdataFunctions": [0x1010],
                },
                "BPGetPlayerDexterity": {
                    "expandedPdataFunctions": [0x1010],
                },
                "HitBonusATBRecoverAdd": {
                    "expandedPdataFunctions": [0x1060],
                },
            },
        },
    }


def _image():
    data = bytearray(0x900)
    text = Section(".text", 0x1000, 0x300, 0x000, 0x300)
    rdata = Section(".rdata", 0x2000, 0x400, 0x300, 0x400)
    functions = (
        RuntimeFunction(0x1010, 0x1050, 0x3000),
        RuntimeFunction(0x1060, 0x10A0, 0x3004),
        RuntimeFunction(0x10B0, 0x10F0, 0x3008),
        RuntimeFunction(0x1100, 0x1140, 0x300C),
        RuntimeFunction(0x1150, 0x1190, 0x3010),
    )

    strings = {
        0x2000: b"ATBPassiveRate\0",
        0x2040: b"PlayerDexterityATBCharge\0",
        0x2080: b"DebugOnlyName\0",
        0x20C0: b"DodgeATBRecover\0",
        0x2100: b"ATBValue\0",
    }
    for rva, raw in strings.items():
        offset = rdata.raw_offset + (rva - rdata.virtual_address)
        data[offset:offset + len(raw)] = raw

    constants = {
        0x2200: 1000.0,
        0x2204: 0.35,
        0x2208: 1.4,
        0x220C: 123.25,
    }
    for rva, value in constants.items():
        offset = rdata.raw_offset + (rva - rdata.virtual_address)
        struct.pack_into("<f", data, offset, value)

    # String LEAs accepted by the shared exact-function scanner.
    string_refs = {
        0x1010: (0x2000, 0x2040, 0x2080, 0x2100),
        0x10B0: (0x20C0,),
    }
    for function_rva, targets in string_refs.items():
        for slot, target_rva in enumerate(targets):
            instruction_rva = function_rva + 2 + slot * 8
            raw_offset = text.raw_offset + (instruction_rva - text.virtual_address)
            data[raw_offset:raw_offset + 3] = b"\x48\x8D\x0D"
            struct.pack_into(
                "<i", data, raw_offset + 3,
                target_rva - (instruction_rva + 7),
            )

    # Narrow scalar SSE RIP-relative forms consumed by _function_float_refs.
    float_refs = {
        0x1010: ((0x2200, 0x10), (0x2204, 0x59)),
        0x10B0: ((0x2208, 0x58),),
        0x1100: ((0x220C, 0x10),),
    }
    for function_rva, refs in float_refs.items():
        for slot, (target_rva, opcode) in enumerate(refs):
            instruction_rva = function_rva + 34 + slot * 8
            raw_offset = text.raw_offset + (instruction_rva - text.virtual_address)
            data[raw_offset:raw_offset + 4] = bytes((0xF3, 0x0F, opcode, 0x0D))
            struct.pack_into(
                "<i", data, raw_offset + 4,
                target_rva - (instruction_rva + 8),
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


def test_candidate_functions_prefer_correlations_and_cross_family_but_keep_anchor_only_context():
    result = _candidate_functions(_assessment())

    assert sorted(result) == [0x1010, 0x1060, 0x10B0, 0x1100, 0x1150]
    assert result[0x1010]["crossFamily"] is True
    assert result[0x1010]["correlated"] is True
    assert result[0x1010]["preferredManualLead"] is True
    assert result[0x1060]["registrationCollisionRisk"] is True
    assert result[0x1060]["preferredManualLead"] is False
    assert result[0x10B0]["correlated"] is True
    assert result[0x10B0]["preferredManualLead"] is True
    assert result[0x1100]["origins"] == ["anchor:SetATB"]
    assert result[0x1100]["preferredManualLead"] is False


def test_float_scanner_finds_only_exact_pdata_scalar_rip_refs_and_labels_known_values():
    image = _image()
    result = _function_float_refs(image, 0x1010)

    assert result["exactPdataFunction"] is True
    by_value = {round(row["floatValue"], 3): row for row in result["refs"]}
    assert by_value[1000.0]["operation"] == "movss"
    assert by_value[1000.0]["fingerprintLabels"] == ["internalUnitsPerDisplayedBar"]
    assert by_value[0.35]["operation"] == "mulss"
    assert by_value[0.35]["fingerprintLabels"] == ["aiPassiveMultiplier"]
    assert all(row["section"] == ".rdata" for row in result["refs"])

    not_boundary = _function_float_refs(image, 0x1011)
    assert not_boundary["exactPdataFunction"] is False
    assert not_boundary["refs"] == []


def test_authority_analysis_ranks_names_and_fingerprints_without_validating_units_or_formula():
    result = analyze_atb_authority_refs(_image(), _assessment())

    assert result["implementationReady"] is False
    assert result["unitsValidated"] is False
    assert result["passiveFormulaValidated"] is False
    assert result["speedFormulaValidated"] is False
    assert result["hitFormulaValidated"] is False
    assert result["hitEventGranularityValidated"] is False
    assert result["dodgeTransitionValidated"] is False
    assert result["candidateFunctionCount"] == 5
    assert result["preferredManualCandidateCount"] == 2

    names = {row["text"]: row for row in result["rankedAuthorityNameLeads"]}
    assert "DebugOnlyName" not in names
    assert "ATBValue" not in names  # existing source anchor, not a discovery lead
    assert names["ATBPassiveRate"]["matchedAuthorityTokens"] == ["atb", "passive", "rate"]
    assert names["PlayerDexterityATBCharge"]["matchedAuthorityTokens"] == [
        "atb", "charge", "dexterity"
    ]
    assert names["DodgeATBRecover"]["matchedAuthorityTokens"] == ["atb", "dodge", "recover"]

    fingerprints = result["documentedFingerprintReferences"]
    values = {round(row["floatValue"], 3) for row in fingerprints}
    assert 1000.0 in values
    assert 0.35 in values
    assert 1.4 in values
    assert 123.25 not in values
    assert result["documentedFingerprintReferenceCount"] == 3
    assert "atb-unit-contract-unvalidated" in result["blockers"]
    assert "candidate-atb-names-and-constants-require-installed-disassembly-validation" in result["blockers"]


def test_unrelated_scalar_constant_stays_visible_in_function_context_but_not_fingerprint_list():
    result = analyze_atb_authority_refs(_image(), _assessment())
    set_atb = next(row for row in result["functions"] if row["functionRva"] == 0x1100)
    assert set_atb["preferredManualLead"] is False
    assert len(set_atb["floatRefs"]) == 1
    assert set_atb["floatRefs"][0]["floatValue"] == 123.25
    assert set_atb["floatRefs"][0]["matchesDocumentedFingerprint"] is False
    assert set_atb["documentedFingerprintRefCount"] == 0
    assert result["unitsValidated"] is False
