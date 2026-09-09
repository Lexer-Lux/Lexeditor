from games.ff7r.atb_resident_fingerprint import classify_resident_atb_fingerprints


def _row(tag, vanilla, *, prop="ParamFloat", key=None):
    return {
        "key": key or f"{tag}|{prop}",
        "tag": tag,
        "property": prop,
        "vanilla": vanilla,
    }


def test_acronym_camelcase_and_separator_tags_map_only_when_vanilla_value_agrees():
    result = classify_resident_atb_fingerprints([
        _row("ATBPlayer", 1.0),
        _row("ATB_Player_AI", 0.35),
        _row("ATBActionAI", 0.25),
        _row("ATB-Guard", 0.1),
        _row("ATBCaution", 0.0),
        _row("ATBAction", 0.0),
        _row("ATBDamage", 0.0),
        _row("ATBDodge", 0.0),
        _row("ATBSuspendAction", 0.0),
    ])

    assert result["uniqueFingerprintCount"] == 9
    assert set(result["uniqueFingerprintSemantics"]) == {
        "player-passive",
        "ai-passive",
        "action-ai",
        "guard",
        "caution",
        "action",
        "damage",
        "dodge",
        "suspend-action",
    }
    assert result["semantics"]["ai-passive"]["candidate"]["tagWords"] == [
        "atb", "player", "ai"
    ]
    assert result["semantics"]["action-ai"]["candidate"]["tagWords"] == [
        "atb", "action", "ai"
    ]
    assert all(
        row["runtimeSemanticsValidated"] is False
        and row["editableAsNamedSemantic"] is False
        for row in result["semantics"].values()
    )
    assert result["runtimeSemanticsValidated"] is False


def test_documented_value_without_semantic_tag_tokens_never_identifies_a_row():
    result = classify_resident_atb_fingerprints([
        _row("CompletelyUnrelatedFloatA", 1.0),
        _row("CompletelyUnrelatedFloatB", 0.35),
        _row("CompletelyUnrelatedFloatC", 0.25),
        _row("CompletelyUnrelatedFloatD", 0.1),
        _row("CompletelyUnrelatedFloatE", 0.0),
    ])

    assert result["uniqueFingerprintCount"] == 0
    for row in result["semantics"].values():
        assert row["status"] == "semantic-tag-not-found"
        assert row["candidate"] is None


def test_semantic_tag_with_wrong_vanilla_value_is_a_mismatch_not_a_candidate():
    result = classify_resident_atb_fingerprints([
        _row("ATBPlayer", 0.99),
        _row("ATBGuard", 0.2),
    ])

    player = result["semantics"]["player-passive"]
    guard = result["semantics"]["guard"]
    assert player["status"] == "tag-candidate-value-mismatch"
    assert player["tagCandidates"][0]["vanilla"] == 0.99
    assert player["fingerprintMatches"] == []
    assert player["candidate"] is None
    assert guard["status"] == "tag-candidate-value-mismatch"
    assert guard["candidate"] is None


def test_duplicate_tag_and_value_matches_are_reported_ambiguous():
    result = classify_resident_atb_fingerprints([
        _row("ATBGuard", 0.1, key="guard-a"),
        _row("BattleATBGuard", 0.1, key="guard-b"),
    ])

    guard = result["semantics"]["guard"]
    assert guard["status"] == "ambiguous-tag-and-value-candidates"
    assert guard["uniqueFingerprintMatch"] is False
    assert [row["key"] for row in guard["fingerprintMatches"]] == [
        "guard-a", "guard-b"
    ]
    assert guard["candidate"] is None
    assert result["ambiguousFingerprintSemantics"] == ["guard"]


def test_paramint_and_nonfinite_values_cannot_match_float_fingerprints():
    result = classify_resident_atb_fingerprints([
        _row("ATBPlayer", 1, prop="ParamInt"),
        _row("ATBGuard", float("nan")),
        _row("ATBDodge", float("inf")),
    ])

    assert result["semantics"]["player-passive"]["status"] == "tag-candidate-value-mismatch"
    assert result["semantics"]["guard"]["status"] == "tag-candidate-value-mismatch"
    assert result["semantics"]["dodge"]["status"] == "tag-candidate-value-mismatch"
    assert result["uniqueFingerprintCount"] == 0


def test_action_action_ai_and_suspend_action_are_kept_semantically_separate():
    result = classify_resident_atb_fingerprints([
        _row("ATBAction", 0.0),
        _row("ATBActionAI", 0.25),
        _row("ATBSuspendAction", 0.0),
    ])

    action = result["semantics"]["action"]
    action_ai = result["semantics"]["action-ai"]
    suspend = result["semantics"]["suspend-action"]
    assert action["candidate"]["tag"] == "ATBAction"
    assert action_ai["candidate"]["tag"] == "ATBActionAI"
    assert suspend["candidate"]["tag"] == "ATBSuspendAction"
    assert [row["tag"] for row in action["tagCandidates"]] == ["ATBAction"]
    assert [row["tag"] for row in action_ai["tagCandidates"]] == ["ATBActionAI"]
    assert [row["tag"] for row in suspend["tagCandidates"]] == ["ATBSuspendAction"]


def test_zero_value_collision_does_not_cross_semantic_tag_families():
    result = classify_resident_atb_fingerprints([
        _row("ATBCaution", 0.0),
        _row("ATBAction", 0.0),
        _row("ATBDamage", 0.0),
        _row("ATBDodge", 0.0),
        _row("ATBSuspendAction", 0.0),
        _row("ATBUnrelated", 0.0),
    ])

    for semantic in ("caution", "action", "damage", "dodge", "suspend-action"):
        row = result["semantics"][semantic]
        assert row["uniqueFingerprintMatch"] is True
        assert len(row["fingerprintMatches"]) == 1
    assert all(
        candidate["tag"] != "ATBUnrelated"
        for semantic in ("caution", "action", "damage", "dodge", "suspend-action")
        for candidate in result["semantics"][semantic]["tagCandidates"]
    )
