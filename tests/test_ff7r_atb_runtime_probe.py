from games.ff7r.atb_runtime_probe import assess_atb_runtime_evidence


def _native(**counts):
    return {
        "needles": [
            {"needle": needle, "hits": [{}] * count}
            for needle, count in counts.items()
        ]
    }


def test_guard_and_ability_data_can_be_ready_while_runtime_is_not():
    result = assess_atb_runtime_evidence(
        _native(), resident_rows=4, guard_rows=12, ability_rows=300)

    assert result["dataBacked"]["guardEditableNow"] is True
    assert result["dataBacked"]["abilityCostsEditableNow"] is True
    assert result["dataBacked"]["residentSemanticsValidated"] is False
    assert result["dataBacked"]["unitsValidated"] is False
    assert result["implementationReady"] is False


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
    assert runtime["atbMaxApiCandidatePresent"] is True
    assert runtime["accessorNeedleHits"]["SetATB"] == 1
    assert "direct-atb-read-write-api-semantics-unvalidated" in result["blockers"]
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
