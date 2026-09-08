from games.ff7r.minimap_runtime_probe import assess_minimap_runtime_evidence


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


def test_minimap_probe_keeps_string_only_evidence_blocked():
    result = assess_minimap_runtime_evidence(
        _native(
            EndFieldOnOffTable_HideNaviMap={"hits": [{}]},
            BPShowNavimap={"hits": [{}]},
            MapJournal={"hits": [{}]},
        )
    )
    assert result["implementationReady"] is False
    assert "hide-state-writer-function-unresolved" in result["blockers"]
    assert "map-button-full-map-function-unresolved" in result["blockers"]


def test_minimap_probe_reports_shared_state_controller_candidate():
    result = assess_minimap_runtime_evidence(
        _native(
            EndFieldOnOffTable_HideNaviMap=_hit(0x1000),
            BPShowNavimap=_hit(0x1000),
            BPHideNavimap=_hit(0x1200),
            EndFieldOnOffTable_ShowMapJournal=_hit(0x2000),
            EndFieldOnOffTable_DisableTouchPad=_hit(0x1000),
        )
    )
    functions = result["candidateFunctions"]
    assert functions["stateDirectOverlap"] == [0x1000]
    assert functions["inputStateDirectOverlap"] == [0x1000]
    assert "central-minimap-state-controller-unvalidated" not in result["blockers"]
    assert "central-minimap-state-controller-next-hop-unvalidated" not in result["blockers"]
    assert "tap-hold-input-to-minimap-link-unvalidated" not in result["blockers"]
    assert "map-button-press-release-semantics-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_keeps_separate_input_and_state_paths_explicit():
    result = assess_minimap_runtime_evidence(
        _native(
            HideNaviMap=_hit(0x1000),
            BPHideNavimap=_hit(0x1000),
            MapJournal=_hit(0x3000),
        )
    )
    assert result["candidateFunctions"]["stateDirectOverlap"] == [0x1000]
    assert result["candidateFunctions"]["inputStateDirectOverlap"] == []
    assert "tap-hold-input-to-minimap-link-unvalidated" in result["blockers"]


def test_minimap_probe_reports_shared_next_hop_without_promoting_it_to_semantics():
    result = assess_minimap_runtime_evidence(
        _native(
            EndFieldOnOffTable_HideNaviMap=_hit(0x1000, 0x5000),
            BPShowNavimap=_hit(0x2000, 0x5000),
            EndFieldOnOffTable_ShowMapJournal=_hit(0x3000, 0x5000),
        )
    )
    functions = result["candidateFunctions"]
    assert functions["stateDirectOverlap"] == []
    assert functions["stateReachableOverlap"] == [0x5000]
    assert functions["inputStateDirectOverlap"] == []
    assert functions["inputStateReachableOverlap"] == [0x5000]
    assert "central-minimap-state-controller-next-hop-unvalidated" in result["blockers"]
    assert "tap-hold-input-next-hop-to-minimap-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_ignores_heuristic_bound_next_hops():
    result = assess_minimap_runtime_evidence(_native(
        EndFieldOnOffTable_HideNaviMap={
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
        BPShowNavimap=_hit(0x5000),
    ))
    functions = result["candidateFunctions"]
    assert functions["hideGate"]["direct"] == []
    assert functions["hideGate"]["nextHops"] == []
    assert functions["stateReachableOverlap"] == []
    assert result["implementationReady"] is False
