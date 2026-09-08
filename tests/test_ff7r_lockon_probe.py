from games.ff7r.lockon_probe import (
    assess_lock_state_evidence,
    assess_marker_slot_evidence,
    rank_lockon_assets,
)


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


def _serialized_lockon_asset(
    name="UI/SerializedLockon", *, property_name="ColorAndOpacity", dedicated=True,
    mapping_trusted=True, header_plausible=True,
):
    asset = _asset(name)
    object_name = "BattleLockonMarker" if dedicated else "GenericTargetImage"
    class_name = "EndBattleLockonMarkerIcon" if dedicated else "Image"
    asset["serializedExportEvidence"] = {
        "mappingTrusted": mapping_trusted,
        "mappingReason": (
            "serial-offset-minus-total-header-size" if mapping_trusted
            else "total-header-size-does-not-match-uasset-length"
        ),
        "refs": [{
            "objectName": object_name,
            "objectPath": f"WidgetTree.{object_name}",
            "outerPath": "WidgetTree",
            "className": class_name,
            "classPath": f"/Script/EndGame.{class_name}",
            "name": property_name,
            "propertyType": "StructProperty",
            "propertyTagLike": True,
            "propertyTagHeaderPlausible": header_plausible,
            "declaredValueSize": 16 if header_plausible else None,
            "arrayIndex": 0 if header_plausible else None,
        }],
    }
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


def test_marker_slot_string_is_research_evidence_not_reticle_ownership():
    ranked = rank_lockon_assets([
        _asset("UI/Settings", "BattleLockonMarker01Widget"),
    ])

    assert len(ranked) == 1
    assert ranked[0]["containsMarkerSlotAnchor"] is True
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


def test_serialized_dedicated_tint_property_outranks_string_only_candidate():
    ranked = rank_lockon_assets([
        _asset("UI/StringOnly", "EndBattleLockonMarkerIcon", "ColorAndOpacity"),
        _serialized_lockon_asset(),
    ])

    assert ranked[0]["asset"] == "UI/SerializedLockon"
    assert ranked[0]["serializedExportMappingTrusted"] is True
    assert ranked[0]["serializedDedicatedPropertyRefs"]
    assert ranked[0]["serializedTintPropertyEvidence"] is True
    assert ranked[0]["serializedPlausibleTintTagEvidence"] is True
    assert ranked[0]["strongPresentationCandidate"] is True


def test_untrusted_serialized_mapping_cannot_promote_injected_refs():
    ranked = rank_lockon_assets([
        _serialized_lockon_asset(mapping_trusted=False),
    ])

    assert ranked == []


def test_serialized_property_on_unrelated_widget_is_not_promoted():
    ranked = rank_lockon_assets([
        _serialized_lockon_asset("UI/GenericSerialized", dedicated=False),
    ])

    assert ranked == []


def test_serialized_tint_without_plausible_generic_header_stays_weak():
    ranked = rank_lockon_assets([
        _serialized_lockon_asset(header_plausible=False),
    ])

    assert len(ranked) == 1
    assert ranked[0]["serializedTintPropertyEvidence"] is True
    assert ranked[0]["serializedPlausibleTintTagEvidence"] is False
    assert ranked[0]["strongPresentationCandidate"] is False


def test_serialized_dedicated_non_tint_property_does_not_claim_tint_semantics():
    ranked = rank_lockon_assets([
        _serialized_lockon_asset(property_name="Visibility"),
    ])

    assert len(ranked) == 1
    assert ranked[0]["serializedDedicatedPropertyRefs"]
    assert ranked[0]["serializedTintPropertyRefs"] == []
    assert ranked[0]["serializedTintPropertyEvidence"] is False
    assert ranked[0]["serializedPlausibleTintTagEvidence"] is False
    assert ranked[0]["strongPresentationCandidate"] is False


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


def test_marker_slots_preserve_order_without_claiming_type_mapping():
    result = assess_marker_slot_evidence(_native(
        BattleLockonMarker00Widget=1,
        BattleLockonMarker01Widget=2,
        BattleLockonMarker02Widget=1,
    ))

    assert result["allSlotAnchorsPresent"] is True
    assert result["slotOrder"] == [
        "BattleLockonMarker00Widget",
        "BattleLockonMarker01Widget",
        "BattleLockonMarker02Widget",
    ]
    assert result["markerTypeOrder"] == ["Default", "Wimp", "Libra"]
    assert result["slotToMarkerTypeMappingValidated"] is False


def test_partial_marker_slots_never_claim_mapping():
    result = assess_marker_slot_evidence(_native(BattleLockonMarker00Widget=1))

    assert result["allSlotAnchorsPresent"] is False
    assert result["slotToMarkerTypeMappingValidated"] is False
