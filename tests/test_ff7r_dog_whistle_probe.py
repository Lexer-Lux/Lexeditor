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


def test_dog_whistle_probe_correlates_item_names_chapter_awards_canines_and_runtime(monkeypatch):
    item = _package(
        "End/DataObject/Item",
        ["ItemNameLabel", "AbilityID", "Category"],
        [
            _entry("POTION", {"ItemNameLabel": "$Potion", "AbilityID": "PotionAbility", "Category": 0}),
            _entry("KEY_WEDGE_WHISTLE", {"ItemNameLabel": "$DogWhistle", "AbilityID": "", "Category": 5}),
        ],
        names=["Item", "POTION", "KEY_WEDGE_WHISTLE", "DogWhistle"],
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
        probe.CHAPTER_TABLE: chapter,
        probe.ENEMY_BOOK_TABLE: enemy_book,
        probe.BATTLE_CHARA_TABLE: battle,
    }
    monkeypatch.setattr(probe, "_load_data", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: ({
        "$DogWhistle": "Dog Whistle",
        "$Chapter4": "Mad Dash",
        "$GuardDog": "Guard Dog",
        "$Soldier": "Security Officer",
        "$Potion": "Potion",
    }, []))
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {
        "needles": [{"needle": name, "hits": []} for name in needles],
        "timestampHex": "0x12345678",
    })

    result = probe.probe_dog_whistle_sources("game", "data", "project", {})
    assert result["item"]["whistleNameMapCandidates"] == ["DogWhistle"]
    assert result["item"]["rowCandidates"][0]["tag"] == "KEY_WEDGE_WHISTLE"
    assert result["chapterProgression"]["referencedKeyItemsThatAreItemRows"] == ["KEY_WEDGE_WHISTLE"]
    assert result["chapterProgression"]["chaptersWithKeyItemAdds"][0]["chapterName"] == "Mad Dash"
    canine = result["canineEnemies"][0]
    assert canine["enemyBookId"] == "EB_GUARD_DOG"
    assert canine["battleCharaRows"] == ["EN_GUARD_DOG"]
    assert result["knownContracts"]["itemUseField"] == "Item.AbilityID"
    assert result["knownContracts"]["enemyRetargetMethod"].endswith("SetTarget(AEndCharacter*)")


def test_whistle_term_matching_handles_underscores_and_compact_identifiers():
    assert probe._contains_term("KEY_DOG_WHISTLE", probe.WHISTLE_TERMS)
    assert probe._contains_term("DogWhistleInternal", probe.WHISTLE_TERMS)
    assert not probe._contains_term("DOG_TAG", probe.WHISTLE_TERMS)


def test_probe_does_not_claim_keyitem_award_targets_item_table_when_ids_do_not_correlate(monkeypatch):
    item = _package("Item", ["AbilityID"], [_entry("POTION", {"AbilityID": "Potion"})])
    chapter = _package("Chapter", ["AddKeyItem_Array"], [
        _entry("Chapter04", {"AddKeyItem_Array": ["KEY_UNKNOWN"]}),
    ])
    packages = {probe.ITEM_TABLE: item, probe.CHAPTER_TABLE: chapter}
    monkeypatch.setattr(probe, "_load_data", lambda _g, _d, _i, name: packages.get(name))
    monkeypatch.setattr(probe, "_all_text_map", lambda *_args, **_kwargs: ({}, []))
    monkeypatch.setattr(probe, "probe_installed_exe", lambda _root, *, needles: {"needles": []})
    result = probe.probe_dog_whistle_sources("g", "d", "p", {})
    assert result["chapterProgression"]["referencedKeyItemsThatAreItemRows"] == []
