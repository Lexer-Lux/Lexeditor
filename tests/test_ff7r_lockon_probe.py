from games.ff7r.lockon_probe import assess_lock_state_evidence, rank_lockon_assets


def _asset(name, *strings):
    return {
        "asset": name,
        "files": [{
            "suffix": ".uasset",
            "path": name + ".uasset",
            "interestingStrings": [
                {"encoding": "ascii", "offset": index * 16, "text": value}
                for index, value in enumerate(strings)
            ],
        }],
    }


def _native(**counts):
    return {
        "needles": [
            {"needle": needle, "hits": [{}] * count}
            for needle, count in counts.items()
        ]
    }


def _resolved_lockon_asset(name="UI/ResolvedLockon"):
    asset = _asset(name, "ColorAndOpacity")
    asset["files"][0]["resolvedExports"] = [
        {
            "index": 0,
            "packageIndex": 1,
            "objectName": "BattleLockonMarker",
            "objectPath": "WidgetTree.BattleLockonMarker",
            "outerPath": "WidgetTree",
            "className": "EndBattleLockonMarkerIcon",
            "classPath": "/Script/EndGame.EndBattleLockonMarkerIcon",
        },
        {
            "index": 1,
            "packageIndex": 2,
            "objectName": "LockOnText",
            "objectPath": "WidgetTree.BattleLockonMarker.LockOnText",
            "outerPath": "WidgetTree.BattleLockonMarker",
            "className": "TextBlock",
            "classPath": "/Script/UMG.TextBlock",
        },
    ]
    return asset


def test_dedicated_widget_with_presentation_fields_ranks_above_generic_anchor():
    ranked = rank_lockon_assets([
        _asset("UI/Generic", "BPShowBattleLockonMarkerIcon"),
        _asset("UI/Lockon", "EndBattleLockonMarkerIcon", "ColorAndOpacity", "Visibility"),
    ])

    assert [row["asset"] for row in ranked] == ["UI/Lockon", "UI/Generic"]
    assert ranked[0]["strongPresentationCandidate"] is True
    assert ranked[0]["containsDedicatedWidgetAnchor"] is True


def test_literal_label_is_not_inferred_from_class_name():
    ranked = rank_lockon_assets([
        _asset("UI/ClassOnly", "EndBattleLockonMarkerIcon", "Tint"),
        _asset("UI/Label", "BattleLockonMarker", "LOCK ON", "Brush"),
    ])

    class_only = next(row for row in ranked if row["asset"] == "UI/ClassOnly")
    label = next(row for row in ranked if row["asset"] == "UI/Label")
    assert class_only["containsLiteralLockOnLabel"] is False
    assert label["containsLiteralLockOnLabel"] is True
    assert label["score"] > class_only["score"]


def test_unrelated_target_ui_is_not_promoted():
    ranked = rank_lockon_assets([
        _asset("UI/Target", "BattleTargetWidget", "Color", "Text", "Visibility"),
    ])

    assert ranked == []


def test_target_state_asset_is_research_evidence_but_not_dedicated_lockon_owner():
    ranked = rank_lockon_assets([
        _asset("UI/BattleTarget", "ShowBattleTargetIcon", "EEndMenuBattleTargetState", "LockedEnabled"),
    ])

    assert len(ranked) == 1
    assert ranked[0]["lockStateAnchorHits"]
    assert ranked[0]["containsDedicatedWidgetAnchor"] is False
    assert ranked[0]["strongPresentationCandidate"] is False


def test_ranking_is_deterministic_for_equal_evidence():
    ranked = rank_lockon_assets([
        _asset("UI/Zed", "BattleLockonMarker"),
        _asset("UI/Alpha", "BattleLockonMarker"),
    ])

    assert [row["asset"] for row in ranked] == ["UI/Alpha", "UI/Zed"]


def test_resolved_widget_owner_outranks_printable_string_only_candidate():
    ranked = rank_lockon_assets([
        _asset("UI/StringOnly", "EndBattleLockonMarkerIcon", "ColorAndOpacity", "Visibility"),
        _resolved_lockon_asset(),
    ])

    assert ranked[0]["asset"] == "UI/ResolvedLockon"
    assert ranked[0]["resolvedDedicatedOwnerEvidence"] is True
    assert ranked[0]["resolvedLabelChildEvidence"] is True
    assert ranked[0]["strongPresentationCandidate"] is True


def test_literal_label_without_resolved_owner_does_not_invent_object_ownership():
    ranked = rank_lockon_assets([
        _asset("UI/LabelOnly", "BattleLockonMarker", "LOCK ON", "ColorAndOpacity"),
    ])

    assert len(ranked) == 1
    assert ranked[0]["containsLiteralLockOnLabel"] is True
    assert ranked[0]["resolvedDedicatedOwnerEvidence"] is False
    assert ranked[0]["resolvedLabelChildEvidence"] is False


def test_show_target_icon_plus_state_enum_is_strong_lead_but_still_unvalidated():
    result = assess_lock_state_evidence(_native(
        ShowBattleTargetIcon=1,
        EEndMenuBattleTargetState=1,
        LockedEnabled=1,
        LockedDisabled=1,
        OutLockedEnabled=1,
    ))

    assert result["reflectedContractPresent"] is True
    assert result["lockedEnumeratorEvidence"] is True
    assert result["lockedStateNeedleHits"]["LockedEnabled"] == 1
    assert result["validatedAsIssuePredicate"] is False


def test_partial_target_state_evidence_never_claims_contract():
    result = assess_lock_state_evidence(_native(ShowBattleTargetIcon=1))

    assert result["reflectedContractPresent"] is False
    assert result["validatedAsIssuePredicate"] is False
