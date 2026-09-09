from games.ff7r.atb_attack_reference import analyze_attack_atb_reference


def test_attack_reference_rejects_single_global_per_hit_constant():
    result = analyze_attack_atb_reference()
    constraints = result["constraints"]

    assert result["exactAttackFormulaValidated"] is False
    assert constraints["singleGlobalPerHitConstantRejected"] is True
    assert len({round(row["normalGainPerHit"], 3) for row in result["samples"]}) > 1
    assert constraints["perHitVsPerAttackEventStillUnresolved"] is True
    assert constraints["runtimeEventGranularityStillUnresolved"] is True


def test_one_hit_tifa_counterexample_rejects_simple_damage_proportional_atb_gain():
    result = analyze_attack_atb_reference()
    counterexample = result["cleanCounterexample"]

    assert counterexample == {
        "lowerPowerMove": "Whirling Uppercut",
        "lowerPower": 108,
        "lowerPowerNormalGain": 400,
        "higherPowerMove": "Omnistrike",
        "higherPower": 370,
        "higherPowerNormalGain": 50,
    }
    assert result["constraints"]["damageProportionalModelRejected"] is True


def test_stagger_bonus_is_not_one_global_multiplier_across_moves():
    result = analyze_attack_atb_reference()
    multipliers = {
        row["move"]: row["staggerMultiplier"]
        for row in result["samples"]
    }

    assert multipliers["Punisher Mode Crush"] == 2.0
    assert multipliers["Whirling Uppercut"] == 1.25
    assert multipliers["Rise and Fall"] > 4.0
    assert result["constraints"]["singleGlobalStaggerMultiplierRejected"] is True


def test_reference_requires_move_specific_explanation_but_does_not_invent_storage_model():
    result = analyze_attack_atb_reference()

    assert result["constraints"]["moveSpecificValuesRequiredBySamples"] is True
    assert result["exactAttackFormulaValidated"] is False
    assert any("do not establish" in note for note in result["notes"])
    assert any("HitSuccess versus PerHitSuccess" in note for note in result["notes"])
