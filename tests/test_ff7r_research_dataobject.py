from pathlib import Path

import pytest

from games.ff7r.archive import _with_virtual_assets
from games.ff7r.research_dataobject import (
    ATB_RUNTIME_PROBE_ASSET,
    BETTER_LOCKON_PROBE_ASSET,
    BETTER_SPRINT_PROBE_ASSET,
    CHAPTER3_BENCH_PROBE_ASSET,
    DOG_WHISTLE_PROBE_ASSET,
    READ_ONLY_RESEARCH_ASSETS,
    UNSCANNED_NAME_PROBE_ASSET,
    atb_runtime_result_package,
    better_lockon_result_package,
    better_sprint_result_package,
    chapter3_bench_result_package,
    dog_whistle_result_package,
    unscanned_name_result_package,
)
from games.ff7r.sprint_probe import assess_sprint_evidence
from games.ff7r.storage import save_edits


def _payload(package_result):
    package, source_sha, using_project = package_result
    payload = package.api_payload(source_sha256=source_sha, using_project=using_project)
    assert payload["sourceSha256"] == payload["activeSha256"]
    assert using_project is False
    assert all(not prop["editable"] for prop in payload["properties"])
    return payload


def test_followup_research_rows_are_catalogued():
    catalog = _with_virtual_assets({"assets": [], "textAssets": []})
    assets = {row["asset"] for row in catalog["assets"]}
    assert READ_ONLY_RESEARCH_ASSETS <= assets


def test_atb_runtime_result_is_bounded_read_only_surface():
    payload = _payload(atb_runtime_result_package({
        "implementationReady": False,
        "blockers": ["atb-accumulator-semantics-unvalidated"],
        "nativeNeedleHits": {"ATBValue": 2, "BPGetPlayerDexterity": 1},
        "dataBacked": {"residentCandidateRows": 3, "guardSlots": 6, "abilityCostRows": 20},
        "runtimeResearch": {
            "accumulatorCandidatePresent": True,
            "speedCandidatePresent": True,
            "hitGainCandidatePresent": False,
            "dodgeStateCandidatePresent": True,
        },
        "notes": ["synthetic fixture"],
    }))
    assert payload["asset"] == ATB_RUNTIME_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["ResidentCandidateRows"] == 3
    assert values["GuardSlots"] == 6
    assert values["AccumulatorCandidatePresent"] is True
    assert "ATBValue=2" in values["NativeNeedleHits"]


def test_unscanned_name_result_preserves_candidate_vs_validation_distinction():
    payload = _payload(unscanned_name_result_package({
        "implementationReady": False,
        "blockers": ["assessed-state-query-unvalidated"],
        "assessedState": {
            "candidatePresent": True,
            "validated": False,
            "candidateNeedleHits": {"GetEnemyBook": 1},
        },
        "presentation": {
            "battleNamePathCandidate": True,
            "atbTargetPathCandidate": True,
            "rankedCandidateCount": 1,
            "nativeNeedleHits": {"BattleTargetWidget": 2},
        },
        "candidates": [{"asset": "UI/BattleTarget", "score": 100, "strongPresentationCandidate": True}],
        "scanErrors": [],
        "notes": ["candidate is not a validated hook"],
    }))
    assert payload["asset"] == UNSCANNED_NAME_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["AssessedStateCandidatePresent"] is True
    assert values["AssessedStateValidated"] is False
    assert "UI/BattleTarget" in values["TopCandidates"]


def test_chapter3_bench_result_exposes_exact_object_evidence_counts():
    payload = _payload(chapter3_bench_result_package({
        "matchingCookedFiles": 7,
        "scannedCookedFiles": 7,
        "truncated": False,
        "objectPairedCandidates": [{"path": "slum7.umap"}],
        "pairedCandidates": [{"path": "slum7.umap"}],
        "allEvidenceCandidates": [{
            "score": 3000,
            "pak": "End/Content/Paks/pakchunk0.pak",
            "path": "End/Content/slum7.umap",
            "benchExports": [{"index": 1}],
            "vendingExports": [{"index": 2}],
            "sharedOuterPairs": [{"outerPath": "PersistentLevel"}],
        }],
        "scanErrors": [],
        "notes": ["shared outer is not adjacency proof"],
    }))
    assert payload["asset"] == CHAPTER3_BENCH_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["ObjectPairedCandidates"] == 1
    assert values["SharedOuterPairs"] == 1
    assert "slum7.umap" in values["TopCandidates"]


def test_dog_whistle_result_stays_fail_closed():
    report = {"scanErrors": [], "notes": ["probe"]}
    assessment = {
        "implementationReady": False,
        "blockers": ["writer-cannot-add-item-row"],
        "itemAuthoring": {
            "existingWhistleRowCandidates": 0,
            "whistleNameMapCandidates": ["Whistle"],
            "writerSupportsNewItemRow": False,
        },
        "chapterAward": {
            "addKeyItemPropertyPresent": True,
            "dataAwardPathPlausible": True,
            "writerSupportsArrayAppend": True,
        },
        "runtimeRetarget": {
            "retargetAnchorsPresent": True,
            "needleHits": {"SetTarget": 2},
        },
        "canineCoverage": {"candidateGroups": 4, "battleCharaRows": 6},
        "notes": ["do not repurpose an unrelated item row"],
    }
    payload = _payload(dog_whistle_result_package(report, assessment))
    assert payload["asset"] == DOG_WHISTLE_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["ImplementationReady"] is False
    assert values["WriterCanAppendChapterReward"] is True
    assert values["WriterCanAddItemRow"] is False


def test_better_lockon_result_exposes_ranked_presentation_evidence():
    payload = _payload(better_lockon_result_package({
        "implementationReady": False,
        "candidates": [{
            "asset": "UI/Lockon",
            "score": 9000,
            "strongPresentationCandidate": True,
            "containsDedicatedWidgetAnchor": True,
            "containsLiteralLockOnLabel": True,
        }],
        "native": {"needles": [{"needle": "BattleLockonMarker", "hits": [{}, {}]}]},
        "scanErrors": [],
        "notes": ["exact child property still requires validation"],
    }))
    assert payload["asset"] == BETTER_LOCKON_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["StrongCandidates"] == 1
    assert values["LiteralLabelCandidates"] == 1
    assert "BattleLockonMarker=2" in values["NativeNeedleHits"]


def test_better_sprint_assessment_never_promotes_animation_or_root_motion_hints():
    native = {
        "needles": [
            {
                "needle": "RunToDashBlendInputThreshold",
                "hits": [{"leaRipXrefs": [{"candidateFunctionRva": 0x1000}]}],
            },
            {
                "needle": "DashRootMotionTranslationScale",
                "hits": [{"leaRipXrefs": [{"candidateFunctionRva": 0x2000}]}],
            },
        ]
    }
    candidates = [
        {
            "asset": "End/Content/GameContents/DataObject/InDoorVolume",
            "entryIndex": 1,
            "record": "Sector7",
            "field": "DashRootMotionTranslationScale",
            "value": 1.2,
        },
        {
            "asset": "End/Content/GameContents/DataObject/CharaSpec",
            "entryIndex": 2,
            "record": "Cloud",
            "field": "RootMotionTranslationScale",
            "value": 1.0,
        },
    ]
    result = assess_sprint_evidence(native, candidates)
    assert result["implementationReady"] is False
    assert "authoritative-player-sprint-speed-path-unvalidated" in result["blockers"]
    assert result["nativeNeedleStats"]["RunToDashBlendInputThreshold"]["candidateFunctions"] == 1
    assert result["fieldCandidateCounts"]["DashRootMotionTranslationScale"] == 1
    assert result["fieldCandidateCounts"]["RootMotionTranslationScale"] == 1
    assert any(
        row["symbol"].endswith("RunToDashBlendInputThreshold")
        and row["sprintAuthority"] == "rejected-as-speed-coefficient"
        for row in result["knownContracts"]
    )


def test_better_sprint_result_surface_preserves_scope_risks():
    assessed = assess_sprint_evidence(
        {
            "needles": [{
                "needle": "DashRootMotionTranslationScale",
                "hits": [{"leaRipXrefs": [{"candidateFunctionRva": 0x3000}]}],
            }]
        },
        [{
            "asset": "End/Content/GameContents/DataObject/InDoorVolume",
            "entryIndex": 0,
            "record": "Town",
            "field": "DashRootMotionTranslationScale",
            "value": 0.9,
        }],
    )
    payload = _payload(better_sprint_result_package(assessed))
    assert payload["asset"] == BETTER_SPRINT_PROBE_ASSET
    values = payload["records"][0]["values"]
    assert values["ImplementationReady"] is False
    assert values["DashRootMotionRows"] == 1
    assert "strings=1" in values["NativeEvidence"]
    assert "RunToDashBlendInputThreshold" in values["KnownContracts"]
    assert "authoritative-player-sprint-speed-path-unvalidated" in values["Blockers"]


@pytest.mark.parametrize("asset", sorted(READ_ONLY_RESEARCH_ASSETS))
def test_followup_research_resources_reject_saves(asset):
    with pytest.raises(ValueError, match="research probes are read-only"):
        save_edits(
            Path("."), Path("."), Path("."), {}, asset,
            source_sha256="source", active_sha256="active", edits=[],
        )
