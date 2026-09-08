from games.ff7r.dog_whistle_safety import assess_dog_whistle_probe


def _report(
    *,
    whistle_rows=(),
    unused_names=("Whistle",),
    templates=(),
    key_items=(),
    chapter4=(),
    canine=(),
    native_hits=(),
    errors=(),
):
    return {
        "item": {
            "rowCandidates": list(whistle_rows),
            "whistleNameMapCandidates": ["Whistle"],
            "unusedWhistleNameMapCandidates": list(unused_names),
            "abilityBackedTemplateCandidates": list(templates),
            "itemProperties": ["AbilityID", "NameID", "DescriptionID"],
        },
        "chapterProgression": {
            "addKeyItemPropertyPresent": True,
            "referencedKeyItemsThatAreItemRows": list(key_items),
            "chapter4Candidates": list(chapter4),
        },
        "canineEnemies": list(canine),
        "native": {
            "needles": [
                {"needle": needle, "hits": [{}] * count}
                for needle, count in native_hits
            ],
        },
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


def test_unused_existing_fname_unlocks_structural_new_row_capability_but_not_template_contract():
    result = assess_dog_whistle_probe(_report(templates=[_template()]))

    assert result["implementationReady"] is False
    assert result["itemAuthoring"]["writerSupportsNewItemRow"] is True
    assert result["itemAuthoring"]["writerSupportsExistingFNameRowClone"] is True
    assert result["itemAuthoring"]["writerSupportsScalarFStringRewrite"] is True
    assert result["itemAuthoring"]["writerSupportsNewTextEntry"] is True
    assert "writer-cannot-clone-new-item-row-with-existing-fname" not in result["blockers"]
    assert "battle-usable-item-template-unproved" in result["blockers"]
    assert "item-name-description-field-linkage-unproved" in result["blockers"]


def test_missing_unused_whistle_fname_keeps_new_row_authoring_blocked():
    result = assess_dog_whistle_probe(_report(unused_names=(), templates=[_template()]))

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
    assert result["chapterAward"]["writerSupportsArrayAppend"] is True
    assert "chapter-reward-contract-unproved" not in result["blockers"]
    assert "chapter4-once-only-award-semantics-unvalidated" in result["blockers"]


def test_ambiguous_chapter4_candidates_fail_closed():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        key_items=["key_item_01"],
        chapter4=[_chapter4("A"), _chapter4("B")],
    ))

    assert result["chapterAward"]["dataAwardPathPlausible"] is False
    assert "chapter4-row-unresolved-or-ambiguous" in result["blockers"]
    assert "chapter-reward-contract-unproved" in result["blockers"]


def test_set_target_plus_ai_lookup_marks_anchors_but_not_runtime_semantics_validated():
    result = assess_dog_whistle_probe(_report(
        templates=[_template()],
        native_hits=[("SetTarget", 2), ("GetBattleAI", 1)],
    ))

    assert result["runtimeRetarget"]["retargetAnchorsPresent"] is True
    assert "runtime-retarget-anchors-unproved" not in result["blockers"]
    assert "runtime-retarget-semantics-unvalidated" in result["blockers"]


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
        native_hits=[("SetTarget", 1), ("GetBattleAIControllerFromID", 1)],
        errors=["EnemyBook: unsupported"],
    ))

    assert result["implementationReady"] is False
    assert "scan-errors" in result["blockers"]
