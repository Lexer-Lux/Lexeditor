"""Semantic FF7R views layered over the generic DataObject reader.

These adapters deliberately validate the installed game's property names before
exposing controls. Public Remake evidence identifies Item/Equipment BuyValue and
MaxCount plus BattleItemPossession as authoritative data surfaces; generated
schemas provide useful candidate names for closely related fields, but a
candidate is never treated as present until the installed FF7R DataObject
actually contains it.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from .storage import load_package, save_edits
from .text_storage import resident_text_map


ECONOMY_TABLE_NAMES = frozenset({"item", "equipment", "materia"})
ECONOMY_FIELDS = ("BuyValue", "SaleValue", "CanSale", "MaxCount")
ECONOMY_EDIT_FIELDS = {
    "buy": "BuyValue",
    "sell": "SaleValue",
    "canSell": "CanSale",
    "maxCount": "MaxCount",
}
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
            "optionalAtRuntime": ["SaleValue", "CanSale", "MaxCount"],
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


def _loot_specs(props: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    specs: dict[str, dict[str, str | None]] = {}
    for kind, item_prop, percent_prop, quantity_prop in LOOT_FIELD_PAIRS:
        if item_prop not in props:
            continue
        specs[kind] = {
            "item": item_prop,
            "chance": percent_prop if percent_prop in props else None,
            "quantity": quantity_prop if quantity_prop in props else None,
        }
    return specs


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
    for kind, fields in _loot_specs(props).items():
        discovered.append({
            "kind": kind,
            "itemProperty": fields["item"],
            "percentProperty": fields["chance"],
            "quantityProperty": fields["quantity"],
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


def save_economy_edits(game_root, data_root, project_root, index: dict, asset: str,
                       *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict:
    """Validate item-setting semantics, then delegate to the fixed-size DataObject writer."""
    if _basename(asset) not in ECONOMY_TABLE_NAMES:
        raise ValueError("Economy saves are limited to Item, Equipment, and Materia DataObjects")
    if not isinstance(edits, list):
        raise TypeError("Economy edits must be a list")

    package, _source_sha, _using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    props = _property_map(package)
    generic_edits: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("Each economy edit must be an object")
        field = str(edit.get("field", ""))
        prop_name = ECONOMY_EDIT_FIELDS.get(field)
        if prop_name is None:
            raise ValueError(f"Unknown economy field: {field}")
        if prop_name not in props:
            raise ValueError(f"{prop_name} is not present in this installed FF7R DataObject")
        if props[prop_name].is_array:
            raise ValueError(f"{prop_name} unexpectedly uses an array in this installed FF7R DataObject")
        if "index" in edit:
            raise ValueError("Economy fields are scalar and do not accept an array index")
        generic_edits.append({
            "entry": int(edit.get("entry", -1)),
            "property": prop_name,
            "value": edit.get("value"),
        })

    result = save_edits(
        game_root, data_root, project_root, index, asset,
        source_sha256=source_sha256,
        active_sha256=active_sha256,
        edits=generic_edits,
    )
    return {**result, "surface": "economy"}


def save_loot_edits(game_root, data_root, project_root, index: dict, asset: str,
                    *, source_sha256: str, active_sha256: str,
                    edits: list[dict[str, Any]]) -> dict:
    """Validate drop/steal semantics, then delegate to the fixed-size DataObject writer."""
    if _basename(asset) != LOOT_TABLE_NAME:
        raise ValueError("Enemy-loot saves are limited to the BattleItemPossession DataObject")
    if not isinstance(edits, list):
        raise TypeError("Enemy-loot edits must be a list")

    package, _source_sha, _using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    specs = _loot_specs(_property_map(package))
    if not specs:
        raise ValueError("This BattleItemPossession DataObject has no recognized drop/steal fields")

    generic_edits: list[dict[str, Any]] = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("Each enemy-loot edit must be an object")
        kind = str(edit.get("kind", ""))
        field = str(edit.get("field", ""))
        if kind not in specs:
            raise ValueError(f"Unknown or unavailable enemy-loot group: {kind}")
        if field not in {"item", "chance", "quantity"}:
            raise ValueError(f"Unknown enemy-loot field: {field}")
        prop_name = specs[kind].get(field)
        if prop_name is None:
            raise ValueError(f"{kind} loot does not expose a {field} field in this installed FF7R DataObject")
        slot = int(edit.get("index", -1))
        if slot < 0:
            raise ValueError("Enemy-loot slot index must be zero or greater")
        value = edit.get("value")
        if field == "chance":
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
                raise ValueError("Enemy-loot chance must be an integer from 0 to 100")
        generic_edits.append({
            "entry": int(edit.get("entry", -1)),
            "property": prop_name,
            "index": slot,
            "value": value,
        })

    result = save_edits(
        game_root, data_root, project_root, index, asset,
        source_sha256=source_sha256,
        active_sha256=active_sha256,
        edits=generic_edits,
    )
    return {**result, "surface": "enemy-loot"}
