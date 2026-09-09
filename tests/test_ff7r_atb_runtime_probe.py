from games.ff7r.atb_runtime_probe import assess_atb_runtime_evidence


def _native(**counts):
    return {
        "needles": [
            {"needle": needle, "hits": [{}] * count}
            for needle, count in counts.items()
        ]
    }


def _inbound(*callers):
    return {
        "refs": [
            {"sourceFunctionRva": caller, "kind": "call-rel32"}
            for caller in callers
        ]
    }


def _function_row(
    needle,
    function_rva,
    *next_hops,
    source="pdata",
    callers=(),
    next_hop_callers=(),
):
    xref = {
        "candidateFunctionRva": function_rva,
        "candidateFunctionSource": source,
        "candidateFunctionCodeRefs": {
            "refs": [
                {
                    "targetFunctionRva": target,
                    **(
                        {"targetFunctionInboundCodeRefs": _inbound(*next_hop_callers)}
                        if next_hop_callers else {}
                    ),
                }
                for target in next_hops
            ],
        },
    }
    if callers:
        xref["candidateFunctionInboundCodeRefs"] = _inbound(*callers)
    return {
        "needle": needle,
        "hits": [{"leaRipXrefs": [xref]}],
    }


def _function_native(*rows):
    return {"needles": list(rows)}


def test_guard_and_ability_data_can_be_ready_while_runtime_is_not():
    result = assess_atb_runtime_evidence(
        _native(), resident_rows=4, guard_rows=12, ability_rows=300)

    assert result["dataBacked"]["guardEditableNow"] is True
    assert result["dataBacked"]["abilityCostsEditableNow"] is True
    assert result["dataBacked"]["residentSemanticsValidated"] is False
    assert result["dataBacked"]["unitsValidated"] is False
    assert result["implementationReady"] is False


def test_documented_vanilla_atb_values_are_reference_fingerprints_not_validation():
    result = assess_atb_runtime_evidence(_native(), resident_rows=8)
    reference = result["dataBacked"]["documentedVanillaReference"]

    assert reference["internalUnitsPerDisplayedBar"] == 1000.0
    assert reference["normalGaugeInternalUnits"] == 2000.0
    assert reference["playerPassiveMultiplier"] == 1.0
    assert reference["aiPassiveMultiplier"] == 0.35
    assert reference["guardMultiplier"] == 0.1
    assert reference["dodgeMultiplier"] == 0.0
    assert reference["hasteMultiplier"] == 1.4
    assert reference["slowMultiplier"] == 0.6
    assert result["dataBacked"]["documentedReferenceValidatedAgainstInstalledRows"] is False
    assert result["dataBacked"]["residentSemanticsValidated"] is False


def test_accumulator_string_evidence_never_marks_hook_semantics_validated():
    result = assess_atb_runtime_evidence(
        _native(ATBValue=2, EnableForceUpdateATB=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["accumulatorCandidatePresent"] is True
    assert result["runtimeResearch"]["accumulatorSemanticsValidated"] is False
    assert "atb-accumulator-semantics-unvalidated" in result["blockers"]


def test_direct_atb_get_set_api_is_reported_without_guessing_units():
    result = assess_atb_runtime_evidence(
        _native(SetATB=1, GetATB=1, GetATBMax=1), guard_rows=1, ability_rows=1)

    runtime = result["runtimeResearch"]
    assert runtime["directATBApiCandidatePresent"] is True
    assert runtime["directATBApiFunctionCandidatePresent"] is False
    assert runtime["atbMaxApiCandidatePresent"] is True
    assert runtime["accessorNeedleHits"]["SetATB"] == 1
    assert "direct-atb-read-write-api-semantics-unvalidated" in result["blockers"]
    assert "direct-atb-read-write-function-path-unresolved" in result["blockers"]
    assert "atb-max-unit-contract-unvalidated" in result["blockers"]
    assert result["dataBacked"]["unitsValidated"] is False


def test_dexterity_anchor_does_not_guess_speed_formula():
    result = assess_atb_runtime_evidence(
        _native(BPGetPlayerDexterity=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["speedCandidatePresent"] is True
    assert result["runtimeResearch"]["speedFormulaValidated"] is False
    assert "speed-atb-formula-unvalidated" in result["blockers"]
    assert result["knownContracts"]["speedStat"].startswith("FEndPlayerStatus.Dexterity")


def test_resident_parameter_reader_is_only_a_correlation_anchor():
    result = assess_atb_runtime_evidence(
        _native(GetResidentParameterFloatBP=1), resident_rows=4, guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["residentReaderCandidatePresent"] is True
    assert result["dataBacked"]["residentSemanticsValidated"] is False


def test_hit_bonus_modifier_does_not_guess_base_hit_gain_semantics():
    result = assess_atb_runtime_evidence(
        _native(HitBonusATBRecoverAdd=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["hitGainCandidatePresent"] is True
    assert result["runtimeResearch"]["hitFormulaValidated"] is False
    assert result["runtimeResearch"]["hitEventGranularityCandidatePresent"] is False
    assert "hit-atb-formula-unvalidated" in result["blockers"]
    assert "hit-atb-event-granularity-unresolved" in result["blockers"]


def test_per_hit_and_attack_level_events_create_granularity_research_path_only():
    result = assess_atb_runtime_evidence(
        _native(
            HitBonusATBRecoverAdd=1,
            NormalAttackHitSuccess=1,
            NormalAttackPerHitSuccess=1,
            WeaponAbilityHitSuccess=1,
            WeaponAbilityPerHitSuccess=1,
        ),
        guard_rows=1,
        ability_rows=1,
    )

    runtime = result["runtimeResearch"]
    assert runtime["hitEventGranularityCandidatePresent"] is True
    assert runtime["hitEventNeedleHits"]["NormalAttackHitSuccess"] == 1
    assert runtime["hitEventNeedleHits"]["NormalAttackPerHitSuccess"] == 1
    assert "hit-atb-event-granularity-unvalidated" in result["blockers"]
    assert "hit-atb-event-granularity-unresolved" not in result["blockers"]
    assert result["implementationReady"] is False


def test_is_dodge_is_only_a_state_candidate_and_transition_remains_blocked():
    result = assess_atb_runtime_evidence(
        _native(IsDodge=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["dodgeStateCandidatePresent"] is True
    assert result["runtimeResearch"]["dodgeTransitionValidated"] is False
    assert "dodge-state-path-unresolved" not in result["blockers"]
    assert "dodge-transition-edge-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_discovery_error_disables_data_editability():
    result = assess_atb_runtime_evidence(
        _native(), guard_rows=1, ability_rows=1, discovery_errors=["bad table"])

    assert result["dataBacked"]["guardEditableNow"] is False
    assert result["dataBacked"]["abilityCostsEditableNow"] is False
    assert "data-discovery-errors" in result["blockers"]


def test_exact_pdata_atb_accessor_targets_correlate_without_validating_semantics():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row("SetATB", 0x1000, 0x5000),
            _function_row("GetATB", 0x2000, 0x5000),
            _function_row("GetATBMax", 0x3000, 0x5000),
        ),
        guard_rows=1,
        ability_rows=1,
    )

    runtime = result["runtimeResearch"]
    correlations = runtime["nativeFunctionCorrelations"]
    assert runtime["directATBApiCandidatePresent"] is True
    assert runtime["directATBApiFunctionCandidatePresent"] is True
    assert runtime["atbMaxFunctionCandidatePresent"] is True
    assert correlations["setToGet"] == [0x5000]
    assert correlations["setToMax"] == [0x5000]
    assert "direct-atb-read-write-function-path-unresolved" not in result["blockers"]
    assert "direct-atb-read-write-api-semantics-unvalidated" in result["blockers"]
    assert "atb-max-unit-contract-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_shared_atb_inbound_callers_are_reported_without_clearing_function_link_blockers():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row("SetATB", 0x1000, callers=(0x9000,)),
            _function_row("GetATB", 0x2000, callers=(0x9000,)),
            _function_row("GetATBMax", 0x3000, callers=(0x9000,)),
            _function_row("ATBValue", 0x4000, callers=(0x9100,)),
            _function_row("BPGetPlayerDexterity", 0x5000, callers=(0x9100,)),
            _function_row("HitBonusATBRecoverAdd", 0x6000, callers=(0x9200,)),
            _function_row("NormalAttackHitSuccess", 0x6100, callers=(0x9200,)),
            _function_row("NormalAttackPerHitSuccess", 0x6200, callers=(0x9300,)),
            _function_row("IsDodge", 0x7000, callers=(0x9000,)),
        ),
        guard_rows=1,
        ability_rows=1,
    )

    runtime = result["runtimeResearch"]
    correlations = runtime["nativeFunctionCorrelations"]
    assert correlations["setToGet"] == []
    assert correlations["setToGetCallers"] == [0x9000]
    assert correlations["setToMaxCallers"] == [0x9000]
    assert correlations["speedToAccumulatorCallers"] == [0x9100]
    assert correlations["hitModifierToAttackLevelEventsCallers"] == [0x9200]
    assert correlations["hitModifierToPerHitEventsCallers"] == []
    assert correlations["dodgeToSetATBCallers"] == [0x9000]
    assert runtime["nativeFunctionEvidence"]["SetATB"]["directInboundCallerFunctions"] == [0x9000]
    assert "direct-atb-read-write-function-link-unvalidated" in result["blockers"]
    assert "speed-to-accumulator-link-unvalidated" in result["blockers"]
    assert "dodge-transition-edge-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_hit_function_correlation_distinguishes_attack_level_from_per_hit_lead():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row("HitBonusATBRecoverAdd", 0x1000, 0x7000),
            _function_row("NormalAttackHitSuccess", 0x1100, 0x7000),
            _function_row("NormalAttackPerHitSuccess", 0x1200, 0x8000),
            _function_row("ATBValue", 0x1300, 0x7000),
        ),
        guard_rows=1,
        ability_rows=1,
    )

    correlations = result["runtimeResearch"]["nativeFunctionCorrelations"]
    assert correlations["hitModifierToAttackLevelEvents"] == [0x7000]
    assert correlations["hitModifierToPerHitEvents"] == []
    assert correlations["hitModifierToAccumulator"] == [0x7000]
    assert correlations["attackLevelEventsToAccumulator"] == [0x7000]
    assert correlations["perHitEventsToAccumulator"] == []
    assert "hit-atb-event-granularity-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_dodge_to_set_atb_function_correlation_remains_transition_blocked():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row("IsDodge", 0x1000, 0x6000),
            _function_row("SetATB", 0x2000, 0x6000),
        ),
        guard_rows=1,
        ability_rows=1,
    )

    correlations = result["runtimeResearch"]["nativeFunctionCorrelations"]
    assert correlations["dodgeToSetATB"] == [0x6000]
    assert "dodge-transition-edge-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_atb_function_correlations_ignore_padding_heuristic_owners_and_callers():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row(
                "SetATB", 0x1000, 0x5000,
                source="padding-heuristic", callers=(0x9000,),
            ),
            _function_row("GetATB", 0x2000, 0x5000),
        ),
        guard_rows=1,
        ability_rows=1,
    )

    runtime = result["runtimeResearch"]
    assert runtime["nativeFunctionEvidence"]["SetATB"]["expandedPdataFunctions"] == []
    assert runtime["nativeFunctionEvidence"]["SetATB"]["expandedInboundCallerFunctions"] == []
    assert runtime["nativeFunctionCorrelations"]["setToGet"] == []
    assert runtime["nativeFunctionCorrelations"]["setToGetCallers"] == []
    assert runtime["directATBApiFunctionCandidatePresent"] is False
    assert "direct-atb-read-write-function-path-unresolved" in result["blockers"]


def test_atb_function_cluster_marks_multi_family_direct_owner_as_registration_risk():
    result = assess_atb_runtime_evidence(
        _function_native(
            _function_row("HitBonusATBRecoverAdd", 0x9000),
            _function_row("NormalAttackHitSuccess", 0x9000),
        ),
        guard_rows=1,
        ability_rows=1,
    )
    cluster = next(
        row for row in result["runtimeResearch"]["nativeFunctionClusters"]
        if row["functionRva"] == 0x9000
    )

    assert cluster["families"] == ["attack-event", "hit-modifier"]
    assert cluster["crossFamily"] is True
    assert cluster["registrationCollisionRisk"] is True
    assert result["implementationReady"] is False
