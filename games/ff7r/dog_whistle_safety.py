"""Fail-closed feasibility assessment for the FF7R Dog Whistle tweak.

The installed-data probe deliberately discovers evidence without inventing an
item contract or repurposing an existing consumable. Structural helpers now cover
several format operations that were previously impossible, so this classifier
separates raw writer capability from the still-unproved gameplay/template links.
"""

from __future__ import annotations

from typing import Any

from .dataobject_structural import (
    EXISTING_FNAME_ROW_CLONE_SUPPORTED,
    FIXED_WIDTH_ARRAY_INSERT_SUPPORTED,
    SCALAR_FSTRING_REPLACE_SUPPORTED,
)
from .textresource_structural import TOP_LEVEL_TEXT_ENTRY_APPEND_SUPPORTED


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
    unused_whistle_names = list(item.get("unusedWhistleNameMapCandidates", ()))
    ability_templates = list(item.get("abilityBackedTemplateCandidates", ()))
    item_properties = {str(value) for value in item.get("itemProperties", ())}
    template_text_assets = sorted({
        str(text_row.get("textAsset", ""))
        for template in ability_templates
        for text_row in template.get("resolvedText", ())
        if text_row.get("textAsset")
    })

    correlated_key_items = list(chapter.get("referencedKeyItemsThatAreItemRows", ()))
    add_key_item_present = bool(chapter.get("addKeyItemPropertyPresent", False))
    chapter4_candidates = list(chapter.get("chapter4Candidates", ()))
    chapter4_with_award_field = [
        row for row in chapter4_candidates
        if isinstance(row.get("addKeyItems", []), list)
    ]

    native_hits = {
        needle: _needle_hit_count(native, needle)
        for needle in (REQUIRED_RETARGET_NEEDLE, *AI_LOOKUP_NEEDLES, *AWARD_NEEDLES)
    }
    retarget_anchors_present = bool(
        native_hits[REQUIRED_RETARGET_NEEDLE]
        and any(native_hits[needle] for needle in AI_LOOKUP_NEEDLES)
    )

    # The writer can clone an existing row without hijacking its ID only when an
    # unused target FName already exists in Item's name map. It can also resize
    # scalar FString IDs and append top-level localized text entries. None of
    # those format capabilities proves which battle-usable row is the right
    # template or which Item fields form the display/use contract.
    writer_supports_new_item_row = bool(
        EXISTING_FNAME_ROW_CLONE_SUPPORTED
        and SCALAR_FSTRING_REPLACE_SUPPORTED
        and unused_whistle_names
    )
    writer_supports_new_text_entry = TOP_LEVEL_TEXT_ENTRY_APPEND_SUPPORTED
    writer_supports_array_append = FIXED_WIDTH_ARRAY_INSERT_SUPPORTED
    data_award_path_plausible = bool(
        add_key_item_present
        and correlated_key_items
        and len(chapter4_with_award_field) == 1
    )

    blockers: list[str] = []
    if scan_errors:
        blockers.append("scan-errors")

    if whistle_rows:
        blockers.append("existing-whistle-row-not-proved-safe-to-repurpose")
    if not unused_whistle_names:
        blockers.append("unused-whistle-item-fname-unresolved")
    if not writer_supports_new_item_row:
        blockers.append("writer-cannot-clone-new-item-row-with-existing-fname")
    else:
        blockers.append("battle-usable-item-template-unproved")
    if not ability_templates:
        blockers.append("ability-backed-item-template-set-unresolved")
    if "AbilityID" not in item_properties:
        blockers.append("item-ability-field-unresolved")
    if not writer_supports_new_text_entry:
        blockers.append("writer-cannot-add-text-entry")
    if not template_text_assets:
        blockers.append("item-text-resource-owner-unresolved")
    else:
        blockers.append("item-name-description-field-linkage-unproved")

    if data_award_path_plausible and not writer_supports_array_append:
        blockers.append("writer-cannot-append-chapter-reward")
    elif not data_award_path_plausible:
        if len(chapter4_candidates) != 1:
            blockers.append("chapter4-row-unresolved-or-ambiguous")
        blockers.append("chapter-reward-contract-unproved")
    else:
        blockers.append("chapter4-once-only-award-semantics-unvalidated")

    if not retarget_anchors_present:
        blockers.append("runtime-retarget-anchors-unproved")
    else:
        blockers.append("runtime-retarget-semantics-unvalidated")
    if not canine_rows:
        blockers.append("canine-enemy-set-unresolved")
    else:
        blockers.append("canine-enemy-set-not-battle-validated")

    return {
        "implementationReady": False,
        "blockers": blockers,
        "itemAuthoring": {
            "existingWhistleRowCandidates": len(whistle_rows),
            "whistleNameMapCandidates": whistle_names,
            "unusedWhistleNameMapCandidates": unused_whistle_names,
            "abilityBackedTemplateCandidates": len(ability_templates),
            "templateTextResourceCandidates": template_text_assets,
            "writerSupportsNewItemRow": writer_supports_new_item_row,
            "writerSupportsExistingFNameRowClone": EXISTING_FNAME_ROW_CLONE_SUPPORTED,
            "writerSupportsScalarFStringRewrite": SCALAR_FSTRING_REPLACE_SUPPORTED,
            "writerSupportsNewTextEntry": writer_supports_new_text_entry,
            "safeExistingRowProved": False,
        },
        "chapterAward": {
            "addKeyItemPropertyPresent": add_key_item_present,
            "ordinaryItemRowCorrelationCount": len(correlated_key_items),
            "chapter4CandidateCount": len(chapter4_candidates),
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
            "An existing whistle-like Item row is never permission to hijack that row; the safe new-row path requires an UNUSED whistle-like FName already in the Item package name map.",
            "The writer can clone a proved Item template, resize scalar FString IDs, and append new localized top-level text IDs without expanding package name maps. Exact Item template/display/use fields still require installed evidence.",
            "Fixed-width array insertion can append the eventual new Item row tag to a proved Chapter 4 AddKeyItem_Array without replacing another reward; exact Chapter 4 ownership and once-only semantics still require validation.",
            "SetTarget is the narrow retarget primitive, but the exact active-enemy enumeration/user-character mapping and scripted/boss exceptions remain unvalidated.",
            "The assessment is read-only and cannot make the Dog Whistle implementation ready by itself.",
        ],
    }
