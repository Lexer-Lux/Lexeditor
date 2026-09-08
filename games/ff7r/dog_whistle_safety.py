"""Fail-closed feasibility assessment for the FF7R Dog Whistle tweak.

The installed-data probe deliberately discovers evidence without inventing an
item/ability contract or repurposing existing content. Structural helpers cover
several format operations that were previously impossible, so this classifier
separates writer capability from still-unproved gameplay/template/runtime links.
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
ENEMY_ENUMERATION_NEEDLE = "GetEnemyMembersRef"
BATTLE_CHARA_ID_NEEDLE = "GetBattleCharaSpec_DataTableID"
ITEM_CLASSIFIER_NEEDLE = "IsItem"
ABILITY_EXECUTION_NEEDLES = (
    "RequestAIPCAbility",
    "RequestAIPCExecuteAbility",
    "ReserveAbility",
    "RequestUseAbility",
)
AWARD_NEEDLES = ("Item_Add", "AddKeyItem")


def _needle_hit_count(native: dict[str, Any], needle: str) -> int:
    for row in native.get("needles", ()):
        if str(row.get("needle", "")) == needle:
            return len(row.get("hits", ()))
    return 0


def assess_dog_whistle_probe(report: dict[str, Any]) -> dict[str, Any]:
    """Classify the current implementation route without authorizing mutation."""
    item = dict(report.get("item", {}))
    battle_ability = dict(report.get("battleAbility", {}))
    chapter = dict(report.get("chapterProgression", {}))
    native = dict(report.get("native", {}))
    canine_rows = list(report.get("canineEnemies", ()))
    scan_errors = [str(error) for error in report.get("scanErrors", ())]

    whistle_rows = list(item.get("rowCandidates", ()))
    whistle_names = list(item.get("whistleNameMapCandidates", ()))
    unused_whistle_names = list(item.get("unusedWhistleNameMapCandidates", ()))
    ability_templates = list(item.get("abilityBackedTemplateCandidates", ()))
    linked_ability_templates = list(item.get("linkedBattleAbilityTemplateCandidates", ()))
    item_command_templates = list(item.get("itemCommandTemplateCandidates", ()))
    unresolved_ability_templates = list(item.get("unresolvedAbilityTemplateCandidates", ()))
    item_properties = {str(value) for value in item.get("itemProperties", ())}

    ability_whistle_rows = list(battle_ability.get("rowCandidates", ()))
    ability_whistle_names = list(battle_ability.get("whistleNameMapCandidates", ()))
    unused_ability_whistle_names = list(battle_ability.get("unusedWhistleNameMapCandidates", ()))
    ability_properties = {str(value) for value in battle_ability.get("properties", ())}

    template_text_assets = sorted({
        str(text_row.get("textAsset", ""))
        for template in item_command_templates or linked_ability_templates or ability_templates
        for text_row in template.get("resolvedText", ())
        if text_row.get("textAsset")
    })

    correlated_key_items = list(chapter.get("referencedKeyItemsThatAreItemRows", ()))
    add_key_item_present = bool(chapter.get("addKeyItemPropertyPresent", False))
    chapter4_candidates = list(chapter.get("chapter4Candidates", ()))
    # A missing field is not equivalent to a proved empty AddKeyItem array. The
    # table-level property flag can be true even when a candidate row was emitted
    # without row-level array evidence, so require the key itself plus list shape.
    chapter4_with_award_field = [
        row for row in chapter4_candidates
        if "addKeyItems" in row and isinstance(row["addKeyItems"], list)
    ]

    native_needles = (
        REQUIRED_RETARGET_NEEDLE,
        *AI_LOOKUP_NEEDLES,
        ENEMY_ENUMERATION_NEEDLE,
        BATTLE_CHARA_ID_NEEDLE,
        ITEM_CLASSIFIER_NEEDLE,
        *ABILITY_EXECUTION_NEEDLES,
        *AWARD_NEEDLES,
    )
    native_hits = {
        needle: _needle_hit_count(native, needle)
        for needle in native_needles
    }
    ai_lookup_present = any(native_hits[needle] for needle in AI_LOOKUP_NEEDLES)
    active_enemy_enumeration_present = bool(native_hits[ENEMY_ENUMERATION_NEEDLE])
    battle_chara_id_lookup_present = bool(native_hits[BATTLE_CHARA_ID_NEEDLE])
    set_target_present = bool(native_hits[REQUIRED_RETARGET_NEEDLE])
    item_classifier_present = bool(native_hits[ITEM_CLASSIFIER_NEEDLE])
    ability_execution_bridge_present = any(
        native_hits[needle] for needle in ABILITY_EXECUTION_NEEDLES
    )
    item_ability_runtime_bridge_present = bool(
        item_classifier_present and ability_execution_bridge_present
    )
    retarget_pipeline_present = bool(
        active_enemy_enumeration_present
        and battle_chara_id_lookup_present
        and ai_lookup_present
        and set_target_present
    )

    # The writer can clone existing fixed-layout rows without hijacking their IDs
    # only when unused target FNames already exist in each package's own name map.
    writer_supports_new_item_row = bool(
        EXISTING_FNAME_ROW_CLONE_SUPPORTED
        and SCALAR_FSTRING_REPLACE_SUPPORTED
        and unused_whistle_names
    )
    writer_supports_new_ability_row = bool(
        EXISTING_FNAME_ROW_CLONE_SUPPORTED
        and unused_ability_whistle_names
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
    if not ability_templates:
        blockers.append("ability-backed-item-template-set-unresolved")
    if ability_templates and not linked_ability_templates:
        blockers.append("battle-ability-template-linkage-unresolved")
    if not item_command_templates:
        blockers.append("item-command-template-unproved")
    else:
        blockers.append("item-command-template-behavior-unvalidated")
    if unresolved_ability_templates:
        blockers.append("item-ability-links-partially-unresolved")
    if "AbilityID" not in item_properties:
        blockers.append("item-ability-field-unresolved")

    if ability_whistle_rows:
        blockers.append("existing-whistle-ability-row-not-proved-safe-to-repurpose")
    if not unused_ability_whistle_names:
        blockers.append("unused-whistle-battleability-fname-unresolved")
    if not writer_supports_new_ability_row:
        blockers.append("writer-cannot-clone-new-battleability-row-with-existing-fname")
    else:
        blockers.append("battle-ability-template-behavior-unproved")
    if battle_ability and not {"CommandType", "CommandTargetType"}.issubset(ability_properties):
        blockers.append("battle-ability-command-contract-incomplete")

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
        if len(chapter4_with_award_field) != 1:
            blockers.append("chapter4-award-array-unresolved")
        blockers.append("chapter-reward-contract-unproved")
    else:
        blockers.append("chapter4-once-only-award-semantics-unvalidated")

    if not active_enemy_enumeration_present:
        blockers.append("runtime-enemy-enumeration-unresolved")
    else:
        blockers.append("runtime-enemy-enumeration-unvalidated")
    if not battle_chara_id_lookup_present:
        blockers.append("runtime-battlechara-id-lookup-unresolved")
    else:
        blockers.append("runtime-battlechara-id-lookup-unvalidated")
    if not retarget_pipeline_present:
        blockers.append("runtime-retarget-pipeline-unproved")
    else:
        blockers.append("runtime-retarget-semantics-unvalidated")
    if not item_classifier_present:
        blockers.append("runtime-item-classifier-unresolved")
    else:
        blockers.append("runtime-item-classifier-unvalidated")
    if not ability_execution_bridge_present:
        blockers.append("runtime-ability-execution-bridge-unresolved")
    else:
        blockers.append("runtime-ability-execution-bridge-unvalidated")
    if not item_ability_runtime_bridge_present:
        blockers.append("runtime-item-ability-bridge-unproved")
    else:
        blockers.append("runtime-item-ability-bridge-unvalidated")
    # None of the reflected execution helpers proves where a human-confirmed
    # Items-menu command commits. Keep that as an independent hard blocker so
    # AI/script-only ability calls cannot accidentally authorize the feature.
    blockers.append("player-item-command-commit-hook-unresolved")
    blockers.append("whistle-user-character-mapping-unvalidated")
    blockers.append("scripted-boss-retarget-exceptions-unvalidated")

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
            "linkedBattleAbilityTemplateCandidates": len(linked_ability_templates),
            "itemCommandTemplateCandidates": len(item_command_templates),
            "unresolvedAbilityTemplateCandidates": len(unresolved_ability_templates),
            "templateTextResourceCandidates": template_text_assets,
            "writerSupportsNewItemRow": writer_supports_new_item_row,
            "writerSupportsExistingFNameRowClone": EXISTING_FNAME_ROW_CLONE_SUPPORTED,
            "writerSupportsScalarFStringRewrite": SCALAR_FSTRING_REPLACE_SUPPORTED,
            "writerSupportsNewTextEntry": writer_supports_new_text_entry,
            "safeExistingRowProved": False,
        },
        "abilityAuthoring": {
            "existingWhistleAbilityRowCandidates": len(ability_whistle_rows),
            "whistleNameMapCandidates": ability_whistle_names,
            "unusedWhistleNameMapCandidates": unused_ability_whistle_names,
            "writerSupportsNewAbilityRow": writer_supports_new_ability_row,
            "commandContractFieldsPresent": sorted(
                {"CommandType", "CommandTargetType"} & ability_properties
            ),
            "safeExistingRowProved": False,
        },
        "chapterAward": {
            "addKeyItemPropertyPresent": add_key_item_present,
            "ordinaryItemRowCorrelationCount": len(correlated_key_items),
            "chapter4CandidateCount": len(chapter4_candidates),
            "chapter4AwardArrayCandidateCount": len(chapter4_with_award_field),
            "dataAwardPathPlausible": data_award_path_plausible,
            "writerSupportsArrayAppend": writer_supports_array_append,
        },
        "runtimeRetarget": {
            "needleHits": native_hits,
            "activeEnemyEnumerationCandidatePresent": active_enemy_enumeration_present,
            "battleCharaIdLookupCandidatePresent": battle_chara_id_lookup_present,
            "aiLookupCandidatePresent": ai_lookup_present,
            "setTargetCandidatePresent": set_target_present,
            "retargetPipelinePresent": retarget_pipeline_present,
            "retargetAnchorsPresent": retarget_pipeline_present,
            "itemClassifierCandidatePresent": item_classifier_present,
            "abilityExecutionBridgeCandidatePresent": ability_execution_bridge_present,
            "itemAbilityRuntimeBridgePresent": item_ability_runtime_bridge_present,
            "playerItemCommandCommitValidated": False,
            "activeEnemyEnumeration": "UEndBattleAPI::GetEnemyMembersRef(TArray<AEndCharacter*>&)",
            "battleCharaIdLookup": "UEndBattleAPI::GetBattleCharaSpec_DataTableID(AEndCharacter*)",
            "requiredMethod": "AEndBattleAIController::SetTarget(AEndCharacter*)",
            "itemClassifier": "UEndBattleAPI::IsItem(FName InAbilityName)",
        },
        "canineCoverage": {
            "candidateGroups": len(canine_rows),
            "battleCharaRows": sum(len(row.get("battleCharaRows", ())) for row in canine_rows),
            "installedBattleValidationRequired": True,
        },
        "notes": [
            "An existing whistle-like Item or BattleAbility row is never permission to hijack it. Safe new-row paths require unused whistle-like FNames independently in each package name map.",
            "Item.AbilityID must resolve to an installed BattleAbility row before that template contributes executable-path evidence; unresolved IDs remain explicit blockers.",
            "Only linked BattleAbility rows classified as the generated Item command category count as battle-usable item template evidence; arbitrary AbilityID links do not.",
            "The writer can clone proved Item/BattleAbility templates, resize scalar FString IDs, and append localized top-level text IDs without expanding package name maps. Exact template behavior and item-use interception still require installed evidence.",
            "A Chapter 4 candidate counts as reward evidence only when that row explicitly exposes an addKeyItems list; a missing row field is not treated as an empty award array.",
            "Fixed-width array insertion can append the eventual new Item row tag to a proved Chapter 4 AddKeyItem_Array without replacing another reward; exact once-only semantics still require validation.",
            "The reflected retarget route is explicit: GetEnemyMembersRef -> GetBattleCharaSpec_DataTableID -> canine set filter -> AI lookup -> SetTarget(user). Every callsite/ABI and user-character mapping still requires installed validation before native mutation.",
            "IsItem plus the reflected ability execution helpers establishes a narrower item/AbilityID bridge, but AI/script execution is not permission to hook the human Items-menu commit path.",
            "The assessment is read-only and cannot make the Dog Whistle implementation ready by itself.",
        ],
    }
