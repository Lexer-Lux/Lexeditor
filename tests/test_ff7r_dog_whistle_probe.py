from types import SimpleNamespace

from games.ff7r import dog_whistle_probe as probe


def _entry(tag, values):
    return SimpleNamespace(tag=tag, values=values)


def _package(asset, properties, entries, names=()):
    return SimpleNamespace(
        asset=asset,
        properties=[SimpleNamespace(name=name) for name in properties],
        entries=entries,
        uasset=SimpleNamespace(names=tuple(names)),
    )


def _text_fixture():
    lookup = {
        "$DogWhistle": "Dog Whistle",
        "$Chapter4": "Mad Dash",
        "$GuardDog": "Guard Dog",
        "$Soldier": "Security Officer",
        "$Potion": "Potion",
        "$PotionAbility": "Restore HP.",
    }
    owners = {key: "End/Text/US/Resident_TxtRes" for key in lookup}
    return lookup, owners, []


def test_dog_whistle_probe_correlates_item_ability_chapter_canines_and_runtime(monkeypatch):
    item = _package(
        "End/DataObject/Item",
        ["ItemNameLabel", "AbilityID", "Category"],
        [
            _entry("POTION", {"ItemNameLabel": "$Potion", "AbilityID": "PotionAbility", "Category": 0}),
            _entry("KEY_WEDGE_WHISTLE", {"ItemNameLabel": "$DogWhistle", "AbilityID": "", "Category": 5}),
        ],
        names=["Item", "POTION", "KEY_WEDGE_WHISTLE", "DogWhistle"],
    )
    ability = _package(
        "End/DataObject/BattleAbility",
        ["UniqueID", "Name", "CommandType", "CommandTargetType", "ATB", "MP", "TargetCount"],
        [
            _entry("PotionAbility", {
                "UniqueID": 100,
                "Name": "$PotionAbility",
                "CommandType": 2,
                "CommandTargetType": 1,
                "ATB": 1000,
                "MP": 0,
                "TargetCount": 1,
            }),
        ],
        names=["BattleAbility", "PotionAbility", "DogWhistleAbility"],
    )
    chapter = _package(
        "End/DataObject/Chapter",
        ["UniqueID", "ChapterNameID", "AddKeyItem_Array"],
        [
            _entry("Chapter04", {
                "UniqueID": 4,
                "ChapterNameID": "$Chapter4",
                "AddKeyItem_Array": ["KEY_WEDGE_WHISTLE"],
            }),
        ],
    )
    enemy_book = _package(
        "End/DataObject/EnemyBook",
        ["NameTextID"],
        [
            _entry("EB_GUARD_DOG", {"NameTextID": "$GuardDog"}),
            _entry("EB_SOLDIER", {"NameTextID": "$Soldier"}),
        ],
    )
    battle = _package(
        "End/DataObject/BattleCharaSpec",
        ["EnemyBookID"],
        [
            _entry("EN_GUARD_DOG", {"EnemyBookID": "EB_GUARD_DOG"}),
            _entry("EN_SOLDIER", {"EnemyBookID": "EB_SOLDIER"}),
        ],
    )

    packages = {
        probe.ITEM_TABLE: item,
        probe.BATTLE_ABILITY_TABLE: ability,
        probe.CHAPTER_TABLE: chapter,
        probe.ENEMY_BOOK_TABLE: enemy_book,
        probe.BATTLE_CHARA_TABLE: battle,
    }
    monkeypatch.setattr(probe, "_load_data", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: _text_fixture())
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {
        "needles": [{"needle": name, "hits": []} for name in needles],
        "timestampHex": "0x12345678",
    })

    result = probe.probe_dog_whistle_sources("game", "data", "project", {})
    assert result["item"]["whistleNameMapCandidates"] == ["DogWhistle", "KEY_WEDGE_WHISTLE"]
    assert result["item"]["unusedWhistleNameMapCandidates"] == ["DogWhistle"]
    assert result["item"]["rowCandidates"][0]["tag"] == "KEY_WEDGE_WHISTLE"
    assert result["item"]["abilityBackedTemplateCandidates"][0]["tag"] == "POTION"
    linked = result["item"]["linkedBattleAbilityTemplateCandidates"][0]
    assert linked["battleAbilityTag"] == "PotionAbility"
    assert linked["battleAbilityValues"]["ATB"] == 1000
    assert linked["battleAbilityValues"]["CommandTargetType"] == 1
    assert result["item"]["unresolvedAbilityTemplateCandidates"] == []
    template_text = linked["resolvedText"][0]
    assert template_text["textAsset"] == "End/Text/US/Resident_TxtRes"

    ability_result = result["battleAbility"]
    assert ability_result["whistleNameMapCandidates"] == ["DogWhistleAbility"]
    assert ability_result["unusedWhistleNameMapCandidates"] == ["DogWhistleAbility"]
    assert "CommandType" in ability_result["properties"]

    chapter_result = result["chapterProgression"]
    assert chapter_result["referencedKeyItemsThatAreItemRows"] == ["KEY_WEDGE_WHISTLE"]
    assert chapter_result["chaptersWithKeyItemAdds"][0]["chapterName"] == "Mad Dash"
    assert chapter_result["chapter4Candidates"][0]["tag"] == "Chapter04"
    assert set(chapter_result["chapter4Candidates"][0]["chapter4Signals"]) == {"row-tag", "unique-id"}

    canine = result["canineEnemies"][0]
    assert canine["enemyBookId"] == "EB_GUARD_DOG"
    assert canine["battleCharaRows"] == ["EN_GUARD_DOG"]
    assert result["knownContracts"]["itemUseField"].startswith("FEndDataTableItem.AbilityID")
    assert result["knownContracts"]["activeEnemyEnumeration"].startswith("UEndBattleAPI::GetEnemyMembersRef")
    assert result["knownContracts"]["battleCharaIdLookup"].startswith("UEndBattleAPI::GetBattleCharaSpec_DataTableID")
    assert result["knownContracts"]["enemyRetargetMethod"].endswith("SetTarget(AEndCharacter*)")


def test_item_ability_id_without_matching_battleability_row_stays_explicitly_unresolved(monkeypatch):
    item = _package(
        "Item", ["AbilityID"], [_entry("POTION", {"AbilityID": "MissingAbility"})]
    )
    ability = _package("BattleAbility", ["CommandType"], [], names=["DogWhistleAbility"])
    packages = {probe.ITEM_TABLE: item, probe.BATTLE_ABILITY_TABLE: ability}
    monkeypatch.setattr(probe, "_load_data", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: ({}, {}, []))
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {"needles": []})

    result = probe.probe_dog_whistle_sources("g", "d", "p", {})
    assert result["item"]["linkedBattleAbilityTemplateCandidates"] == []
    assert result["item"]["unresolvedAbilityTemplateCandidates"][0]["abilityId"] == "MissingAbility"


def test_whistle_term_matching_handles_underscores_and_compact_identifiers():
    assert probe._contains_term("KEY_DOG_WHISTLE", probe.WHISTLE_TERMS)
    assert probe._contains_term("DogWhistleInternal", probe.WHISTLE_TERMS)
    assert not probe._contains_term("DOG_TAG", probe.WHISTLE_TERMS)


def test_chapter4_detection_uses_evidence_not_row_order():
    lookup = {"$C1": "The Destruction of Mako Reactor 1", "$C4": "Chapter 4: Mad Dash"}
    owners = {key: "Resident" for key in lookup}
    first = _entry("Chapter01", {"UniqueID": 1, "ChapterNameID": "$C1"})
    fourth = _entry("OpaqueRowName", {"UniqueID": 99, "ChapterNameID": "$C4"})

    assert probe._chapter4_signals(first, probe._resolved_entry_text(first, lookup, owners)) == []
    assert probe._chapter4_signals(fourth, probe._resolved_entry_text(fourth, lookup, owners)) == [
        "resolved-text:ChapterNameID"
    ]


def test_probe_does_not_claim_keyitem_award_targets_item_table_when_ids_do_not_correlate(monkeypatch):
    item = _package("Item", ["AbilityID"], [_entry("POTION", {"AbilityID": "Potion"})])
    chapter = _package("Chapter", ["AddKeyItem_Array"], [
        _entry("Chapter04", {"AddKeyItem_Array": ["KEY_UNKNOWN"]}),
    ])
    packages = {probe.ITEM_TABLE: item, probe.CHAPTER_TABLE: chapter}
    monkeypatch.setattr(probe, "_load_data", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: ({}, {}, []))
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {"needles": []})
    result = probe.probe_dog_whistle_sources("g", "d", "p", {})
    assert result["chapterProgression"]["referencedKeyItemsThatAreItemRows"] == []


def test_native_probe_requests_full_active_enemy_and_item_dispatch_research_route(monkeypatch):
    monkeypatch.setattr(probe, "_load_data", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: ({}, {}, []))
    captured = {}

    def fake_native(_root, *, needles):
        captured["needles"] = tuple(needles)
        return {"needles": []}

    monkeypatch.setattr(probe, "probe_installed_exe", fake_native)
    probe.probe_dog_whistle_sources("g", "d", "p", {})
    assert "GetEnemyMembersRef" in captured["needles"]
    assert "GetBattleCharaSpec_DataTableID" in captured["needles"]
    assert "GetBattleAIControllerFromID" in captured["needles"]
    assert "SetTarget" in captured["needles"]
    assert "RequestUseAbility" in captured["needles"]
