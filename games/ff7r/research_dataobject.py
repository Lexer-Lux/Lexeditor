"""Read-only DataObject-shaped surfaces for unresolved FF7R follow-up research.

The underlying probes intentionally do not mutate game data.  These adapters make
that installed-build evidence available through Lexeditor's existing Game Data UI
without promoting string/xref/cooked-asset candidates into validated hooks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .dataobject import Entry
from .runtime_dataobject import VirtualPackage, VirtualProperty


ATB_RUNTIME_PROBE_ASSET = "Lexeditor/ATBRuntimeProbe"
UNSCANNED_NAME_PROBE_ASSET = "Lexeditor/UnscannedNameProbe"
CHAPTER3_BENCH_PROBE_ASSET = "Lexeditor/Chapter3BenchProbe"
DOG_WHISTLE_PROBE_ASSET = "Lexeditor/DogWhistleProbe"
BETTER_LOCKON_PROBE_ASSET = "Lexeditor/BetterLockonProbe"

READ_ONLY_RESEARCH_ASSETS = frozenset({
    ATB_RUNTIME_PROBE_ASSET,
    UNSCANNED_NAME_PROBE_ASSET,
    CHAPTER3_BENCH_PROBE_ASSET,
    DOG_WHISTLE_PROBE_ASSET,
    BETTER_LOCKON_PROBE_ASSET,
})

RESEARCH_VIRTUAL_ASSET_ROWS = (
    {
        "asset": ATB_RUNTIME_PROBE_ASSET,
        "name": "ATB Runtime Research",
        "group": "Lexeditor Research",
        "synthetic": "atb-runtime-probe",
    },
    {
        "asset": UNSCANNED_NAME_PROBE_ASSET,
        "name": "Unscanned Enemy Name Research",
        "group": "Lexeditor Research",
        "synthetic": "unscanned-name-probe",
    },
    {
        "asset": CHAPTER3_BENCH_PROBE_ASSET,
        "name": "Chapter 3 Bench Research",
        "group": "Lexeditor Research",
        "synthetic": "chapter3-bench-probe",
    },
    {
        "asset": DOG_WHISTLE_PROBE_ASSET,
        "name": "Dog Whistle Research",
        "group": "Lexeditor Research",
        "synthetic": "dog-whistle-probe",
    },
    {
        "asset": BETTER_LOCKON_PROBE_ASSET,
        "name": "Better Lock-on Research",
        "group": "Lexeditor Research",
        "synthetic": "better-lockon-probe",
    },
)


def is_research_virtual_asset(asset: str) -> bool:
    return asset in READ_ONLY_RESEARCH_ASSETS


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _joined(values: Iterable[Any], *, limit: int = 64) -> str:
    rows = [str(value) for value in values if str(value)]
    if not rows:
        return "—"
    clipped = rows[:limit]
    suffix = f"\n… {len(rows) - limit} more" if len(rows) > limit else ""
    return "\n".join(clipped) + suffix


def _notes(result: dict[str, Any]) -> str:
    return " ".join(str(value) for value in result.get("notes", ()) if value) or "—"


def _needle_counts(native: dict[str, Any]) -> dict[str, int]:
    return {
        str(row.get("needle", "")): len(row.get("hits", ()))
        for row in native.get("needles", ())
        if row.get("needle")
    }


def _counts_text(values: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(values.items())) or "—"


def _readonly_package(asset: str, export_name: str, properties: list[VirtualProperty],
                      values: dict[str, Any], result: dict[str, Any], *, tag: str) -> tuple[VirtualPackage, str, bool]:
    active_sha = _canonical_hash(result)
    return (
        VirtualPackage(
            asset=asset,
            export_name=export_name,
            properties=properties,
            entries=[Entry(0, tag, values, {})],
            source_sha=active_sha,
            active_sha=active_sha,
        ),
        active_sha,
        False,
    )


def atb_runtime_result_package(result: dict[str, Any]):
    data = dict(result.get("dataBacked", {}))
    runtime = dict(result.get("runtimeResearch", {}))
    properties = [
        VirtualProperty("ImplementationReady", "Implementation Ready", "BOOL"),
        VirtualProperty("Blockers", "Implementation Blockers", "STRING"),
        VirtualProperty("AccumulatorCandidatePresent", "ATB Accumulator Candidate Present", "BOOL"),
        VirtualProperty("SpeedCandidatePresent", "Speed Input Candidate Present", "BOOL"),
        VirtualProperty("HitGainCandidatePresent", "Hit ATB Candidate Present", "BOOL"),
        VirtualProperty("DodgeStateCandidatePresent", "Dodge State Candidate Present", "BOOL"),
        VirtualProperty("ResidentCandidateRows", "Resident ATB Candidate Rows", "INT32"),
        VirtualProperty("GuardSlots", "Editable Guard ATB Slots", "INT32"),
        VirtualProperty("AbilityCostRows", "Editable Ability ATB Cost Rows", "INT32"),
        VirtualProperty("NativeNeedleHits", "Native Needle Hits", "STRING"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]
    values = {
        "ImplementationReady": bool(result.get("implementationReady", False)),
        "Blockers": _joined(result.get("blockers", ())),
        "AccumulatorCandidatePresent": bool(runtime.get("accumulatorCandidatePresent", False)),
        "SpeedCandidatePresent": bool(runtime.get("speedCandidatePresent", False)),
        "HitGainCandidatePresent": bool(runtime.get("hitGainCandidatePresent", False)),
        "DodgeStateCandidatePresent": bool(runtime.get("dodgeStateCandidatePresent", False)),
        "ResidentCandidateRows": int(data.get("residentCandidateRows", 0)),
        "GuardSlots": int(data.get("guardSlots", 0)),
        "AbilityCostRows": int(data.get("abilityCostRows", 0)),
        "NativeNeedleHits": _counts_text(dict(result.get("nativeNeedleHits", {}))),
        "ResearchNotes": _notes(result),
    }
    return _readonly_package(
        ATB_RUNTIME_PROBE_ASSET, "LexeditorATBRuntimeProbe", properties, values, result,
        tag="ATB Runtime Research",
    )


def unscanned_name_result_package(result: dict[str, Any]):
    assessed = dict(result.get("assessedState", {}))
    presentation = dict(result.get("presentation", {}))
    candidates = list(result.get("candidates", ()))
    top = [
        f"{row.get('score', 0)} | {row.get('asset', row.get('path', '—'))} | strong={bool(row.get('strongPresentationCandidate', False))}"
        for row in candidates[:16]
    ]
    properties = [
        VirtualProperty("ImplementationReady", "Implementation Ready", "BOOL"),
        VirtualProperty("Blockers", "Implementation Blockers", "STRING"),
        VirtualProperty("AssessedStateCandidatePresent", "Assessed-State Query Candidate Present", "BOOL"),
        VirtualProperty("AssessedStateValidated", "Assessed-State Query Validated", "BOOL"),
        VirtualProperty("BattleNamePathCandidate", "Battle Name Presentation Candidate", "BOOL"),
        VirtualProperty("ATBTargetPathCandidate", "ATB Target Presentation Candidate", "BOOL"),
        VirtualProperty("RankedCandidateCount", "Ranked Cooked UI Candidates", "INT32"),
        VirtualProperty("QueryNeedleHits", "Assessed-State Native Needle Hits", "STRING"),
        VirtualProperty("PresentationNeedleHits", "Presentation Native Needle Hits", "STRING"),
        VirtualProperty("TopCandidates", "Top Cooked UI Candidates", "STRING"),
        VirtualProperty("ScanErrors", "Scan Errors", "STRING"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]
    values = {
        "ImplementationReady": bool(result.get("implementationReady", False)),
        "Blockers": _joined(result.get("blockers", ())),
        "AssessedStateCandidatePresent": bool(assessed.get("candidatePresent", False)),
        "AssessedStateValidated": bool(assessed.get("validated", False)),
        "BattleNamePathCandidate": bool(presentation.get("battleNamePathCandidate", False)),
        "ATBTargetPathCandidate": bool(presentation.get("atbTargetPathCandidate", False)),
        "RankedCandidateCount": int(presentation.get("rankedCandidateCount", len(candidates))),
        "QueryNeedleHits": _counts_text(dict(assessed.get("candidateNeedleHits", {}))),
        "PresentationNeedleHits": _counts_text(dict(presentation.get("nativeNeedleHits", {}))),
        "TopCandidates": _joined(top, limit=16),
        "ScanErrors": _joined(result.get("scanErrors", ())),
        "ResearchNotes": _notes(result),
    }
    return _readonly_package(
        UNSCANNED_NAME_PROBE_ASSET, "LexeditorUnscannedNameProbe", properties, values, result,
        tag="Unscanned Enemy Name Research",
    )


def chapter3_bench_result_package(result: dict[str, Any]):
    candidates = list(result.get("allEvidenceCandidates", ()))
    object_paired = list(result.get("objectPairedCandidates", ()))
    printable_paired = list(result.get("pairedCandidates", ()))
    shared_outer_count = sum(len(row.get("sharedOuterPairs", ())) for row in candidates)
    top = [
        f"{row.get('score', 0)} | {row.get('pak', '—')} :: {row.get('path', '—')} | "
        f"benchExports={len(row.get('benchExports', ()))}, vendingExports={len(row.get('vendingExports', ()))}, "
        f"sharedOuterPairs={len(row.get('sharedOuterPairs', ()))}"
        for row in candidates[:16]
    ]
    properties = [
        VirtualProperty("ImplementationReady", "Implementation Ready", "BOOL"),
        VirtualProperty("MatchingCookedFiles", "Matching Sector 7 Cooked Files", "INT32"),
        VirtualProperty("ScannedCookedFiles", "Scanned Cooked Files", "INT32"),
        VirtualProperty("ScanTruncated", "Candidate Scan Truncated", "BOOL"),
        VirtualProperty("ObjectPairedCandidates", "Bench + Vending Export Candidates", "INT32"),
        VirtualProperty("PrintablePairedCandidates", "Bench + Vending String Candidates", "INT32"),
        VirtualProperty("SharedOuterPairs", "Resolved Shared-Outer Pairs", "INT32"),
        VirtualProperty("TopCandidates", "Top Candidate Packages", "STRING"),
        VirtualProperty("ScanErrors", "Scan Errors", "STRING"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]
    values = {
        "ImplementationReady": False,
        "MatchingCookedFiles": int(result.get("matchingCookedFiles", 0)),
        "ScannedCookedFiles": int(result.get("scannedCookedFiles", 0)),
        "ScanTruncated": bool(result.get("truncated", False)),
        "ObjectPairedCandidates": len(object_paired),
        "PrintablePairedCandidates": len(printable_paired),
        "SharedOuterPairs": shared_outer_count,
        "TopCandidates": _joined(top, limit=16),
        "ScanErrors": _joined(result.get("scanErrors", ())),
        "ResearchNotes": _notes(result),
    }
    return _readonly_package(
        CHAPTER3_BENCH_PROBE_ASSET, "LexeditorChapter3BenchProbe", properties, values, result,
        tag="Chapter 3 Bench Research",
    )


def dog_whistle_result_package(report: dict[str, Any], assessment: dict[str, Any]):
    item = dict(assessment.get("itemAuthoring", {}))
    award = dict(assessment.get("chapterAward", {}))
    retarget = dict(assessment.get("runtimeRetarget", {}))
    canine = dict(assessment.get("canineCoverage", {}))
    combined = {"report": report, "assessment": assessment}
    properties = [
        VirtualProperty("ImplementationReady", "Implementation Ready", "BOOL"),
        VirtualProperty("Blockers", "Implementation Blockers", "STRING"),
        VirtualProperty("ExistingWhistleRows", "Existing Whistle-like Item Rows", "INT32"),
        VirtualProperty("WhistleFNameCandidates", "Whistle-like Item FNames", "STRING"),
        VirtualProperty("WriterCanAddItemRow", "Writer Can Add New Item Row", "BOOL"),
        VirtualProperty("ChapterAddKeyItemPresent", "Chapter.AddKeyItem_Array Present", "BOOL"),
        VirtualProperty("ChapterAwardPlausible", "Chapter Reward Data Path Plausible", "BOOL"),
        VirtualProperty("WriterCanAppendChapterReward", "Writer Can Append Existing FName Reward", "BOOL"),
        VirtualProperty("CanineCandidateGroups", "Canine Candidate Groups", "INT32"),
        VirtualProperty("CanineBattleRows", "Canine BattleChara Rows", "INT32"),
        VirtualProperty("RetargetAnchorsPresent", "Runtime Retarget Anchors Present", "BOOL"),
        VirtualProperty("NativeNeedleHits", "Retarget/Award Native Needle Hits", "STRING"),
        VirtualProperty("ScanErrors", "Scan Errors", "STRING"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]
    values = {
        "ImplementationReady": bool(assessment.get("implementationReady", False)),
        "Blockers": _joined(assessment.get("blockers", ())),
        "ExistingWhistleRows": int(item.get("existingWhistleRowCandidates", 0)),
        "WhistleFNameCandidates": _joined(item.get("whistleNameMapCandidates", ())),
        "WriterCanAddItemRow": bool(item.get("writerSupportsNewItemRow", False)),
        "ChapterAddKeyItemPresent": bool(award.get("addKeyItemPropertyPresent", False)),
        "ChapterAwardPlausible": bool(award.get("dataAwardPathPlausible", False)),
        "WriterCanAppendChapterReward": bool(award.get("writerSupportsArrayAppend", False)),
        "CanineCandidateGroups": int(canine.get("candidateGroups", 0)),
        "CanineBattleRows": int(canine.get("battleCharaRows", 0)),
        "RetargetAnchorsPresent": bool(retarget.get("retargetAnchorsPresent", False)),
        "NativeNeedleHits": _counts_text(dict(retarget.get("needleHits", {}))),
        "ScanErrors": _joined(report.get("scanErrors", ())),
        "ResearchNotes": _notes(assessment),
    }
    return _readonly_package(
        DOG_WHISTLE_PROBE_ASSET, "LexeditorDogWhistleProbe", properties, values, combined,
        tag="Dog Whistle Research",
    )


def better_lockon_result_package(result: dict[str, Any]):
    candidates = list(result.get("candidates", ()))
    strong = [row for row in candidates if row.get("strongPresentationCandidate")]
    dedicated = [row for row in candidates if row.get("containsDedicatedWidgetAnchor")]
    labels = [row for row in candidates if row.get("containsLiteralLockOnLabel")]
    top = [
        f"{row.get('score', 0)} | {row.get('asset', row.get('path', '—'))} | "
        f"widget={bool(row.get('containsDedicatedWidgetAnchor'))}, label={bool(row.get('containsLiteralLockOnLabel'))}, "
        f"strong={bool(row.get('strongPresentationCandidate'))}"
        for row in candidates[:16]
    ]
    properties = [
        VirtualProperty("ImplementationReady", "Implementation Ready", "BOOL"),
        VirtualProperty("CandidateCount", "Ranked Cooked UI Candidates", "INT32"),
        VirtualProperty("StrongCandidates", "Strong Presentation Candidates", "INT32"),
        VirtualProperty("DedicatedWidgetCandidates", "Dedicated Lock-on Widget Candidates", "INT32"),
        VirtualProperty("LiteralLabelCandidates", "Literal LOCK ON Label Candidates", "INT32"),
        VirtualProperty("NativeNeedleHits", "Native Lock-on Needle Hits", "STRING"),
        VirtualProperty("TopCandidates", "Top Cooked UI Candidates", "STRING"),
        VirtualProperty("ScanErrors", "Scan Errors", "STRING"),
        VirtualProperty("ResearchNotes", "Research Notes", "STRING"),
    ]
    values = {
        "ImplementationReady": bool(result.get("implementationReady", False)),
        "CandidateCount": len(candidates),
        "StrongCandidates": len(strong),
        "DedicatedWidgetCandidates": len(dedicated),
        "LiteralLabelCandidates": len(labels),
        "NativeNeedleHits": _counts_text(_needle_counts(dict(result.get("native", {})))),
        "TopCandidates": _joined(top, limit=16),
        "ScanErrors": _joined(result.get("scanErrors", ())),
        "ResearchNotes": _notes(result),
    }
    return _readonly_package(
        BETTER_LOCKON_PROBE_ASSET, "LexeditorBetterLockonProbe", properties, values, result,
        tag="Better Lock-on Research",
    )


def load_research_virtual_package(game_root: Path, data_root: Path, project_root: Path,
                                  index: dict, asset: str):
    """Run one installed-build research probe and expose a bounded read-only view."""
    if asset == ATB_RUNTIME_PROBE_ASSET:
        from .atb_runtime_probe import probe_atb_runtime_sources
        from .atb_tweaks import discover_atb_sources

        discovery = discover_atb_sources(game_root, data_root, index)
        return atb_runtime_result_package(probe_atb_runtime_sources(game_root, discovery))

    if asset == UNSCANNED_NAME_PROBE_ASSET:
        from .unscanned_name_probe import probe_unscanned_name_sources

        return unscanned_name_result_package(probe_unscanned_name_sources(game_root))

    if asset == CHAPTER3_BENCH_PROBE_ASSET:
        from .bench_probe import probe_chapter3_bench

        return chapter3_bench_result_package(probe_chapter3_bench(game_root))

    if asset == DOG_WHISTLE_PROBE_ASSET:
        from .dog_whistle_probe import probe_dog_whistle_sources
        from .dog_whistle_safety import assess_dog_whistle_probe

        report = probe_dog_whistle_sources(game_root, data_root, project_root, index)
        return dog_whistle_result_package(report, assess_dog_whistle_probe(report))

    if asset == BETTER_LOCKON_PROBE_ASSET:
        from .lockon_probe import probe_better_lockon_sources

        return better_lockon_result_package(probe_better_lockon_sources(game_root))

    raise KeyError(f"Unknown FF7R research probe: {asset}")
