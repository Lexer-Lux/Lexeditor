from games.ff7r.minimap_runtime_probe import assess_minimap_runtime_evidence


def _inbound(*callers):
    return {
        "refs": [
            {"sourceFunctionRva": caller, "kind": "call-rel32"}
            for caller in callers
        ]
    }


def _hit(function_rva, *next_hops, callers=(), next_hop_callers=()):
    xref = {
        "candidateFunctionRva": function_rva,
        "candidateFunctionSource": "pdata",
    }
    if callers:
        xref["candidateFunctionInboundCodeRefs"] = _inbound(*callers)
    if next_hops:
        xref["candidateFunctionCodeRefs"] = {
            "refs": [
                {
                    "targetFunctionRva": target,
                    "kind": "call-rel32",
                    **(
                        {"targetFunctionInboundCodeRefs": _inbound(*next_hop_callers)}
                        if next_hop_callers else {}
                    ),
                }
                for target in next_hops
            ]
        }
    return {"hits": [{"leaRipXrefs": [xref]}]}


def _native(**rows):
    return {
        "needles": [
            {"needle": needle, **payload}
            for needle, payload in rows.items()
        ]
    }


def test_minimap_probe_keeps_string_only_evidence_blocked():
    result = assess_minimap_runtime_evidence(_native(
        EndFieldOnOffTable_HideNaviMap={"hits": [{}]},
        BPShowNavimap={"hits": [{}]},
        MapJournal={"hits": [{}]},
        KeyboardToggleMap={"hits": [{}]},
    ))
    assert result["implementationReady"] is False
    assert "hide-state-writer-function-unresolved" in result["blockers"]
    assert "native-map-menu-input-anchor-unresolved" in result["blockers"]
    assert "map-button-full-map-function-unresolved" in result["blockers"]
    assert "native-minimap-toggle-input-function-unresolved" in result["blockers"]


def test_minimap_probe_reports_shared_state_and_native_toggle_candidate():
    result = assess_minimap_runtime_evidence(_native(
        EndFieldOnOffTable_HideNaviMap=_hit(0x1000),
        BPShowNavimap=_hit(0x1000),
        BPHideNavimap=_hit(0x1200),
        EndFieldOnOffTable_ShowMapJournal=_hit(0x2000),
        EndFieldOnOffTable_DisableTouchPad=_hit(0x1000),
        KeyboardMapMenu=_hit(0x2000),
        KeyboardToggleMap=_hit(0x1000),
    ))
    functions = result["candidateFunctions"]
    assert functions["stateDirectOverlap"] == [0x1000]
    assert functions["inputStateDirectOverlap"] == [0x1000]
    assert functions["toggleStateDirectOverlap"] == [0x1000]
    assert functions["stateOverlap"] == [0x1000]
    assert functions["nativeToggleInput"]["direct"] == [0x1000]
    assert functions["mapMenuInput"]["direct"] == [0x1000, 0x2000]
    assert functions["mapMenuSupport"]["direct"] == [0x1000, 0x2000]
    assert functions["mapMenuAction"]["direct"] == [0x2000]
    assert result["mapMenuActionNeedleHits"]["KeyboardMapMenu"] == 1
    assert "native-map-menu-input-anchor-unresolved" not in result["blockers"]
    assert "map-button-full-map-function-unresolved" not in result["blockers"]
    assert "central-minimap-state-controller-unvalidated" not in result["blockers"]
    assert "central-minimap-state-controller-next-hop-unvalidated" not in result["blockers"]
    assert "tap-hold-input-to-minimap-link-unvalidated" not in result["blockers"]
    assert "native-minimap-toggle-input-anchor-unresolved" not in result["blockers"]
    assert "native-toggle-input-to-state-link-unvalidated" not in result["blockers"]
    assert "map-button-press-release-semantics-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_generic_map_journal_and_input_gates_cannot_substitute_for_keyboard_map_menu():
    result = assess_minimap_runtime_evidence(_native(
        HideNaviMap=_hit(0x1000),
        BPHideNavimap=_hit(0x1000),
        EndFieldOnOffTable_ShowMapJournal=_hit(0x1000),
        EndFieldOnOffTable_DisableTouchPad=_hit(0x1000),
        MapJournal=_hit(0x1000),
        KeyboardToggleMap=_hit(0x1000),
    ))

    functions = result["candidateFunctions"]
    assert functions["mapMenuSupport"]["direct"] == [0x1000]
    assert functions["mapMenuAction"]["direct"] == []
    assert functions["mapInput"]["direct"] == [0x1000]
    assert "native-map-menu-input-anchor-unresolved" in result["blockers"]
    assert "map-button-full-map-function-unresolved" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_keeps_separate_input_and_state_paths_explicit():
    result = assess_minimap_runtime_evidence(_native(
        HideNaviMap=_hit(0x1000),
        BPHideNavimap=_hit(0x1000),
        MapJournal=_hit(0x3000),
        KeyboardToggleMap=_hit(0x4000),
    ))
    assert result["candidateFunctions"]["stateDirectOverlap"] == [0x1000]
    assert result["candidateFunctions"]["inputStateDirectOverlap"] == []
    assert result["candidateFunctions"]["toggleStateDirectOverlap"] == []
    assert "native-map-menu-input-anchor-unresolved" in result["blockers"]
    assert "map-button-full-map-function-unresolved" in result["blockers"]
    assert "tap-hold-input-to-minimap-link-unvalidated" in result["blockers"]
    assert "native-toggle-input-to-state-link-unvalidated" in result["blockers"]


def test_missing_native_toggle_option_anchor_is_explicit_blocker():
    result = assess_minimap_runtime_evidence(_native(
        HideNavimap=_hit(0x1000),
        BPShowNavimap=_hit(0x1000),
        KeyboardMapMenu=_hit(0x2000),
    ))
    assert result["toggleInputNeedleHits"]["KeyboardToggleMap"] == 0
    assert result["candidateFunctions"]["nativeToggleInput"]["direct"] == []
    assert "native-minimap-toggle-input-anchor-unresolved" in result["blockers"]


def test_minimap_probe_reports_shared_next_hop_without_promoting_it_to_semantics():
    result = assess_minimap_runtime_evidence(_native(
        EndFieldOnOffTable_HideNaviMap=_hit(0x1000, 0x5000),
        BPShowNavimap=_hit(0x2000, 0x5000),
        EndFieldOnOffTable_ShowMapJournal=_hit(0x3000, 0x5000),
        KeyboardMapMenu=_hit(0x3500, 0x5000),
        KeyboardToggleMap=_hit(0x4000, 0x5000),
    ))
    functions = result["candidateFunctions"]
    assert functions["stateDirectOverlap"] == []
    assert functions["stateReachableOverlap"] == [0x5000]
    assert functions["inputStateDirectOverlap"] == []
    assert functions["inputStateReachableOverlap"] == [0x5000]
    assert functions["mapMenuStateDirectOverlap"] == []
    assert functions["mapMenuStateReachableOverlap"] == [0x5000]
    assert functions["toggleStateDirectOverlap"] == []
    assert functions["toggleStateReachableOverlap"] == [0x5000]
    assert "central-minimap-state-controller-next-hop-unvalidated" in result["blockers"]
    assert "tap-hold-input-next-hop-to-minimap-unvalidated" in result["blockers"]
    assert "native-map-menu-input-next-hop-to-state-unvalidated" in result["blockers"]
    assert "native-toggle-input-next-hop-to-state-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_reports_shared_exact_inbound_caller_without_promoting_it_to_hook():
    result = assess_minimap_runtime_evidence(_native(
        HideNaviMap=_hit(0x1000, callers=(0x9000,)),
        BPShowNavimap=_hit(0x2000, callers=(0x9000,)),
        KeyboardMapMenu=_hit(0x3000, callers=(0x9000,)),
        KeyboardToggleMap=_hit(0x4000, callers=(0x9000,)),
    ))

    functions = result["candidateFunctions"]
    assert functions["stateDirectOverlap"] == []
    assert functions["inputStateDirectOverlap"] == []
    assert functions["inputStateCallerOverlap"] == [0x9000]
    assert functions["mapMenuStateCallerOverlap"] == [0x9000]
    assert functions["toggleStateCallerOverlap"] == [0x9000]
    assert functions["mapMenuToggleCallerOverlap"] == [0x9000]
    assert functions["mapMenuAction"]["directCallers"] == [0x9000]
    assert functions["nativeToggleInput"]["directCallers"] == [0x9000]
    assert "tap-hold-input-to-minimap-link-unvalidated" in result["blockers"]
    assert "map-button-press-release-semantics-unvalidated" in result["blockers"]
    assert "player-choice-persistence-write-interception-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_ignores_heuristic_bound_next_hops_and_inbound_callers():
    result = assess_minimap_runtime_evidence(_native(
        EndFieldOnOffTable_HideNaviMap={
            "hits": [{"leaRipXrefs": [{
                "candidateFunctionRva": 0x1000,
                "candidateFunctionSource": "padding-heuristic",
                "candidateFunctionInboundCodeRefs": _inbound(0x9000),
                "candidateFunctionCodeRefs": {"refs": [{"targetFunctionRva": 0x5000}]},
            }]}]
        },
        BPShowNavimap=_hit(0x5000),
        KeyboardMapMenu=_hit(0x5500, 0x5000),
        KeyboardToggleMap=_hit(0x6000, 0x5000),
    ))
    functions = result["candidateFunctions"]
    assert functions["hideGate"]["direct"] == []
    assert functions["hideGate"]["nextHops"] == []
    assert functions["hideGate"]["directCallers"] == []
    assert functions["stateReachableOverlap"] == []
    assert functions["inputStateCallerOverlap"] == []
    assert result["implementationReady"] is False
