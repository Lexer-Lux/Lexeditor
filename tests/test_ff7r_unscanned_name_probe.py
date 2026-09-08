from games.ff7r.unscanned_name_probe import (
    assess_unscanned_name_evidence,
    rank_unscanned_name_assets,
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


def test_presentation_asset_requires_dedicated_battle_or_target_anchor():
    ranked = rank_unscanned_name_assets([
        _asset("UI/EnemyBook", "EnemyBookID", "Text", "Name"),
        _asset("UI/Battle", "BattleEnemyStatusWidget", "TextBlock", "EnemyName"),
    ])

    assert [row["asset"] for row in ranked] == ["UI/Battle"]
    assert ranked[0]["strongPresentationCandidate"] is True


def test_view_state_and_libra_do_not_count_as_assessed_state_query():
    ranked = rank_unscanned_name_assets([
        _asset("UI/Battle", "BattleEnemyStatusWidget", "Text", "ViewState", "Libra"),
    ])
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1, BattleTargetNewWidget=1, Libra=3),
        candidates=ranked,
    )

    assert result["assessedState"]["candidatePresent"] is False
    assert result["assessedState"]["validated"] is False
    assert "assessed-state-query-not-found" in result["blockers"]
    assert "FEndDataTableEnemyBook.ViewState" in result["assessedState"]["explicitlyNotAcceptedAsState"]


def test_query_like_native_string_is_still_unvalidated_and_not_ready():
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
    assert result["assessedState"]["validated"] is False
    assert "assessed-state-query-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_both_requested_presentation_paths_are_tracked_independently():
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1),
        candidates=[],
    )

    assert result["presentation"]["battleNamePathCandidate"] is True
    assert result["presentation"]["atbTargetPathCandidate"] is False
    assert "atb-target-presentation-path-unresolved" in result["blockers"]


def test_scan_errors_always_block():
    result = assess_unscanned_name_evidence(
        native=_native(EnemyBookID=1, BattleEnemyStatusWidget=1, BattleTargetWidget=1),
        candidates=[],
        scan_errors=["bad pak"],
    )

    assert "scan-errors" in result["blockers"]
    assert result["implementationReady"] is False
