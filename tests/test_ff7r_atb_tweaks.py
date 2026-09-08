from __future__ import annotations

import json
from pathlib import Path
import struct

import pytest

from games.ff7r.atb_tweaks import (
    ATB_ABILITY_ASSET,
    ATB_GUARD_ASSET,
    ATB_RESIDENT_ASSET,
    ATB_SETTINGS_ASSET,
    DEFAULT_ATB_CONFIG,
    discover_atb_sources,
    load_atb_config,
    materialize_atb_overrides,
    resource_spec,
    save_atb_config,
    save_virtual_edits,
    validate_atb_config,
)
from games.ff7r.dataobject import FLOAT, INT32, DataObjectPackage


def _fstring(value: str) -> bytes:
    raw = value.encode("utf-8") + b"\0"
    return struct.pack("<i", len(raw)) + raw


def _package(properties, entries):
    names = ["Fixture"]
    for prop_name, _type_code, _array in properties:
        if prop_name not in names:
            names.append(prop_name)
    for entry in entries:
        if entry["tag"] not in names:
            names.append(entry["tag"])

    header = bytearray()
    header += struct.pack("<Iii", 0x9E2A83C1, -4, 0)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    header += struct.pack("<i", 0)
    counts_offset = len(header)
    header += b"\0" * 24
    names_offset = len(header)
    for name in names:
        header += _fstring(name) + b"\0\0\0\0"
    exports_offset = len(header)
    header += struct.pack("<iiii", 0, 0, 0, 0)
    header += struct.pack("<iI", 0, 0)
    header += struct.pack("<Iqq", 0, 0, 0)
    header += b"\0\0\0" + (b"\0" * 16) + struct.pack("<i", 0) + b"\0\1"
    struct.pack_into("<i", header, 20, len(header))
    struct.pack_into("<iiiiii", header, counts_offset,
                     len(names), names_offset, 0, 0, 1, exports_offset)

    name_index = {name: index for index, name in enumerate(names)}
    fname = lambda name: struct.pack("<iI", name_index[name], 0)

    def scalar(type_code, value):
        if type_code == FLOAT:
            return struct.pack("<f", float(value))
        if type_code == INT32:
            return struct.pack("<i", int(value))
        raise AssertionError(f"unsupported fixture type {type_code}")

    uexp = bytearray(b"\0" * 0x0A)
    uexp += struct.pack("<ii", len(entries), len(properties))
    for prop_name, type_code, _array in properties:
        uexp += fname(prop_name) + struct.pack("<B", type_code)
    for entry in entries:
        uexp += fname(entry["tag"])
        for prop_name, type_code, is_array in properties:
            value = entry["values"][prop_name]
            if is_array:
                uexp += struct.pack("<i", len(value))
                for element in value:
                    uexp += scalar(type_code, element)
            else:
                uexp += scalar(type_code, value)
    return bytes(header), bytes(uexp)


def _write_pair(root: Path, name: str, pair):
    directory = root / "End" / "Content" / "GameContents" / "DataObject" / "Resident"
    directory.mkdir(parents=True, exist_ok=True)
    uasset = directory / f"{name}.uasset"
    uexp = directory / f"{name}.uexp"
    uasset.write_bytes(pair[0])
    uexp.write_bytes(pair[1])
    asset = f"End/Content/GameContents/DataObject/Resident/{name}"
    return {
        "asset": asset,
        "name": name,
        "group": "Resident",
        "uasset": {"fixture": uasset.as_posix()},
        "uexp": {"fixture": uexp.as_posix()},
    }


def _index(tmp_path: Path):
    resident = _package(
        [("ParamFloat", FLOAT, False), ("ParamInt", INT32, False)],
        [
            {"tag": "ATB_Player", "values": {"ParamFloat": 1.0, "ParamInt": 0}},
            {"tag": "ATB_Guard", "values": {"ParamFloat": 0.1, "ParamInt": 0}},
            {"tag": "NotATB", "values": {"ParamFloat": 9.0, "ParamInt": 9}},
        ],
    )
    guard = _package(
        [
            ("GuardReactionNoneAddATB_Array", FLOAT, True),
            ("GuardReactionMediumAddATB_Array", FLOAT, True),
            ("GuardReactionLargeAddATB_Array", FLOAT, True),
        ],
        [{"tag": "Cloud", "values": {
            "GuardReactionNoneAddATB_Array": [10.0, 20.0],
            "GuardReactionMediumAddATB_Array": [30.0],
            "GuardReactionLargeAddATB_Array": [40.0],
        }}],
    )
    abilities = _package(
        [("ATB", INT32, False)],
        [
            {"tag": "Cloud_Braver", "values": {"ATB": 1000}},
            {"tag": "Cloud_FocusedThrust", "values": {"ATB": 1000}},
        ],
    )
    return {
        "schema": 2,
        "signature": {"fixture": str(tmp_path)},
        "signatureId": "atb-fixture",
        "pakVersions": {},
        "assets": [
            _write_pair(tmp_path, "ResidentParameter", resident),
            _write_pair(tmp_path, "BattlePlayerParameter", guard),
            _write_pair(tmp_path, "BattleAbility", abilities),
        ],
        "textAssets": [],
    }


def _source_package(tmp_path: Path, index: dict, name: str) -> DataObjectPackage:
    row = next(row for row in index["assets"] if row["name"] == name)
    return DataObjectPackage(Path(row["uasset"]["fixture"]), Path(row["uexp"]["fixture"]), asset=row["asset"])


def test_atb_discovery_uses_installed_rows_and_authoritative_fields(tmp_path):
    index = _index(tmp_path)
    discovery = discover_atb_sources(tmp_path, tmp_path / "cache", index)
    resident_keys = {row["key"] for row in discovery["resident"]}
    assert "ATB_Player|ParamFloat" in resident_keys
    assert "ATB_Guard|ParamFloat" in resident_keys
    assert "NotATB|ParamFloat" in resident_keys  # tag contains ATB; discovery does not guess semantics beyond that
    assert len(discovery["guard"]) == 4
    assert {row["tag"] for row in discovery["abilities"]} == {"Cloud_Braver", "Cloud_FocusedThrust"}
    assert all(row["property"] == "ATB" for row in discovery["abilities"])


def test_atb_virtual_resources_save_only_semantic_config(tmp_path):
    index = _index(tmp_path)
    project = tmp_path / "project"

    settings = resource_spec(ATB_SETTINGS_ASSET, tmp_path, tmp_path / "cache", project, index)
    result = save_virtual_edits(
        tmp_path, tmp_path / "cache", project, index, ATB_SETTINGS_ASSET,
        source_sha256=settings["sourceSha256"], active_sha256=settings["activeSha256"],
        edits=[
            {"entry": 0, "property": "Enabled", "value": True},
            {"entry": 0, "property": "MovementMultiplier", "value": 0.75},
            {"entry": 0, "property": "RollReduction", "value": 125.0},
        ],
    )
    assert result["saved"] == 3

    resident = resource_spec(ATB_RESIDENT_ASSET, tmp_path, tmp_path / "cache", project, index)
    row_index = next(i for i, row in enumerate(resident["entries"]) if row["tag"] == "ATB_Player|ParamFloat")
    save_virtual_edits(
        tmp_path, tmp_path / "cache", project, index, ATB_RESIDENT_ASSET,
        source_sha256=resident["sourceSha256"], active_sha256=resident["activeSha256"],
        edits=[{"entry": row_index, "property": "OverrideValue", "value": 1.5}],
    )

    guard = resource_spec(ATB_GUARD_ASSET, tmp_path, tmp_path / "cache", project, index)
    guard_index = next(i for i, row in enumerate(guard["entries"]) if row["tag"].endswith("|0"))
    save_virtual_edits(
        tmp_path, tmp_path / "cache", project, index, ATB_GUARD_ASSET,
        source_sha256=guard["sourceSha256"], active_sha256=guard["activeSha256"],
        edits=[{"entry": guard_index, "property": "OverrideValue", "value": 55.0}],
    )

    abilities = resource_spec(ATB_ABILITY_ASSET, tmp_path, tmp_path / "cache", project, index)
    ability_index = next(i for i, row in enumerate(abilities["entries"]) if row["tag"] == "Cloud_Braver")
    save_virtual_edits(
        tmp_path, tmp_path / "cache", project, index, ATB_ABILITY_ASSET,
        source_sha256=abilities["sourceSha256"], active_sha256=abilities["activeSha256"],
        edits=[{"entry": ability_index, "property": "OverrideATB", "value": 500}],
    )

    config = load_atb_config(project)
    assert config["enabled"] is True
    assert config["movementMultiplier"] == 0.75
    assert config["rollReduction"] == 125.0
    assert config["residentOverrides"]["ATB_Player|ParamFloat"] == 1.5
    assert config["abilityCostOverrides"]["Cloud_Braver"] == 500
    assert not (project / "content").exists()


def test_enabled_atb_overrides_materialize_to_staging_without_touching_source(tmp_path):
    index = _index(tmp_path)
    project = tmp_path / "project"
    staging = tmp_path / "staging"
    source_resident_before = _source_package(tmp_path, index, "ResidentParameter").entries[0].values["ParamFloat"]
    source_guard_before = _source_package(tmp_path, index, "BattlePlayerParameter").entries[0].values["GuardReactionNoneAddATB_Array"][0]
    source_ability_before = _source_package(tmp_path, index, "BattleAbility").entries[0].values["ATB"]

    config = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    config.update(enabled=True, movementMultiplier=0.5, rollReduction=100.0)
    config["residentOverrides"] = {"ATB_Player|ParamFloat": 1.75}
    config["guardOverrides"] = {"Cloud|GuardReactionNoneAddATB_Array|0": 66.0}
    config["abilityCostOverrides"] = {"Cloud_Braver": 500}
    save_atb_config(project, config)

    materialized = materialize_atb_overrides(
        tmp_path, tmp_path / "cache", project, index, staging)
    assert len(materialized) == 3

    resident_asset = next(row["asset"] for row in index["assets"] if row["name"] == "ResidentParameter")
    guard_asset = next(row["asset"] for row in index["assets"] if row["name"] == "BattlePlayerParameter")
    ability_asset = next(row["asset"] for row in index["assets"] if row["name"] == "BattleAbility")
    resident = DataObjectPackage(staging / f"{resident_asset}.uasset", staging / f"{resident_asset}.uexp", asset=resident_asset)
    guard = DataObjectPackage(staging / f"{guard_asset}.uasset", staging / f"{guard_asset}.uexp", asset=guard_asset)
    ability = DataObjectPackage(staging / f"{ability_asset}.uasset", staging / f"{ability_asset}.uexp", asset=ability_asset)
    assert resident.entries[0].values["ParamFloat"] == pytest.approx(1.75)
    assert guard.entries[0].values["GuardReactionNoneAddATB_Array"][0] == pytest.approx(66.0)
    assert ability.entries[0].values["ATB"] == 500

    assert _source_package(tmp_path, index, "ResidentParameter").entries[0].values["ParamFloat"] == source_resident_before
    assert _source_package(tmp_path, index, "BattlePlayerParameter").entries[0].values["GuardReactionNoneAddATB_Array"][0] == source_guard_before
    assert _source_package(tmp_path, index, "BattleAbility").entries[0].values["ATB"] == source_ability_before


def test_disabled_atb_tweak_never_materializes_saved_overrides(tmp_path):
    index = _index(tmp_path)
    project = tmp_path / "project"
    config = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    config["enabled"] = False
    config["residentOverrides"] = {"ATB_Player|ParamFloat": 2.0}
    save_atb_config(project, config)
    staging = tmp_path / "staging"
    assert materialize_atb_overrides(tmp_path, tmp_path / "cache", project, index, staging) == []
    assert not staging.exists()


def test_atb_config_rejects_invalid_runtime_new_mechanics_and_costs():
    value = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    value["movementMultiplier"] = -0.1
    with pytest.raises(ValueError, match="at least"):
        validate_atb_config(value)

    value = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    value["rollReduction"] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        validate_atb_config(value)

    value = json.loads(json.dumps(DEFAULT_ATB_CONFIG))
    value["abilityCostOverrides"] = {"Cloud_Braver": 1.5}
    with pytest.raises(ValueError, match="integer"):
        validate_atb_config(value)
