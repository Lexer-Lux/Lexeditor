"""Fail-closed feasibility assessment for the FF7R Dog Whistle tweak.

The installed-data probe deliberately discovers evidence without inventing a new
item row or repurposing an existing consumable. This module records which parts
of the requested feature have a plausible authoritative path and which parts
still require structural/runtime work.
"""

from __future__ import annotations

from typing import Any

from .dataobject_structural import FIXED_WIDTH_ARRAY_INSERT_SUPPORTED


REQUIRED_RETARGET_NEEDLE = "SetTarget"
AI_LOOKUP_NEEDLES = ("GetBattleAI", "GetBattleAIControllerFromID")
AWARD_NEEDLES = ("Item_Add", "AddKeyItem")


def _needle_hit_count(native: dict[str, Any], needle: str) -> int:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return len(row.get("hits", ()))
    return 0


def assess_dog_whistle_probe(report: dict[str, Any]) -> dict[str, Any]:
    """Classify the current implementation route without authorizing mutation."""
    item = dict(report.get("item", {}))
    chapter = dict(report.get("chapterProgression", {}))
    native = dict(report.get("native", {}))
    canine_rows = list(report.get("canineEnemies", ()))
    scan_errors = [str(error) for error in report.get("scanErrors", ())]

    whistle_rows = list(item.get("rowCandidates", ()))
    whistle_names = list(item.get("whistleNameMapCandidates", ()))
    correlated_key_items = list(chapter.get("referencedKeyItemsThatAreItemRows", ()))
    add_key_item_present = bool(chapter.get("addKeyItemPropertyPresent", False))

    native_hits = {
        needle: _needle_hit_count(native, needle)
        for needle in (REQUIRED_RETARGET_NEEDLE, *AI_LOOKUP_NEEDLES, *AWARD_NEEDLES)
    }
    retarget_anchors_present = bool(
        native_hits[REQUIRED_RETARGET_NEEDLE]
        and any(native_hits[needle] for needle in AI_LOOKUP_NEEDLES)
    )

    # A dedicated structural helper can now append existing FNames to declared
    # fixed-width arrays such as Chapter.AddKeyItem_Array without replacing an
    # existing reward. Creating a genuinely new Item row/name-map entry remains
    # deliberately unsupported.
    writer_supports_new_item_row = False
    writer_supports_array_append = FIXED_WIDTH_ARRAY_INSERT_SUPPORTED
    data_award_path_plausible = bool(add_key_item_present and correlated_key_items)

    blockers: list[str] = []
    if scan_errors:
        blockers.append("scan-errors")
    if not whistle_rows:
        blockers.append("no-existing-whistle-item-row")
    else:
        blockers.append("existing-whistle-row-not-proved-safe-to-repurpose")
    if not writer_supports_new_item_row:
        blockers.append("writer-cannot-add-item-row")
    if data_award_path_plausible and not writer_supports_array_append:
        blockers.append("writer-cannot-append-chapter-reward")
    elif not data_award_path_plausible:
        blockers.append("chapter-reward-contract-unproved")
    if not retarget_anchors_present:
        blockers.append("runtime-retarget-anchors-unproved")
    if not canine_rows:
        blockers.append("canine-enemy-set-unresolved")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "itemAuthoring": {
            "existingWhistleRowCandidates": len(whistle_rows),
            "whistleNameMapCandidates": whistle_names,
            "writerSupportsNewItemRow": writer_supports_new_item_row,
            "safeExistingRowProved": False,
        },
        "chapterAward": {
            "addKeyItemPropertyPresent": add_key_item_present,
            "ordinaryItemRowCorrelationCount": len(correlated_key_items),
            "dataAwardPathPlausible": data_award_path_plausible,
            "writerSupportsArrayAppend": writer_supports_array_append,
        },
        "runtimeRetarget": {
            "needleHits": native_hits,
            "retargetAnchorsPresent": retarget_anchors_present,
            "requiredMethod": "AEndBattleAIController::SetTarget(AEndCharacter*)",
        },
        "canineCoverage": {
            "candidateGroups": len(canine_rows),
            "battleCharaRows": sum(len(row.get("battleCharaRows", ())) for row in canine_rows),
            "installedBattleValidationRequired": True,
        },
        "notes": [
            "An existing whistle-like FName is not permission to hijack an unrelated Item row.",
            "Fixed-width array insertion can append an existing FName reward without replacing another Chapter.AddKeyItem_Array entry; the installed identifier contract still must be proved first.",
            "SetTarget is the narrow retarget primitive; canine candidates still require validation for scripted/boss exceptions such as Darkstar.",
            "The assessment is read-only and cannot make the Dog Whistle implementation ready by itself.",
        ],
    }
