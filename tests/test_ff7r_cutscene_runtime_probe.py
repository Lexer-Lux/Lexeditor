from games.ff7r.cutscene_runtime_probe import assess_cutscene_runtime_evidence


def _hit(function_rva):
    return {
        "hits": [{
            "leaRipXrefs": [{"candidateFunctionRva": function_rva}],
        }]
    }


def _native(**rows):
    return {
        "needles": [
            {"needle": needle, **payload}
            for needle, payload in rows.items()
        ]
    }


def test_cutscene_probe_keeps_string_only_cut_contract_unvalidated():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed={"hits": [{}]},
        GetGameSpeed={"hits": [{}]},
        EGameSpeed_CUT={"hits": [{}]},
        PlayCutScene={"hits": [{}]},
        SkipCinema={"hits": [{}]},
    ))

    assert result["cutGameSpeedContractPresent"] is True
    assert result["candidateFunctions"]["cutSpeedOverlap"] == []
    assert "cut-game-speed-channel-function-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_cut_channel_and_lifecycle_colocation_still_does_not_authorize_formula():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x1000),
        PlayCutScene=_hit(0x1000),
        RequestPlayCutScene=_hit(0x1400),
        SkipCinema=_hit(0x2000),
        IsSkipCinema=_hit(0x2000),
    ))

    assert result["candidateFunctions"]["cutSpeedOverlap"] == [0x1000]
    assert result["candidateFunctions"]["lifecycleSpeedOverlap"] == [0x1000]
    assert "cut-game-speed-channel-function-unvalidated" not in result["blockers"]
    assert "cutscene-lifecycle-to-speed-link-unvalidated" not in result["blockers"]
    assert "native-fast-forward-to-speed-link-unvalidated" in result["blockers"]
    assert "base-times-native-fast-forward-formula-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_fast_forward_and_cut_speed_colocation_is_only_a_multiplier_lead():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x1000),
        PlayCutScene=_hit(0x1000),
        SkipCinema=_hit(0x1000),
        IsSkipCinemaAtThisFrame=_hit(0x1000),
    ))

    assert result["nativeFastForwardStateCandidatePresent"] is True
    assert result["candidateFunctions"]["fastForwardSpeedOverlap"] == [0x1000]
    assert "native-fast-forward-to-speed-link-unvalidated" not in result["blockers"]
    assert "native-fast-forward-multiplier-semantics-unvalidated" in result["blockers"]
    assert "base-times-native-fast-forward-formula-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_skip_state_without_cut_speed_contract_never_promotes_r2_behavior():
    result = assess_cutscene_runtime_evidence(_native(
        SkipCinema=_hit(0x2000),
        IsSkipCinema=_hit(0x2000),
        FastForward=_hit(0x2000),
    ))

    assert result["nativeFastForwardStateCandidatePresent"] is True
    assert result["cutGameSpeedContractPresent"] is False
    assert "cut-game-speed-contract-unresolved" in result["blockers"]
    assert result["implementationReady"] is False


def test_non_cut_speed_categories_are_reported_only_for_isolation_research():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x1000),
        EGameSpeed_SYSTEM=_hit(0x3000),
        EGameSpeed_BATTLE=_hit(0x3200),
        PlayCutScene=_hit(0x1000),
    ))

    assert result["candidateFunctions"]["nonCutSpeedCategories"] == [0x3000, 0x3200]
    assert "cut-only-gameplay-speed-isolation-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False
