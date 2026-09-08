"""Semantic FF7R views layered over the generic DataObject reader.

These adapters deliberately validate the installed game's property names before
exposing controls. Public Remake evidence identifies Equipment.BuyValue and
BattleItemPossession as authoritative data surfaces; Rebirth's generated schema
provides useful candidate names for closely related fields, but a candidate is
never treated as present until the installed FF7R DataObject actually contains
it.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from .storage import load_package
from .text_storage import resident_text_map


ECONOMY_TABLE_NAMES = frozenset({"item", "equipment", "materia"})
ECONOMY_FIELDS = ("BuyValue", "SaleValue", "CanSale")
LOOT_TABLE_NAME = "battleitempossession"
LOOT_FIELD_PAIRS = (
    ("normal", "NormalItemName_Array", "NormalItemPercent_Array", None),
    ("rare", "RareItemName_Array", "RareItemPercent_Array", None),
    ("steal", "StealItemName_Array", None, "StealItemQuantity_Array"),
)
NAME_PROPERTY_HINTS = (
    "ItemNameLabel", "NameLabel", "ItemName", "Name", "DisplayName",
    "TextLabel", "Label", "EquipmentName", "MateriaNameLabel",
)


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _property_map(package) -> dict[str, Any]:
    return {prop.name: prop for prop in package.properties}


def _first_text_id(values: dict[str, Any]) -> str:
    for hint in NAME_PROPERTY_HINTS:
        value = values.get(hint)
        if isinstance(value, str) and value.startswith("$"):
            return value
    for value in values.values():
        if isinstance(value, str) and value.startswith("$Item_"):
            return value
    for value in values.values():
        if isinstance(value, str) and value.startswith("$"):
            return value
    return ""


def _text_lookup(game_root, data_root, project_root, index, language: str) -> dict[str, str]:
    try:
        return resident_text_map(
            game_root, data_root, project_root, index, language=language)
    except Exception:
        return {}


def _candidate_rows(index: dict, names: frozenset[str] | set[str]) -> list[dict]:
    return [row for row in index.get("assets", [])
            if _basename(str(row.get("asset", ""))) in names]


def _economy_tables(game_root, data_root, project_root, index: dict,
                    *, language: str, vanilla: bool) -> tuple[list[dict], dict[str, str], dict[str, str]]:
    text = _text_lookup(game_root, data_root, project_root, index, language)
    tables: list[dict] = []
    item_names: dict[str, str] = {}
    text_ids: dict[str, str] = {}
    for row in _candidate_rows(index, ECONOMY_TABLE_NAMES):
        asset = row["asset"]
        try:
            package, source_sha, using_project = load_package(
                game_root, data_root, project_root, index, asset, vanilla=vanilla)
        except Exception as error:
            tables.append({
                "asset": asset, "name": row.get("name", PurePosixPath(asset).name),
                "available": False, "error": str(error), "rows": [],
            })
            continue
        props = _property_map(package)
        present = [name for name in ECONOMY_FIELDS if name in props]
        if not present:
            continue
        api_rows = []
        for entry in package.entries:
            text_id = _first_text_id(entry.values)
            display = text.get(text_id, "") if text_id else ""
            if not display:
                display = entry.tag
            if entry.tag:
                item_names[entry.tag] = display
            if text_id:
                text_ids[entry.tag] = text_id
            fields = {}
            for name in present:
                prop = props[name]
                fields[name] = {
                    "value": entry.values[name],
                    "type": prop.api()["type"],
                    "editable": prop.editable,
                    "min": prop.api()["min"],
                    "max": prop.api()["max"],
                }
            api_rows.append({
                "entry": entry.index,
                "id": entry.tag,
                "name": display,
                "textId": text_id,
                "fields": fields,
            })
        tables.append({
            "asset": asset,
            "name": row.get("name", PurePosixPath(asset).name),
            "available": True,
            "sourceSha256": source_sha,
            "activeSha256": package.api_payload()["activeSha256"],
            "usingProject": using_project,
            "properties": present,
            "rows": api_rows,
        })
    return tables, item_names, text_ids


def economy_payload(game_root, data_root, project_root, index: dict,
                    *, language: str = "US", vanilla: bool = False) -> dict:
    tables, _item_names, _text_ids = _economy_tables(
        game_root, data_root, project_root, index,
        language=language, vanilla=vanilla)
    available = [table for table in tables if table.get("available")]
    return {
        "language": language.upper(),
        "available": bool(available),
        "tables": tables,
        "evidence": {
            "requiredAtRuntime": ["BuyValue"],
            "optionalAtRuntime": ["SaleValue", "CanSale"],
            "candidateTables": sorted(ECONOMY_TABLE_NAMES),
        },
    }


def _item_name_map(game_root, data_root, project_root, index: dict,
                   *, language: str, vanilla: bool) -> dict[str, str]:
    _tables, names, _text_ids = _economy_tables(
        game_root, data_root, project_root, index,
        language=language, vanilla=vanilla)
    return names


def _loot_asset(index: dict) -> dict | None:
    for row in index.get("assets", []):
        if _basename(str(row.get("asset", ""))) == LOOT_TABLE_NAME:
            return row
    return None


def _array(values: dict[str, Any], name: str | None) -> list[Any]:
    if not name:
        return []
    value = values.get(name, [])
    return list(value) if isinstance(value, list) else []


def loot_payload(game_root, data_root, project_root, index: dict,
                 *, language: str = "US", vanilla: bool = False) -> dict:
    row = _loot_asset(index)
    if row is None:
        return {
            "available": False,
            "reason": "BattleItemPossession DataObject was not found in the installed FF7R archives.",
            "rows": [],
        }
    asset = row["asset"]
    package, source_sha, using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=vanilla)
    props = _property_map(package)
    item_names = _item_name_map(
        game_root, data_root, project_root, index,
        language=language, vanilla=vanilla)

    discovered = []
    for kind, item_prop, percent_prop, quantity_prop in LOOT_FIELD_PAIRS:
        if item_prop in props:
            discovered.append({
                "kind": kind,
                "itemProperty": item_prop,
                "percentProperty": percent_prop if percent_prop in props else None,
                "quantityProperty": quantity_prop if quantity_prop in props else None,
            })
    if not discovered:
        return {
            "available": False,
            "asset": asset,
            "reason": "BattleItemPossession exists, but no known drop/steal item-array properties were present.",
            "rows": [],
            "properties": sorted(props),
        }

    # FName edits are same-size only, so only names already in this package can
    # be selected. Restricting to recognized item IDs gives a useful dropdown;
    # include currently referenced unknown IDs so no existing value disappears.
    referenced_names: set[str] = set()
    for entry in package.entries:
        for spec in discovered:
            referenced_names.update(str(value) for value in _array(entry.values, spec["itemProperty"]) if value)
    known_choices = [
        {"id": name, "name": item_names.get(name, name)}
        for name in package.uasset.names
        if name in item_names or name in referenced_names
    ]

    result_rows = []
    for entry in package.entries:
        groups = []
        for spec in discovered:
            items = _array(entry.values, spec["itemProperty"])
            percents = _array(entry.values, spec["percentProperty"])
            quantities = _array(entry.values, spec["quantityProperty"])
            slots = []
            for index_in_array, item in enumerate(items):
                chance = percents[index_in_array] if index_in_array < len(percents) else None
                quantity = quantities[index_in_array] if index_in_array < len(quantities) else None
                slots.append({
                    "index": index_in_array,
                    "item": item,
                    "itemName": item_names.get(str(item), str(item)),
                    "chance": chance,
                    "quantity": quantity,
                })
            groups.append({**spec, "slots": slots})
        result_rows.append({
            "entry": entry.index,
            "id": entry.tag,
            "name": entry.tag,
            "groups": groups,
        })

    return {
        "available": True,
        "asset": asset,
        "sourceSha256": source_sha,
        "activeSha256": package.api_payload()["activeSha256"],
        "usingProject": using_project,
        "groups": discovered,
        "itemChoices": known_choices,
        "rows": result_rows,
        "notes": [
            "Normal and rare drops are shown separately when the installed table provides both arrays.",
            "Steal data is exposed separately and is never labeled as an ordinary drop.",
            "Chance controls use the installed raw percent field; semantic UI constrains percent-like fields to 0..100.",
        ],
    }
