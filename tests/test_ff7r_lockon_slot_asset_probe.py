from games.ff7r.lockon_slot_asset_probe import (
    canonical_cooked_package_path,
    correlate_marker_slots_to_assets,
    plan_red_reticle_rewrites,
)


SLOTS = (
    "BattleLockonMarker00Widget",
    "BattleLockonMarker01Widget",
    "BattleLockonMarker02Widget",
)


def _slot_research(*paths):
    return {
        "uniqueSlotValues": {
            slot: (
                {"assetPath": path, "subPath": ""}
                if path is not None else None
            )
            for slot, path in zip(SLOTS, paths)
        },
    }


def _candidate(asset, *, linear=False, value=None, refs=None, dedicated=True):
    linear_refs = []
    if refs is not None:
        linear_refs = list(refs)
        linear = bool(linear_refs)
    elif linear:
        linear_refs.append({
            "name": "ColorAndOpacity",
            "objectName": "BattleLockonMarker",
            "className": "EndBattleLockonMarkerIcon",
            "valueOffset": 49,
            "valueEndOffset": 65,
            "linearColorValue": value or {
                "r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0,
            },
        })
    return {
        "asset": asset,
        "score": 100,
        "containsDedicatedWidgetAnchor": dedicated,
        "resolvedDedicatedOwnerEvidence": dedicated,
        "serializedTintPropertyEvidence": linear,
        "serializedTintValueLayoutEvidence": linear,
        "serializedLinearColorTintValueEvidence": linear,
        "serializedLinearColorTintRefs": linear_refs,
    }


def _blue(value, *, name="ColorAndOpacity"):
    return {
        "name": name,
        "objectName": "BattleLockonMarker",
        "className": "EndBattleLockonMarkerIcon",
        "valueOffset": 49,
        "valueEndOffset": 65,
        "linearColorValue": value,
    }


def test_canonical_package_path_joins_game_and_end_content_roots_without_leaf_guessing():
    expected = "ui/battle/wbp_marker0"
    assert canonical_cooked_package_path(
        "/Game/UI/Battle/WBP_Marker0.WBP_Marker0_C"
    ) == expected
    assert canonical_cooked_package_path(
        "End/Content/UI/Battle/WBP_Marker0"
    ) == expected
    assert canonical_cooked_package_path(
        "UI/Battle/WBP_Marker0.uasset"
    ) == expected
    assert canonical_cooked_package_path(
        "BlueprintGeneratedClass'/Game/UI/Battle/WBP_Marker0.WBP_Marker0_C'"
    ) == expected
    assert canonical_cooked_package_path(
        "/Game/UI/Other/WBP_Marker0.WBP_Marker0_C"
    ) != expected


def test_three_unique_softclass_paths_correlate_to_exact_cooked_assets_and_keep_semantics_unvalidated():
    research = _slot_research(
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        "/Game/UI/WBP_Marker1.WBP_Marker1_C",
        "/Game/UI/WBP_Marker2.WBP_Marker2_C",
    )
    candidates = [
        _candidate("End/Content/UI/WBP_Marker0", linear=True),
        _candidate("UI/WBP_Marker1", linear=True, value={
            "r": 0.1, "g": 0.4, "b": 1.0, "a": 1.0,
        }),
        _candidate("/Game/UI/WBP_Marker2", linear=False),
    ]

    result = correlate_marker_slots_to_assets(research, candidates)

    assert result["implementationReady"] is False
    assert result["correlatedSlotCount"] == 3
    assert result["allSlotsUniquelyCorrelated"] is True
    assert result["correlatedLinearColorSlotCount"] == 2
    assert result["slotToMarkerTypeMappingValidated"] is False
    assert result["activeBlueReticleSlotValidated"] is False
    assert result["redReticleOwnerValidated"] is False
    slot1 = result["slotCorrelations"]["BattleLockonMarker01Widget"]
    assert slot1["status"] == "unique-exact-package-match"
    assert slot1["uniqueCookedAsset"]["asset"] == "UI/WBP_Marker1"
    assert slot1["uniqueCookedAssetWithLinearColor"] is True
    assert slot1["uniqueCookedAsset"]["serializedLinearColorTintRefs"][0][
        "linearColorValue"
    ] == {"r": 0.1, "g": 0.4, "b": 1.0, "a": 1.0}
    assert "marker-slot-to-marker-type-semantics-unvalidated" in result["blockers"]
    assert "active-blue-reticle-slot-unvalidated" in result["blockers"]


def test_duplicate_exact_package_candidates_are_ambiguous_not_silently_ranked():
    research = _slot_research(
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        None,
        None,
    )
    candidates = [
        _candidate("UI/WBP_Marker0", linear=True),
        _candidate("End/Content/UI/WBP_Marker0", linear=True),
    ]

    result = correlate_marker_slots_to_assets(research, candidates)
    slot0 = result["slotCorrelations"]["BattleLockonMarker00Widget"]

    assert slot0["status"] == "ambiguous-cooked-asset-match"
    assert slot0["matchCount"] == 2
    assert slot0["uniqueCookedAsset"] is None
    assert result["ambiguousSlotCount"] == 1
    assert result["allSlotsUniquelyCorrelated"] is False
    assert "marker-slot-cooked-assets-ambiguous" in result["blockers"]


def test_same_leaf_name_in_different_directory_never_counts_as_match():
    research = _slot_research(
        "/Game/UI/Battle/WBP_Marker0.WBP_Marker0_C",
        None,
        None,
    )
    result = correlate_marker_slots_to_assets(
        research,
        [_candidate("UI/Other/WBP_Marker0", linear=True)],
    )

    slot0 = result["slotCorrelations"]["BattleLockonMarker00Widget"]
    assert slot0["status"] == "cooked-asset-not-found"
    assert slot0["matchCount"] == 0
    assert result["correlatedSlotCount"] == 0


def test_nonunique_upstream_slot_value_cannot_be_recovered_by_candidate_guessing():
    research = _slot_research(
        None,
        "/Game/UI/WBP_Marker1.WBP_Marker1_C",
        "/Game/UI/WBP_Marker2.WBP_Marker2_C",
    )
    result = correlate_marker_slots_to_assets(
        research,
        [
            _candidate("UI/WBP_Marker0", linear=True),
            _candidate("UI/WBP_Marker1", linear=True),
            _candidate("UI/WBP_Marker2", linear=True),
        ],
    )

    slot0 = result["slotCorrelations"]["BattleLockonMarker00Widget"]
    assert slot0["status"] == "slot-value-unresolved"
    assert slot0["uniqueCookedAsset"] is None
    assert result["correlatedSlotCount"] == 2
    assert result["unresolvedSlotCount"] == 1
    assert result["allSlotsUniquelyCorrelated"] is False


def test_red_reticle_plan_rewrites_all_three_unique_blue_dedicated_markers_without_slot_type_guessing():
    research = _slot_research(
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        "/Game/UI/WBP_Marker1.WBP_Marker1_C",
        "/Game/UI/WBP_Marker2.WBP_Marker2_C",
    )
    candidates = [
        _candidate("UI/WBP_Marker0", refs=[_blue({"r": 0.05, "g": 0.25, "b": 1.0, "a": 1.0})]),
        _candidate("UI/WBP_Marker1", refs=[_blue({"r": 0.10, "g": 0.40, "b": 1.25, "a": 0.8})]),
        _candidate("UI/WBP_Marker2", refs=[_blue({"r": 0.00, "g": 0.10, "b": 0.75, "a": 0.5})]),
    ]
    correlation = correlate_marker_slots_to_assets(research, candidates)

    plan = plan_red_reticle_rewrites(correlation)

    assert plan["implementationReady"] is True
    assert plan["redReticleOwnerValidated"] is True
    assert plan["rewriteAllNumberedMarkerSlots"] is True
    assert plan["slotToMarkerTypeMappingRequired"] is False
    assert len(plan["rewritePlan"]) == 3
    assert [row["slot"] for row in plan["rewritePlan"]] == list(SLOTS)
    assert plan["rewritePlan"][0]["replacementRgba"] == [1.0, 0.0, 0.0, 1.0]
    assert plan["rewritePlan"][1]["replacementRgba"] == [1.25, 0.0, 0.0, 0.8]
    assert plan["rewritePlan"][2]["replacementRgba"] == [0.75, 0.0, 0.0, 0.5]


def test_red_reticle_plan_rejects_white_or_ambiguous_blue_colors():
    research = _slot_research(
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        "/Game/UI/WBP_Marker1.WBP_Marker1_C",
        "/Game/UI/WBP_Marker2.WBP_Marker2_C",
    )
    candidates = [
        _candidate("UI/WBP_Marker0", refs=[_blue({"r": 0.05, "g": 0.25, "b": 1.0, "a": 1.0})]),
        _candidate("UI/WBP_Marker1", refs=[_blue({"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0})]),
        _candidate("UI/WBP_Marker2", refs=[
            _blue({"r": 0.0, "g": 0.1, "b": 0.8, "a": 1.0}),
            _blue({"r": 0.1, "g": 0.2, "b": 0.9, "a": 1.0}, name="TintColor"),
        ]),
    ]
    correlation = correlate_marker_slots_to_assets(research, candidates)

    plan = plan_red_reticle_rewrites(correlation)

    assert plan["implementationReady"] is False
    assert plan["rewritePlan"] == []
    assert "BattleLockonMarker01Widget:expected-one-blue-linearcolor-found-0" in plan["blockers"]
    assert "BattleLockonMarker02Widget:expected-one-blue-linearcolor-found-2" in plan["blockers"]


def test_red_reticle_plan_rejects_generic_or_shared_assets_even_if_blue():
    research = _slot_research(
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        "/Game/UI/WBP_Marker0.WBP_Marker0_C",
        "/Game/UI/WBP_Marker2.WBP_Marker2_C",
    )
    candidates = [
        _candidate("UI/WBP_Marker0", refs=[_blue({"r": 0.0, "g": 0.1, "b": 1.0, "a": 1.0})]),
        _candidate("UI/WBP_Marker2", refs=[_blue({"r": 0.0, "g": 0.1, "b": 1.0, "a": 1.0})], dedicated=False),
    ]
    correlation = correlate_marker_slots_to_assets(research, candidates)

    plan = plan_red_reticle_rewrites(correlation)

    assert plan["implementationReady"] is False
    assert plan["rewritePlan"] == []
    assert any("duplicate-marker-asset" in blocker for blocker in plan["blockers"])
    assert any("dedicated-lockon-anchor-unproven" in blocker for blocker in plan["blockers"])
