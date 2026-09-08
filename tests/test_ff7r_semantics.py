from __future__ import annotations

import struct
from pathlib import Path

from games.ff7r.dataobject import (
    BOOLEAN_BYTE, BYTE, INT32, NAME, STRING,
)
from games.ff7r.semantics import economy_payload, loot_payload


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
        for (prop_name, type_code, is_array) in properties:
            values = entry["values"][prop_name]
            scan = values if is_array else [values]
            if type_code == NAME:
                for value in scan:
                    if value not in names:
                        names.append(value)

    header = bytearray()
    header += struct.pack("<Iii", 0x9E2A83C1, -4, 0)
    header += struct.pack("<i", 0)  # licensee
    header += struct.pack("<i", 0)  # custom versions
    header += struct.pack("<i", 0)  # header size placeholder
    header += struct.pack("<i", 0)  # empty package group FString
    header += struct.pack("<i", 0)  # flags
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

    def scalar(type_code, value, *, array=False):
        if type_code == STRING:
            return _fstring(value)
        if type_code == NAME:
            return fname(value)
        if type_code in (BYTE, BOOLEAN_BYTE):
            return struct.pack("<B", int(value))
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
                    uexp += scalar(type_code, element, array=True)
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


def _fixture_index(tmp_path: Path):
    equipment = _package(
        [
            ("ItemNameLabel", STRING, False),
            ("BuyValue", INT32, False),
            ("SaleValue", INT32, False),
            ("CanSale", BOOLEAN_BYTE, False),
        ],
        [
            {"tag": "WEP_CLOUD_01", "values": {
                "ItemNameLabel": "$Item_BusterSword", "BuyValue": 1000,
                "SaleValue": 500, "CanSale": 1,
            }},
            {"tag": "POTION", "values": {
                "ItemNameLabel": "$Item_Potion", "BuyValue": 50,
                "SaleValue": 25, "CanSale": 1,
            }},
        ],
    )
    loot = _package(
        [
            ("NormalItemName_Array", NAME, True),
            ("NormalItemPercent_Array", BYTE, True),
            ("RareItemName_Array", NAME, True),
            ("RareItemPercent_Array", BYTE, True),
            ("StealItemName_Array", NAME, True),
            ("StealItemQuantity_Array", BYTE, True),
        ],
        [
            {"tag": "EN0001_00", "values": {
                "NormalItemName_Array": ["POTION"],
                "NormalItemPercent_Array": [50],
                "RareItemName_Array": ["WEP_CLOUD_01"],
                "RareItemPercent_Array": [5],
                "StealItemName_Array": ["POTION"],
                "StealItemQuantity_Array": [2],
            }},
        ],
    )
    rows = [
        _write_pair(tmp_path, "Equipment", equipment),
        _write_pair(tmp_path, "BattleItemPossession", loot),
    ]
    return {
        "schema": 2,
        "signature": {"fixture": str(tmp_path)},
        "signatureId": "semantic-fixture",
        "pakVersions": {},
        "assets": rows,
        "textAssets": [],
    }


def test_economy_exposes_only_authoritative_installed_fields(tmp_path):
    index = _fixture_index(tmp_path)
    payload = economy_payload(tmp_path, tmp_path / "cache", tmp_path / "project", index)
    assert payload["available"] is True
    assert len(payload["tables"]) == 1
    table = payload["tables"][0]
    assert table["name"] == "Equipment"
    assert table["properties"] == ["BuyValue", "SaleValue", "CanSale"]
    assert table["rows"][0]["fields"]["BuyValue"]["value"] == 1000
    assert table["rows"][0]["fields"]["SaleValue"]["value"] == 500
    assert table["rows"][0]["fields"]["CanSale"]["value"] is True


def test_loot_keeps_normal_rare_and_steal_semantics_separate(tmp_path):
    index = _fixture_index(tmp_path)
    payload = loot_payload(tmp_path, tmp_path / "cache", tmp_path / "project", index)
    assert payload["available"] is True
    assert payload["asset"].endswith("/BattleItemPossession")
    row = payload["rows"][0]
    groups = {group["kind"]: group for group in row["groups"]}
    assert groups["normal"]["slots"][0] == {
        "index": 0, "item": "POTION", "itemName": "POTION",
        "chance": 50, "quantity": None,
    }
    assert groups["rare"]["slots"][0]["chance"] == 5
    assert groups["steal"]["slots"][0]["quantity"] == 2
    choices = {choice["id"] for choice in payload["itemChoices"]}
    assert {"POTION", "WEP_CLOUD_01"} <= choices


def test_semantics_fail_closed_when_known_schema_is_absent(tmp_path):
    unknown = _package([("SomethingElse", INT32, False)], [
        {"tag": "ROW", "values": {"SomethingElse": 1}},
    ])
    index = {
        "schema": 2,
        "signature": {"fixture": str(tmp_path)},
        "signatureId": "unknown-fixture",
        "pakVersions": {},
        "assets": [_write_pair(tmp_path, "Item", unknown)],
        "textAssets": [],
    }
    economy = economy_payload(tmp_path, tmp_path / "cache", tmp_path / "project", index)
    assert economy["available"] is False
    loot = loot_payload(tmp_path, tmp_path / "cache", tmp_path / "project", index)
    assert loot["available"] is False
