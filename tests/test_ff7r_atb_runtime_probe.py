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
    assert result["implementationReady"] is False


def test_accumulator_string_evidence_never_marks_hook_semantics_validated():
    result = assess_atb_runtime_evidence(
        _native(ATBValue=2, EnableForceUpdateATB=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["accumulatorCandidatePresent"] is True
    assert result["runtimeResearch"]["accumulatorSemanticsValidated"] is False
    assert "atb-accumulator-semantics-unvalidated" in result["blockers"]


def test_dexterity_anchor_does_not_guess_speed_formula():
    result = assess_atb_runtime_evidence(
        _native(BPGetPlayerDexterity=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["speedCandidatePresent"] is True
    assert result["runtimeResearch"]["speedFormulaValidated"] is False
    assert "speed-atb-formula-unvalidated" in result["blockers"]


def test_hit_bonus_modifier_does_not_guess_base_hit_gain_semantics():
    result = assess_atb_runtime_evidence(
        _native(HitBonusATBRecoverAdd=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["hitGainCandidatePresent"] is True
    assert result["runtimeResearch"]["hitFormulaValidated"] is False
    assert "hit-atb-formula-unvalidated" in result["blockers"]


def test_is_dodge_is_only_a_state_candidate():
    result = assess_atb_runtime_evidence(
        _native(IsDodge=1), guard_rows=1, ability_rows=1)

    assert result["runtimeResearch"]["dodgeStateCandidatePresent"] is True
    assert "dodge-state-path-unresolved" not in result["blockers"]
    assert result["implementationReady"] is False


def test_discovery_error_disables_data_editability():
    result = assess_atb_runtime_evidence(
        _native(), guard_rows=1, ability_rows=1, discovery_errors=["bad table"])

    assert result["dataBacked"]["guardEditableNow"] is False
    assert result["dataBacked"]["abilityCostsEditableNow"] is False
    assert "data-discovery-errors" in result["blockers"]
