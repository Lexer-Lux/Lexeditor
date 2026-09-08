from games.ff7r.dog_whistle_safety import assess_dog_whistle_probe


def _native_function_row(needle, function_rva, *next_hops, source="pdata"):
    return {
        "needle": needle,
        "hits": [{
            "leaRipXrefs": [{
                "candidateFunctionRva": function_rva,
                "candidateFunctionSource": source,
                "candidateFunctionCodeRefs": {
                    "refs": [
                        {"targetFunctionRva": target}
                        for target in next_hops
                    ],
                },
            }],
        }],
    }


def _report(
    *,
    whistle_rows=(),
    unused_names=("Whistle",),
    templates=(),
    linked_templates=(),
    item_command_templates=(),
    unresolved_templates=(),
    ability_rows=(),
    ability_names=("WhistleAbility",),
    unused_ability_names=("WhistleAbility",),
    ability_properties=("CommandType", "CommandTargetType"),
    key_items=(),
    chapter4=(),
    canine=(),
    native_hits=(),
    native_rows=(),
    errors=(),
):
    rows = [
        {"needle": needle, "hits": [{}] * count}
        for needle, count in native_hits
    ]
    rows.extend(native_rows)
    return {
        "item": {
            "rowCandidates": list(whistle_rows),
            "whistleNameMapCandidates": ["Whistle"],
            "unusedWhistleNameMapCandidates": list(unused_names),
            "abilityBackedTemplateCandidates": list(templates),
            "linkedBattleAbilityTemplateCandidates": list(linked_templates),
            "itemCommandTemplateCandidates": list(item_command_templates),
            "unresolvedAbilityTemplateCandidates": list(unresolved_templates),
            "itemProperties": ["AbilityID", "NameID", "DescriptionID"],
        },
        "battleAbility": {
            "rowCandidates": list(ability_rows),
            "whistleNameMapCandidates": list(ability_names),
            "unusedWhistleNameMapCandidates": list(unused_ability_names),
            "properties": list(ability_properties),
        },
        "chapterProgression": {
            "addKeyItemPropertyPresent": True,
            "referencedKeyItemsThatAreItemRows": list(key_items),
            "chapter4Candidates": list(chapter4),
        },
        "canineEnemies": list(canine),
        "native": {"needles": rows},
        "scanErrors": list(errors),
    }


def _template(tag="potion"):
    return {
        "tag": tag,
        "abilityId": "Item_Potion",
        "resolvedText": [
            {
                "property": "NameID",
                "textId": "$Item_Potion_Name",
                "text": "Potion",
                "textAsset": "End/Content/GameContents/Text/US/Resident_TxtRes",
            }
        ],
    }


def _chapter4(tag="Chapter04"):
    return {
        "tag": tag,
        "chapter4Signals": ["row-tag", "resolved-text:ChapterNameID"],
        "addKeyItems": [],
    }


def test_unused_existing_fname_unlocks_structural_new_row_capability_but_not_template_behavior():
    template = _template()
    result = assess_dog_whistle_probe(_report(
        templates=[template],
        linked_templates=[template],
        item_command_templates=[template],
    ))

    assert result["implementationReady"] is False
    assert result["itemAuthoring"]["writerSupportsNewItemRow"] is True
    assert result["itemAuthoring"]["writerSupportsExistingFNameRowClone"] is True
    assert result["itemAuthoring"]["writerSupportsScalarFStringRewrite"] is True
    assert result["itemAuthoring"]["writerSupportsNewTextEntry"] is True
    assert result["itemAuthoring"]["itemCommandTemplateCandidates"] == 1
    assert "writer-cannot-clone-new-item-row-with-existing-fname" not in result["blockers"]
    assert "item-command-template-unproved" not in result["blockers"]
    assert "item-command-template-behavior-unvalidated" in result["blockers"]
    assert "item-name-description-field-linkage-unproved" in result["blockers"]


def test_linked_ability_without_item_command_classification_does_not_prove_item_template():
    template = _template()
    result = assess_dog_whistle_probe(_report(
        templates=[template],
        linked_templates=[template],
    ))

    assert result["itemAuthoring"]["linkedBattleAbilityTemplateCandidates"] == 1
    assert result["itemAuthoring"]["itemCommandTemplateCandidates"] == 0
    assert "item-command-template-unproved" in result["blockers"]


def test_missing_unused_whistle_fname_keeps_new_row_authoring_blocked():
    template = _template()
    result = assess_dog_whistle_probe(_report(
        unused_names=(),
        templates=[template],
        linked_templates=[template],
        item_command_templates=[template],
    ))

    assert result["itemAuthoring"]["writerSupportsNewItemRow"] is False
    assert "unused-whistle-item-fname-unresolved" in result["blockers"]
    assert "writer-cannot-clone-new-item-row-with-existing-fname" in result["blockers"]


def test_existing_candidate_never_authorizes_repurposing():
    result = assess_dog_whistle_probe(_report(
        whistle_rows=[{"tag": "SomeWhistle"}],
        templates=[_template()],
    ))

    assert result["itemAuthoring"]["existingWhistleRowCandidates"] == 1
    assert result["itemAuthoring"]["safeExistingRowProved"] is False
    assert "existing-whistle-row-not-proved-safe-to-repurpose" in result["blockers"]


def test_chapter_reward_requires_unique_chapter4_owner_and_item_row_correlation():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        key_items=["key_item_01"],
        chapter4=[_chapter4()],
    ))

    assert result["chapterAward"]["dataAwardPathPlausible"] is True
    assert result["chapterAward"]["chapter4CandidateCount"] == 1
    assert result["chapterAward"]["chapter4AwardArrayCandidateCount"] == 1
    assert result["chapterAward"]["writerSupportsArrayAppend"] is True
    assert "chapter-reward-contract-unproved" not in result["blockers"]
    assert "chapter4-once-only-award-semantics-unvalidated" in result["blockers"]


def test_chapter_reward_missing_row_award_array_fails_closed():
    chapter = _chapter4()
    chapter.pop("addKeyItems")
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        key_items=["key_item_01"],
        chapter4=[chapter],
    ))

    assert result["chapterAward"]["chapter4CandidateCount"] == 1
    assert result["chapterAward"]["chapter4AwardArrayCandidateCount"] == 0
    assert result["chapterAward"]["dataAwardPathPlausible"] is False
    assert "chapter4-award-array-unresolved" in result["blockers"]
    assert "chapter-reward-contract-unproved" in result["blockers"]
    assert "chapter4-once-only-award-semantics-unvalidated" not in result["blockers"]


def test_ambiguous_chapter4_candidates_fail_closed():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        key_items=["key_item_01"],
        chapter4=[_chapter4("A"), _chapter4("B")],
    ))

    assert result["chapterAward"]["dataAwardPathPlausible"] is False
    assert "chapter4-row-unresolved-or-ambiguous" in result["blockers"]
    assert "chapter-reward-contract-unproved" in result["blockers"]


def test_set_target_plus_ai_lookup_is_not_enough_without_enemy_enumeration_and_id_lookup():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        native_hits=[("SetTarget", 2), ("GetBattleAI", 1)],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["setTargetCandidatePresent"] is True
    assert runtime["aiLookupCandidatePresent"] is True
    assert runtime["activeEnemyEnumerationCandidatePresent"] is False
    assert runtime["battleCharaIdLookupCandidatePresent"] is False
    assert runtime["retargetPipelinePresent"] is False
    assert runtime["retargetAnchorsPresent"] is False
    assert "runtime-enemy-enumeration-unresolved" in result["blockers"]
    assert "runtime-battlechara-id-lookup-unresolved" in result["blockers"]
    assert "runtime-retarget-pipeline-unproved" in result["blockers"]
    assert "runtime-retarget-semantics-unvalidated" not in result["blockers"]


def test_full_reflected_retarget_pipeline_is_still_semantically_and_functionally_unvalidated():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        native_hits=[
            ("GetEnemyMembersRef", 1),
            ("GetBattleCharaSpec_DataTableID", 1),
            ("GetBattleAIControllerFromID", 1),
            ("SetTarget", 2),
        ],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["activeEnemyEnumerationCandidatePresent"] is True
    assert runtime["battleCharaIdLookupCandidatePresent"] is True
    assert runtime["aiLookupCandidatePresent"] is True
    assert runtime["setTargetCandidatePresent"] is True
    assert runtime["retargetPipelinePresent"] is True
    assert runtime["retargetFunctionEvidenceComplete"] is False
    assert runtime["retargetAnchorsPresent"] is True
    assert "runtime-retarget-pipeline-unproved" not in result["blockers"]
    assert "runtime-retarget-semantics-unvalidated" in result["blockers"]
    assert "runtime-retarget-function-evidence-incomplete" in result["blockers"]


def test_exact_pdata_evidence_for_each_retarget_anchor_still_does_not_prove_call_path():
    result = assess_dog_whistle_probe(_report(
        native_rows=[
            _native_function_row("GetEnemyMembersRef", 0x1000, 0x5000),
            _native_function_row("GetBattleCharaSpec_DataTableID", 0x1100, 0x5100),
            _native_function_row("GetBattleAIControllerFromID", 0x1200, 0x5200),
            _native_function_row("SetTarget", 0x1300, 0x5300),
        ],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["retargetPipelinePresent"] is True
    assert runtime["retargetFunctionEvidenceComplete"] is True
    assert runtime["activeEnemyEnumerationFunctionCandidatePresent"] is True
    assert runtime["battleCharaIdLookupFunctionCandidatePresent"] is True
    assert runtime["aiLookupFunctionCandidatePresent"] is True
    assert runtime["setTargetFunctionCandidatePresent"] is True
    assert "runtime-retarget-function-evidence-incomplete" not in result["blockers"]
    assert "runtime-retarget-function-path-unvalidated" in result["blockers"]
    assert "runtime-retarget-semantics-unvalidated" in result["blockers"]
    assert result["implementationReady"] is False


def test_item_classifier_and_ability_execution_bridge_still_do_not_prove_player_menu_commit():
    result = assess_dog_whistle_probe(_report(
        native_hits=[
            ("IsItem", 1),
            ("RequestAIPCExecuteAbility", 1),
        ],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["itemClassifierCandidatePresent"] is True
    assert runtime["abilityExecutionBridgeCandidatePresent"] is True
    assert runtime["itemAbilityRuntimeBridgePresent"] is True
    assert runtime["itemAbilityFunctionEvidenceComplete"] is False
    assert runtime["playerItemCommandCommitValidated"] is False
    assert "runtime-item-ability-bridge-unproved" not in result["blockers"]
    assert "runtime-item-ability-bridge-unvalidated" in result["blockers"]
    assert "runtime-item-ability-function-evidence-incomplete" in result["blockers"]
    assert "player-item-command-commit-hook-unresolved" in result["blockers"]


def test_exact_item_and_ai_execution_functions_still_cannot_stand_in_for_player_commit():
    result = assess_dog_whistle_probe(_report(
        native_rows=[
            _native_function_row("IsItem", 0x2000, 0x6000),
            _native_function_row("RequestAIPCExecuteAbility", 0x2100, 0x6100),
        ],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["itemAbilityRuntimeBridgePresent"] is True
    assert runtime["itemAbilityFunctionEvidenceComplete"] is True
    assert runtime["itemClassifierFunctionCandidatePresent"] is True
    assert runtime["abilityExecutionFunctionCandidatePresent"] is True
    assert "runtime-item-ability-function-evidence-incomplete" not in result["blockers"]
    assert "runtime-item-ability-function-path-unvalidated" in result["blockers"]
    assert "player-item-command-commit-hook-unresolved" in result["blockers"]
    assert runtime["playerItemCommandCommitValidated"] is False


def test_padding_heuristic_runtime_owners_cannot_strengthen_function_evidence():
    result = assess_dog_whistle_probe(_report(
        native_rows=[
            _native_function_row(
                "GetEnemyMembersRef", 0x1000, 0x5000,
                source="padding-heuristic",
            ),
            _native_function_row("GetBattleCharaSpec_DataTableID", 0x1100),
            _native_function_row("GetBattleAIControllerFromID", 0x1200),
            _native_function_row("SetTarget", 0x1300),
        ],
    ))

    runtime = result["runtimeRetarget"]
    assert runtime["retargetPipelinePresent"] is True
    assert runtime["activeEnemyEnumerationFunctionCandidatePresent"] is False
    assert runtime["nativeFunctionEvidence"]["GetEnemyMembersRef"]["expandedPdataFunctions"] == []
    assert runtime["retargetFunctionEvidenceComplete"] is False
    assert "runtime-retarget-function-evidence-incomplete" in result["blockers"]


def test_multi_name_direct_owner_is_reported_as_registration_collision_risk():
    result = assess_dog_whistle_probe(_report(
        native_rows=[
            _native_function_row("GetBattleAIControllerFromID", 0x7000),
            _native_function_row("SetTarget", 0x7000),
        ],
    ))
    cluster = next(
        row for row in result["runtimeRetarget"]["nativeFunctionClusters"]
        if row["functionRva"] == 0x7000
    )

    assert cluster["families"] == ["ai-lookup", "retarget"]
    assert cluster["directNeedles"] == ["GetBattleAIControllerFromID", "SetTarget"]
    assert cluster["crossFamily"] is True
    assert cluster["registrationCollisionRisk"] is True
    assert result["implementationReady"] is False


def test_canine_coverage_counts_groups_and_battle_rows_without_claiming_validation():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        canine=[
            {"battleCharaRows": ["dog_a", "dog_b"]},
            {"battleCharaRows": ["dog_c"]},
        ],
    ))

    assert result["canineCoverage"] == {
        "candidateGroups": 2,
        "battleCharaRows": 3,
        "installedBattleValidationRequired": True,
    }
    assert "canine-enemy-set-not-battle-validated" in result["blockers"]


def test_scan_error_blocks_even_otherwise_good_research_evidence():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        key_items=["Whistle"],
        chapter4=[_chapter4()],
        canine=[{"battleCharaRows": ["dog"]}],
        native_hits=[
            ("GetEnemyMembersRef", 1),
            ("GetBattleCharaSpec_DataTableID", 1),
            ("GetBattleAIControllerFromID", 1),
            ("SetTarget", 1),
        ],
        errors=["EnemyBook: unsupported"],
    ))

    assert result["implementationReady"] is False
    assert "scan-errors" in result["blockers"]