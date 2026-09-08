from __future__ import annotations

import struct

import pytest

import games.ff7r.encounter_tweaks as encounters
from games.ff7r.dataobject import BYTE, INT32, NAME, DataObjectPackage, PACKAGE_TAG


def _fstring(value: str) -> bytes:
    encoded = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(encoded)) + encoded


def _fixture_dataobject(properties, rows, *, export_name="Fixture") -> tuple[bytes, bytes]:
    names: list[str] = []

    def add_name(value: str) -> None:
        if value not in names:
            names.append(value)

    add_name(export_name)
    for prop_name, _type_code in properties:
        add_name(prop_name)
    for tag, values in rows:
        add_name(tag)
        for prop_name, type_code in properties:
            if type_code != NAME:
                continue
            value = values[prop_name]
            if prop_name.endswith("_Array"):
                for item in value:
                    add_name(str(item))
            else:
                add_name(str(value))

    name_index = {name: index for index, name in enumerate(names)}

    def fname(value: str) -> bytes:
        return struct.pack("<iI", name_index[value], 0)

    def scalar(type_code: int, value) -> bytes:
        if type_code == BYTE:
            return struct.pack("<B", int(value))
        if type_code == INT32:
            return struct.pack("<i", int(value))
        if type_code == NAME:
            return fname(str(value))
        raise AssertionError(f"unsupported fixture type {type_code}")

    uexp = bytearray(b"\0" * 0x0A)
    uexp += struct.pack("<ii", len(rows), len(properties))
    for prop_name, type_code in properties:
        uexp += fname(prop_name) + struct.pack("<B", type_code)
    for tag, values in rows:
        uexp += fname(tag)
        for prop_name, type_code in properties:
            value = values[prop_name]
            if prop_name.endswith("_Array"):
                uexp += struct.pack("<i", len(value))
                for item in value:
                    uexp += scalar(type_code, item)
            else:
                uexp += scalar(type_code, value)

    header = bytearray()
    header += struct.pack("<Iii", PACKAGE_TAG, -4, 0)
    header += struct.pack("<i", 0)  # licensee version
    header += struct.pack("<i", 0)  # custom versions
    header += struct.pack("<i", 0)  # header size placeholder
    header += struct.pack("<i", 0)  # empty package-group FString
    header += struct.pack("<i", 0)  # package flags
    counts_offset = len(header)
    header += b"\0" * 24
    names_offset = len(header)
    for name in names:
        header += _fstring(name) + b"\0\0\0\0"
    exports_offset = len(header)
    header += struct.pack("<iiii", 0, 0, 0, 0)
    header += fname(export_name)
    header += struct.pack("<Iqq", 0, len(uexp), 0)
    header += b"\0\0\0" + (b"\0" * 16) + struct.pack("<i", 0) + b"\0\1"
    struct.pack_into("<i", header, 20, len(header))
    struct.pack_into(
        "<iiiiii",
        header,
        counts_offset,
        len(names),
        names_offset,
        0,
        0,
        1,
        exports_offset,
    )
    return bytes(header), bytes(uexp)


def _packages_for_target():
    scene_uasset, scene_uexp = _fixture_dataobject(
        [
            ("BattleCharaSpecID_Array", NAME),
            ("Level_Array", BYTE),
            ("RoleType_Array", INT32),
        ],
        [
            (
                "btsc_tnnl4_305",
                {
                    "BattleCharaSpecID_Array": [
                        "EN_Flame_A",
                        "EN_Turret",
                        "EN_Flame_B",
                        "EN_Turret",
                    ],
                    "Level_Array": [11, 12, 13, 14],
                    "RoleType_Array": [101, 102, 103, 104],
                },
            )
        ],
        export_name="BattleScene",
    )
    chara_uasset, chara_uexp = _fixture_dataobject(
        [("EnemyBookID", NAME)],
        [
            ("EN_Flame_A", {"EnemyBookID": "BOOK_Flame"}),
            ("EN_Flame_B", {"EnemyBookID": "BOOK_Flame"}),
            ("EN_Turret", {"EnemyBookID": "BOOK_Turret"}),
        ],
        export_name="BattleCharaSpec",
    )
    book_uasset, book_uexp = _fixture_dataobject(
        [("TipsTextID", NAME)],
        [
            ("BOOK_Flame", {"TipsTextID": "$Enemy_Flame"}),
            ("BOOK_Turret", {"TipsTextID": "$Enemy_Turret"}),
        ],
        export_name="EnemyBook",
    )
    return {
        encounters.BATTLE_SCENE_TABLE: DataObjectPackage.from_bytes(
            scene_uasset, scene_uexp, asset="End/Content/GameContents/DataObject/BattleScene"
        ),
        encounters.BATTLE_CHARA_TABLE: DataObjectPackage.from_bytes(
            chara_uasset, chara_uexp, asset="End/Content/GameContents/DataObject/BattleCharaSpec"
        ),
        encounters.ENEMY_BOOK_TABLE: DataObjectPackage.from_bytes(
            book_uasset, book_uexp, asset="End/Content/GameContents/DataObject/EnemyBook"
        ),
    }


def test_discovers_unique_tnnl4_two_flame_two_turret_encounter(monkeypatch, tmp_path):
    packages = _packages_for_target()
    monkeypatch.setattr(
        encounters,
        "_load_source",
        lambda _game, _data, _index, basename: packages.get(basename),
    )
    monkeypatch.setattr(
        encounters,
        "resident_text_map",
        lambda *_args, **_kwargs: {
            "$Enemy_Flame": "Flametrooper",
            "$Enemy_Turret": "Sentry Launcher",
        },
    )

    result = encounters.discover_chapter5_subway_encounter(
        tmp_path / "game", tmp_path / "data", tmp_path / "project", {}
    )
    assert result["candidateCount"] == 1
    candidate = result["candidates"][0]
    assert candidate["sceneTag"] == "btsc_tnnl4_305"
    assert candidate["kinds"] == ["flametrooper", "turret", "flametrooper", "turret"]
    assert candidate["turretIndices"] == [1, 3]
    assert candidate["removeIndex"] == 3
    assert candidate["parallelArrayLengths"] == {
        "BattleCharaSpecID_Array": 4,
        "Level_Array": 4,
        "RoleType_Array": 4,
    }
    assert candidate["unexpectedParallelArrayLengths"] == []


def _discovery_fixture(asset: str, ids=None) -> dict:
    ids = list(ids or ["EN_Flame_A", "EN_Turret", "EN_Flame_B", "EN_Turret"])
    return {
        "language": "US",
        "battleSceneAsset": asset,
        "battleCharaAsset": "",
        "enemyBookAsset": "",
        "candidateCount": 1,
        "candidates": [
            {
                "entry": 0,
                "sceneTag": "btsc_tnnl4_305",
                "battleCharaSpecIds": ids,
                "kinds": ["flametrooper", "turret", "flametrooper", "turret"],
                "flametrooperIndices": [0, 2],
                "turretIndices": [1, 3],
                "removeIndex": 3,
                "parallelArrayLengths": {
                    "BattleCharaSpecID_Array": 4,
                    "Level_Array": 4,
                    "RoleType_Array": 4,
                },
                "unexpectedParallelArrayLengths": [],
            }
        ],
        "classificationCounts": {"flametrooper": 2, "turret": 1},
        "errors": [],
        "notes": [],
    }


def _enable_tweak(project):
    encounters.save_encounter_config(
        project,
        {"schemaVersion": encounters.ENCOUNTER_SCHEMA_VERSION, "chapter5SubwayReducedTurret": True},
    )


def test_materializer_removes_same_turret_slot_from_all_parallel_arrays(monkeypatch, tmp_path):
    asset = "End/Content/GameContents/DataObject/BattleScene"
    uasset, uexp = _fixture_dataobject(
        [
            ("BattleCharaSpecID_Array", NAME),
            ("Level_Array", BYTE),
            ("RoleType_Array", INT32),
        ],
        [
            (
                "btsc_tnnl4_305",
                {
                    "BattleCharaSpecID_Array": [
                        "EN_Flame_A",
                        "EN_Turret",
                        "EN_Flame_B",
                        "EN_Turret",
                    ],
                    "Level_Array": [11, 12, 13, 14],
                    "RoleType_Array": [101, 102, 103, 104],
                },
            )
        ],
        export_name="BattleScene",
    )
    source = tmp_path / "source"
    source.mkdir()
    source_uasset = source / "BattleScene.uasset"
    source_uexp = source / "BattleScene.uexp"
    source_uasset.write_bytes(uasset)
    source_uexp.write_bytes(uexp)
    original_uasset = source_uasset.read_bytes()
    original_uexp = source_uexp.read_bytes()

    project = tmp_path / "project"
    _enable_tweak(project)
    discovery = _discovery_fixture(asset)
    monkeypatch.setattr(
        encounters, "discover_chapter5_subway_encounter", lambda *_args, **_kwargs: discovery
    )
    monkeypatch.setattr(
        encounters, "extract_pair", lambda *_args, **_kwargs: (source_uasset, source_uexp)
    )

    staging = tmp_path / "staging"
    result = encounters.materialize_encounter_tweaks(
        tmp_path / "game", tmp_path / "data", project, {}, staging
    )
    assert len(result) == 1
    assert result[0]["removedIndex"] == 3
    assert result[0]["removedBattleCharaSpecId"] == "EN_Turret"
    assert result[0]["deletedFields"] == [
        "BattleCharaSpecID_Array",
        "Level_Array",
        "RoleType_Array",
    ]
    assert result[0]["resultBattleCharaSpecIds"] == [
        "EN_Flame_A",
        "EN_Turret",
        "EN_Flame_B",
    ]

    staged_package = DataObjectPackage(
        staging / f"{asset}.uasset", staging / f"{asset}.uexp", asset=asset
    )
    row = staged_package.entries[0].values
    assert row["BattleCharaSpecID_Array"] == ["EN_Flame_A", "EN_Turret", "EN_Flame_B"]
    assert row["Level_Array"] == [11, 12, 13]
    assert row["RoleType_Array"] == [101, 102, 103]

    assert source_uasset.read_bytes() == original_uasset
    assert source_uexp.read_bytes() == original_uexp
    source_package = DataObjectPackage(source_uasset, source_uexp, asset=asset)
    assert len(source_package.entries[0].values["BattleCharaSpecID_Array"]) == 4


def test_materializer_supports_two_distinct_turret_specs(monkeypatch, tmp_path):
    asset = "End/Content/GameContents/DataObject/BattleScene"
    ids = ["EN_Flame_A", "EN_Turret_A", "EN_Flame_B", "EN_Turret_B"]
    uasset, uexp = _fixture_dataobject(
        [
            ("BattleCharaSpecID_Array", NAME),
            ("Level_Array", BYTE),
            ("RoleType_Array", INT32),
        ],
        [
            (
                "btsc_tnnl4_305",
                {
                    "BattleCharaSpecID_Array": ids,
                    "Level_Array": [11, 12, 13, 14],
                    "RoleType_Array": [101, 102, 103, 104],
                },
            )
        ],
        export_name="BattleScene",
    )
    source = tmp_path / "source-distinct"
    source.mkdir()
    source_uasset = source / "BattleScene.uasset"
    source_uexp = source / "BattleScene.uexp"
    source_uasset.write_bytes(uasset)
    source_uexp.write_bytes(uexp)

    project = tmp_path / "project-distinct"
    _enable_tweak(project)
    discovery = _discovery_fixture(asset, ids)
    monkeypatch.setattr(
        encounters, "discover_chapter5_subway_encounter", lambda *_args, **_kwargs: discovery
    )
    monkeypatch.setattr(
        encounters, "extract_pair", lambda *_args, **_kwargs: (source_uasset, source_uexp)
    )

    result = encounters.materialize_encounter_tweaks(
        tmp_path / "game", tmp_path / "data", project, {}, tmp_path / "staging-distinct"
    )
    assert result[0]["removedBattleCharaSpecId"] == "EN_Turret_B"
    assert result[0]["resultBattleCharaSpecIds"] == [
        "EN_Flame_A",
        "EN_Turret_A",
        "EN_Flame_B",
    ]


def test_disabled_encounter_tweak_does_not_materialize(monkeypatch, tmp_path):
    called = False

    def discovery(*_args, **_kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(encounters, "discover_chapter5_subway_encounter", discovery)
    result = encounters.materialize_encounter_tweaks(
        tmp_path / "game", tmp_path / "data", tmp_path / "project", {}, tmp_path / "staging"
    )
    assert result == []
    assert called is False


def test_materializer_fails_closed_on_ambiguous_or_misaligned_encounter(monkeypatch, tmp_path):
    project = tmp_path / "project"
    _enable_tweak(project)

    ambiguous = _discovery_fixture("End/Content/GameContents/DataObject/BattleScene")
    ambiguous["candidateCount"] = 2
    ambiguous["candidates"] = ambiguous["candidates"] * 2
    monkeypatch.setattr(
        encounters, "discover_chapter5_subway_encounter", lambda *_args, **_kwargs: ambiguous
    )
    with pytest.raises(RuntimeError, match="requires exactly one"):
        encounters.materialize_encounter_tweaks(
            tmp_path / "game", tmp_path / "data", project, {}, tmp_path / "staging-a"
        )

    misaligned = _discovery_fixture("End/Content/GameContents/DataObject/BattleScene")
    misaligned["candidates"][0]["unexpectedParallelArrayLengths"] = ["RoleType_Array"]
    monkeypatch.setattr(
        encounters, "discover_chapter5_subway_encounter", lambda *_args, **_kwargs: misaligned
    )
    with pytest.raises(RuntimeError, match="unexpected per-enemy array lengths"):
        encounters.materialize_encounter_tweaks(
            tmp_path / "game", tmp_path / "data", project, {}, tmp_path / "staging-b"
        )
