from games.ff7r.unscanned_name_probe import (
    assess_unscanned_name_evidence,
    rank_unscanned_name_assets,
)


def _asset(name, *strings, objects=()):
    return {
        "asset": name,
        "files": [{
            "suffix": ".uasset",
            "path": name + ".uasset",
            "interestingStrings": [
                {"encoding": "ascii", "offset": index * 16, "text": value}
                for index, value in enumerate(strings)
            ],
            "resolvedExports": list(objects),
        }],
    }


def _native(**counts):
    return {
        "needles": [
            {"needle": needle, "hits": [{}] * count}
            for needle, count in counts.items()
        ]
    }


def _function_hit(needle, function_rva, *next_hops, callers=(), source="pdata"):
    return {
        "needle": needle,
        "hits": [{
            "leaRipXrefs": [{
                "candidateFunctionRva": function_rva,
                "candidateFunctionSource": source,
                "candidateFunctionInboundCodeRefs": {
                    "refs": [
                        {"sourceFunctionRva": caller}
                        for caller in callers
                    ],
                },
                "candidateFunctionCodeRefs": {
                    "refs": [
                        {
                            "targetFunctionRva": target,
                            "targetFunctionInboundCodeRefs": {"refs": []},
                        }
                        for target in next_hops
                    ],
                },
            }],
        }],
    }


def _text_object(name, outer, *, class_name="TextBlock"):
    return {
        "index": 0,
        "packageIndex": 1,
        "objectName": name,
        "objectPath": f"{outer}.{name}",
        "outerPath": outer,
        "className": class_name,
        "classPath": f"/Script/UMG.{class_name}",
    }


def test_presentation_asset_requires_dedicated_battle_or_target_anchor():
    ranked = rank_unscanned_name_assets([
        _asset("UI/EnemyBook", "EnemyBookID", "Text", "Name"),
        _asset("UI/Battle", "BattleEnemyStatusWidget", "TextBlock", "EnemyName"),
    ])

    assert [row["asset"] for row in ranked] == ["UI/Battle"]
    assert ranked[0]["strongPresentationCandidate"] is True


def test_resolved_battle_and_target_text_children_strengthen_each_surface_independently():
    ranked = rank_unscanned_name_assets([
        _asset(
            "UI/BattleEnemyStatusWidget",
            objects=[_text_object("EnemyNameText", "WidgetTree.BattleEnemyStatusWidget")],
        ),
        _asset(
            "UI/BattleTargetNewWidget",
            objects=[_text_object("TargetNameLabel", "WidgetTree.BattleTargetNewWidget")],
        ),
    ])

    battle = next(row for row in ranked if row["asset"].endswith("BattleEnemyStatusWidget"))
    target = next(row for row in ranked if row["asset"].endswith("BattleTargetNewWidget"))
    assert battle["resolvedBattleNameOwnerEvidence"] is True
    assert battle["resolvedBattleNameChildren"][0]["objectName"] == "EnemyNameText"
    assert battle["resolvedAtbTargetOwnerEvidence"] is False
    assert target["resolvedAtbTargetOwnerEvidence"] is True
    assert target["resolvedAtbTargetNameChildren"][0]["objectName"] == "TargetNameLabel"


def test_view_state_and_libra_do_not_count_as_assessed_state_query():
    ranked = rank_unscanned_name_assets([
        _asset("UI/Battle", "BattleEnemyStatusWidget", "Text", "ViewState", "Libra"),
    ])
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1, BattleTargetNewWidget=1, Libra=3),
        candidates=ranked,
    )

    assert result["assessedState"]["candidatePresent"] is False
    assert result["assessedState"]["functionCandidatePresent"] is False
    assert result["assessedState"]["validated"] is False
    assert "assessed-state-query-not-found" in result["blockers"]
    assert "FEndDataTableEnemyBook.ViewState" in result["assessedState"]["explicitlyNotAcceptedAsState"]


def test_query_like_native_string_without_exact_function_stays_weaker_and_blocked():
    result = assess_unscanned_name_evidence(
        native=_native(
            EnemyBookID=1,
            IsEnemyBook=1,
            BattleEnemyStatusWidget=1,
            BattleTargetWidget=1,
        ),
        candidates=[],
    )

    assert result["assessedState"]["candidatePresent"] is True
    assert result["assessedState"]["functionCandidatePresent"] is False
    assert result["assessedState"]["validated"] is False
    assert "assessed-state-query-function-unresolved" in result["blockers"]
    assert "assessed-state-query-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_exact_query_function_is_still_semantically_unvalidated():
    native = {"needles": [
        _function_hit("IsEnemyBook", 0x1000),
        _function_hit("EnemyBookID", 0x2000),
    ]}
    result = assess_unscanned_name_evidence(native=native, candidates=[])

    assert result["assessedState"]["candidatePresent"] is True
    assert result["assessedState"]["functionCandidatePresent"] is True
    assert result["assessedState"]["validated"] is False
    assert "assessed-state-query-function-unresolved" not in result["blockers"]
    assert "assessed-state-query-function-semantics-unvalidated" in result["blockers"]
    assert "assessed-state-query-unvalidated" in result["blockers"]
    assert result["nativeFunctionEvidence"]["IsEnemyBook"]["directPdataFunctions"] == [0x1000]


def test_query_identity_and_both_presentation_surfaces_can_correlate_without_becoming_ready():
    native = {"needles": [
        _function_hit("IsEnemyBook", 0x1000, 0x5000, callers=(0x9000,)),
        _function_hit("EnemyBookID", 0x2000, 0x5000, callers=(0x9000,)),
        _function_hit("ShowBattleEnemyStatusWindow", 0x3000, 0x5000, callers=(0x9000,)),
        _function_hit("ShowBattleTargetIcon", 0x4000, 0x5000, callers=(0x9000,)),
    ]}
    result = assess_unscanned_name_evidence(native=native, candidates=[])
    correlations = result["nativeFunctionCorrelations"]

    assert correlations["queryToEnemyBookLink"] == [0x5000]
    assert correlations["queryToBattleName"] == [0x5000]
    assert correlations["queryToAtbTarget"] == [0x5000]
    assert correlations["queryToEnemyBookLinkCallers"] == [0x9000]
    assert correlations["queryToBattleNameCallers"] == [0x9000]
    assert correlations["queryToAtbTargetCallers"] == [0x9000]
    assert result["assessedState"]["validated"] is False
    assert result["implementationReady"] is False
    assert "assessed-state-query-function-semantics-unvalidated" in result["blockers"]


def test_padding_heuristic_query_owner_cannot_strengthen_state_query():
    native = {"needles": [
        _function_hit("IsEnemyBook", 0x1000, source="padding-heuristic"),
    ]}
    result = assess_unscanned_name_evidence(native=native, candidates=[])

    assert result["assessedState"]["candidatePresent"] is True
    assert result["assessedState"]["functionCandidatePresent"] is False
    assert result["nativeFunctionEvidence"]["IsEnemyBook"]["expandedPdataFunctions"] == []
    assert "assessed-state-query-function-unresolved" in result["blockers"]


def test_both_requested_presentation_paths_are_tracked_independently():
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1),
        candidates=[],
    )

    assert result["presentation"]["battleNamePathCandidate"] is True
    assert result["presentation"]["atbTargetPathCandidate"] is False
    assert "battle-name-text-child-unresolved" in result["blockers"]
    assert "atb-target-presentation-path-unresolved" in result["blockers"]


def test_resolved_children_clear_only_presentation_child_blockers_not_assessed_state():
    ranked = rank_unscanned_name_assets([
        _asset(
            "UI/BattleEnemyStatusWidget",
            objects=[_text_object("EnemyNameText", "WidgetTree.BattleEnemyStatusWidget")],
        ),
        _asset(
            "UI/BattleTargetWidget",
            objects=[_text_object("TargetNameText", "WidgetTree.BattleTargetWidget")],
        ),
    ])
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1),
        candidates=ranked,
    )

    assert result["presentation"]["battleNameTextChildCandidate"] is True
    assert result["presentation"]["atbTargetNameTextChildCandidate"] is True
    assert result["presentation"]["resolvedBattleOwnerCandidates"] == 1
    assert result["presentation"]["resolvedAtbTargetOwnerCandidates"] == 1
    assert "battle-name-text-child-unresolved" not in result["blockers"]
    assert "atb-target-name-text-child-unresolved" not in result["blockers"]
    assert "assessed-state-query-not-found" in result["blockers"]
    assert result["implementationReady"] is False


def test_enemybook_id_plus_is_reported_as_secondary_identity_not_save_state():
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, EnemyBookIDPlus=1),
        candidates=[],
    )
    assert result["enemyBookLink"]["authoritativeAuthoredField"] == "BattleCharaSpec.EnemyBookID"
    assert result["enemyBookLink"]["secondaryAuthoredField"] == "BattleCharaSpec.EnemyBookIDPlus"
    assert result["assessedState"]["validated"] is False


def test_scan_errors_always_block():
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1, BattleTargetWidget=1),
        candidates=[],
        scan_errors=["bad pak"],
    )

    assert "scan-errors" in result["blockers"]
    assert result["implementationReady"] is False
