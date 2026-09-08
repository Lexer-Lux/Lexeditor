from games.ff7r.minimap_runtime_probe import assess_minimap_runtime_evidence


def _hit(function_rva):
    return {
        "hits": [
            {
                "leaRipXrefs": [
                    {"candidateFunctionRva": function_rva},
                ]
            }
        ]
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
            KeyboardToggleMap={"hits": [{}]},
        )
    )
    assert result["implementationReady"] is False
    assert "hide-state-writer-function-unresolved" in result["blockers"]
    assert "map-button-full-map-function-unresolved" in result["blockers"]
    assert "native-minimap-toggle-input-function-unresolved" in result["blockers"]


def test_minimap_probe_reports_shared_state_controller_candidate():
    result = assess_minimap_runtime_evidence(
        _native(
            EndFieldOnOffTable_HideNaviMap=_hit(0x1000),
            BPShowNavimap=_hit(0x1000),
            BPHideNavimap=_hit(0x1200),
            EndFieldOnOffTable_ShowMapJournal=_hit(0x2000),
            EndFieldOnOffTable_DisableTouchPad=_hit(0x1000),
            KeyboardMapMenu=_hit(0x2000),
            KeyboardToggleMap=_hit(0x1000),
        )
    )
    functions = result["candidateFunctions"]
    assert functions["stateOverlap"] == [0x1000]
    assert functions["inputStateOverlap"] == [0x1000]
    assert functions["mapMenuInput"] == [0x1000, 0x2000]
    assert functions["nativeToggleInput"] == [0x1000]
    assert functions["toggleStateOverlap"] == [0x1000]
    assert "central-minimap-state-controller-unvalidated" not in result["blockers"]
    assert "tap-hold-input-to-minimap-link-unvalidated" not in result["blockers"]
    assert "native-minimap-toggle-input-anchor-unresolved" not in result["blockers"]
    assert "native-minimap-toggle-input-function-unresolved" not in result["blockers"]
    assert "native-toggle-input-to-state-link-unvalidated" not in result["blockers"]
    assert "map-button-press-release-semantics-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_minimap_probe_keeps_separate_input_and_state_paths_explicit():
    result = assess_minimap_runtime_evidence(
        _native(
            HideNaviMap=_hit(0x1000),
            BPHideNavimap=_hit(0x1000),
            MapJournal=_hit(0x3000),
            KeyboardToggleMap=_hit(0x4000),
        )
    )
    assert result["candidateFunctions"]["stateOverlap"] == [0x1000]
    assert result["candidateFunctions"]["inputStateOverlap"] == []
    assert result["candidateFunctions"]["toggleStateOverlap"] == []
    assert "tap-hold-input-to-minimap-link-unvalidated" in result["blockers"]
    assert "native-toggle-input-to-state-link-unvalidated" in result["blockers"]


def test_missing_native_toggle_option_anchor_is_explicit_blocker():
    result = assess_minimap_runtime_evidence(
        _native(
            HideNavimap=_hit(0x1000),
            BPShowNavimap=_hit(0x1000),
            KeyboardMapMenu=_hit(0x2000),
        )
    )
    assert result["toggleInputNeedleHits"]["KeyboardToggleMap"] == 0
    assert result["candidateFunctions"]["nativeToggleInput"] == []
    assert "native-minimap-toggle-input-anchor-unresolved" in result["blockers"]
