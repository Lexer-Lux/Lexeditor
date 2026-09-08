from games.ff7r.dog_whistle_safety import assess_dog_whistle_probe


def _report(*, whistle_rows=(), key_items=(), canine=(), native_hits=(), errors=()):
    return {
        "item": {
            "rowCandidates": list(whistle_rows),
            "whistleNameMapCandidates": ["Whistle"],
        },
        "chapterProgression": {
            "addKeyItemPropertyPresent": True,
            "referencedKeyItemsThatAreItemRows": list(key_items),
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


def test_new_item_row_is_explicit_blocker_when_no_existing_whistle_item_exists():
    result = assess_dog_whistle_probe(_report())

    assert result["implementationReady"] is False
    assert "no-existing-whistle-item-row" in result["blockers"]
    assert "writer-cannot-add-item-row" in result["blockers"]
    assert result["itemAuthoring"]["writerSupportsNewItemRow"] is False


def test_existing_candidate_never_authorizes_repurposing():
    result = assess_dog_whistle_probe(_report(whistle_rows=[{"tag": "SomeWhistle"}]))

    assert result["itemAuthoring"]["existingWhistleRowCandidates"] == 1
    assert result["itemAuthoring"]["safeExistingRowProved"] is False
    assert "existing-whistle-row-not-proved-safe-to-repurpose" in result["blockers"]


def test_chapter_reward_correlation_is_plausible_but_append_remains_blocked():
    result = assess_dog_whistle_probe(_report(key_items=["key_item_01"]))

    assert result["chapterAward"]["dataAwardPathPlausible"] is True
    assert result["chapterAward"]["writerSupportsArrayAppend"] is False
    assert "writer-cannot-append-chapter-reward" in result["blockers"]


def test_set_target_plus_ai_lookup_marks_runtime_retarget_anchors_present():
    result = assess_dog_whistle_probe(_report(native_hits=[("SetTarget", 2), ("GetBattleAI", 1)]))

    assert result["runtimeRetarget"]["retargetAnchorsPresent"] is True
    assert "runtime-retarget-anchors-unproved" not in result["blockers"]


def test_canine_coverage_counts_groups_and_battle_rows_without_claiming_validation():
    result = assess_dog_whistle_probe(_report(canine=[
        {"battleCharaRows": ["dog_a", "dog_b"]},
        {"battleCharaRows": ["dog_c"]},
    ]))

    assert result["canineCoverage"] == {
        "candidateGroups": 2,
        "battleCharaRows": 3,
        "installedBattleValidationRequired": True,
    }


def test_scan_error_blocks_even_otherwise_good_research_evidence():
    result = assess_dog_whistle_probe(_report(
        whistle_rows=[{"tag": "Whistle"}],
        key_items=["Whistle"],
        canine=[{"battleCharaRows": ["dog"]}],
        native_hits=[("SetTarget", 1), ("GetBattleAIControllerFromID", 1)],
        errors=["EnemyBook: unsupported"],
    ))

    assert result["implementationReady"] is False
    assert "scan-errors" in result["blockers"]
