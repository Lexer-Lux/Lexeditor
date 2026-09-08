from games.ff7r.cutscene_runtime_probe import assess_cutscene_runtime_evidence


def _hit(function_rva, *next_hops):
    xref = {
        "candidateFunctionRva": function_rva,
        "candidateFunctionSource": "pdata",
    }
    if next_hops:
        xref["candidateFunctionCodeRefs"] = {
            "refs": [
                {"targetFunctionRva": target, "kind": "call-rel32"}
                for target in next_hops
            ]
        }
    return {
        "hits": [{
            "leaRipXrefs": [xref],
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
    assert result["candidateFunctions"]["cutSpeedDirectOverlap"] == []
    assert result["candidateFunctions"]["cutSpeedReachableOverlap"] == []
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

    functions = result["candidateFunctions"]
    assert functions["cutSpeedDirectOverlap"] == [0x1000]
    assert functions["lifecycleSpeedDirectOverlap"] == [0x1000]
    assert "cut-game-speed-channel-function-unvalidated" not in result["blockers"]
    assert "cut-game-speed-channel-next-hop-unvalidated" not in result["blockers"]
    assert "cutscene-lifecycle-to-speed-link-unvalidated" not in result["blockers"]
    assert "native-fast-forward-to-speed-link-unvalidated" in result["blockers"]
    assert "base-times-native-fast-forward-formula-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_bounded_next_hops_are_navigation_evidence_not_direct_hook_validation():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000, 0x5000),
        GetGameSpeed=_hit(0x1100),
        EGameSpeed_CUT=_hit(0x2000, 0x5000),
        PlayCutScene=_hit(0x3000, 0x5000),
        SkipCinema=_hit(0x4000, 0x5000),
        IsSkipCinema=_hit(0x4100),
    ))

    functions = result["candidateFunctions"]
    assert functions["cutSpeedDirectOverlap"] == []
    assert functions["cutSpeedReachableOverlap"] == [0x5000]
    assert functions["lifecycleSpeedDirectOverlap"] == []
    assert functions["lifecycleSpeedReachableOverlap"] == [0x5000]
    assert functions["fastForwardSpeedDirectOverlap"] == []
    assert functions["fastForwardSpeedReachableOverlap"] == [0x5000]
    assert "cut-game-speed-channel-next-hop-unvalidated" in result["blockers"]
    assert "cutscene-lifecycle-next-hop-to-speed-unvalidated" in result["blockers"]
    assert "native-fast-forward-next-hop-semantics-unvalidated" in result["blockers"]
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
    assert result["candidateFunctions"]["fastForwardSpeedDirectOverlap"] == [0x1000]
    assert "native-fast-forward-to-speed-link-unvalidated" not in result["blockers"]
    assert "native-fast-forward-multiplier-semantics-unvalidated" in result["blockers"]
    assert "base-times-native-fast-forward-formula-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_generic_fast_forward_text_cannot_substitute_for_skip_state_contract():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x1000),
        PlayCutScene=_hit(0x1000),
        FastForward=_hit(0x1000),
    ))

    assert result["nativeFastForwardSupportPresent"] is True
    assert result["nativeFastForwardStateCandidatePresent"] is False
    assert result["candidateFunctions"]["nativeFastForwardSupport"]["direct"] == [0x1000]
    assert result["candidateFunctions"]["nativeFastForwardState"]["direct"] == []
    assert "native-fast-forward-state-unresolved" in result["blockers"]
    assert "generic-fast-forward-support-only" in result["blockers"]
    assert "native-fast-forward-multiplier-semantics-unvalidated" not in result["blockers"]
    assert result["implementationReady"] is False


def test_generic_cutscene_labels_cannot_substitute_for_play_action_contract():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x1000),
        EventScene=_hit(0x1000),
        CutScene=_hit(0x1000),
        SkipCinema=_hit(0x1000),
    ))

    assert result["cutsceneLifecycleSupportPresent"] is True
    assert result["cutsceneLifecycleCandidatePresent"] is False
    assert result["candidateFunctions"]["cutsceneSupport"]["direct"] == [0x1000]
    assert result["candidateFunctions"]["cutsceneAction"]["direct"] == []
    assert "cutscene-lifecycle-action-unresolved" in result["blockers"]
    assert "cutscene-generic-lifecycle-support-only" in result["blockers"]
    assert "cutscene-lifecycle-to-speed-link-unvalidated" not in result["blockers"]
    assert result["implementationReady"] is False


def test_skip_state_without_cut_speed_contract_never_promotes_r2_behavior():
    result = assess_cutscene_runtime_evidence(_native(
        SkipCinema=_hit(0x2000),
        IsSkipCinema=_hit(0x2000),
        FastForward=_hit(0x2000),
    ))

    assert result["nativeFastForwardStateCandidatePresent"] is True
    assert result["nativeFastForwardSupportPresent"] is True
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

    assert result["candidateFunctions"]["nonCutSpeedCategories"]["direct"] == [0x3000, 0x3200]
    assert "cut-only-gameplay-speed-isolation-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_function_clusters_preserve_direct_registration_collision_risk():
    result = assess_cutscene_runtime_evidence(_native(
        SetGameSpeed=_hit(0x1000),
        EGameSpeed_CUT=_hit(0x1000),
        PlayCutScene=_hit(0x1000),
        SkipCinema=_hit(0x1000),
    ))
    cluster = next(
        row for row in result["candidateFunctions"]["functionClusters"]
        if row["functionRva"] == 0x1000
    )

    assert cluster["families"] == ["cut-speed", "cutscene-action", "fast-forward-state"]
    assert cluster["directNeedles"] == [
        "EGameSpeed_CUT",
        "PlayCutScene",
        "SetGameSpeed",
        "SkipCinema",
    ]
    assert cluster["crossFamily"] is True
    assert cluster["registrationCollisionRisk"] is True
    assert result["implementationReady"] is False


def test_padding_heuristic_function_never_contributes_direct_or_next_hop_evidence():
    native = _native(
        SetGameSpeed={
            "hits": [{
                "leaRipXrefs": [{
                    "candidateFunctionRva": 0x1000,
                    "candidateFunctionSource": "padding-heuristic",
                    "candidateFunctionCodeRefs": {
                        "refs": [{"targetFunctionRva": 0x5000}],
                    },
                }]
            }]
        },
        GetGameSpeed=_hit(0x1200),
        EGameSpeed_CUT=_hit(0x5000),
    )
    result = assess_cutscene_runtime_evidence(native)

    assert result["candidateFunctions"]["setGameSpeed"]["direct"] == []
    assert result["candidateFunctions"]["setGameSpeed"]["nextHops"] == []
    assert result["candidateFunctions"]["cutSpeedDirectOverlap"] == []
    assert result["candidateFunctions"]["cutSpeedReachableOverlap"] == []
    assert result["implementationReady"] is False
