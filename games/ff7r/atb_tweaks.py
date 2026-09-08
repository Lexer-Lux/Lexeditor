"""Reversible, installed-data-driven ATB tweaks for FF7R.

Vanilla ATB state coefficients, guard gains, and command costs live in cooked
DataObjects.  Lexeditor stores only semantic overrides plus one enable flag;
those overrides are materialized into a temporary build tree only when the tweak
is enabled.  This keeps "disabled" truly vanilla without deleting or rewriting
saved project DataObject edits.

The two requested new mechanics (movement multiplier and dodge/roll reduction)
are stored here too, but are not represented as DataObject edits.  They remain
runtime-hook settings until their native accumulator paths are validated.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Any

from .archive import extract_pair
from .dataobject import DataObjectPackage


ATB_SCHEMA_VERSION = 1
ATB_CONFIG_NAME = "LexeditorFF7RATBTweaks.json"
ATB_SETTINGS_ASSET = "Lexeditor/ATBTweaks"
ATB_RESIDENT_ASSET = "Lexeditor/ATBResidentParameters"
ATB_GUARD_ASSET = "Lexeditor/ATBGuardReactions"
ATB_ABILITY_ASSET = "Lexeditor/ATBAbilityCosts"
ATB_VIRTUAL_ASSETS = frozenset({
    ATB_SETTINGS_ASSET,
    ATB_RESIDENT_ASSET,
    ATB_GUARD_ASSET,
    ATB_ABILITY_ASSET,
})

RESIDENT_TABLE = "residentparameter"
GUARD_TABLE = "battleplayerparameter"
ABILITY_TABLE = "battleability"
RESIDENT_VALUE_PROPERTIES = ("ParamFloat", "ParamInt")
GUARD_PROPERTIES = (
    "GuardReactionNoneAddATB_Array",
    "GuardReactionMediumAddATB_Array",
    "GuardReactionLargeAddATB_Array",
)

DEFAULT_ATB_CONFIG = {
    "schemaVersion": ATB_SCHEMA_VERSION,
    "enabled": False,
    "movementMultiplier": 1.0,
    "rollReduction": 0.0,
    "residentOverrides": {},
    "guardOverrides": {},
    "abilityCostOverrides": {},
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / ATB_CONFIG_NAME


def _clone_default() -> dict:
    return json.loads(json.dumps(DEFAULT_ATB_CONFIG))


def _finite_number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return result


def _numeric_map(value: Any, label: str, *, integers: bool = False) -> dict[str, int | float]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    out: dict[str, int | float] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label} keys must be non-empty strings")
        number = _finite_number(raw, f"{label}.{key}")
        if integers:
            integer = int(number)
            if integer != number:
                raise ValueError(f"{label}.{key} must be an integer")
            if integer < -2147483648 or integer > 2147483647:
                raise ValueError(f"{label}.{key} is outside the FF7R INT32 range")
            out[key] = integer
        else:
            out[key] = number
    return out


def validate_atb_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("ATB tweak config must be an object")
    allowed = {
        "schemaVersion", "enabled", "movementMultiplier", "rollReduction",
        "residentOverrides", "guardOverrides", "abilityCostOverrides",
    }
    if set(value) - allowed:
        raise ValueError("ATB tweak config contains unsupported top-level fields")
    if value.get("schemaVersion", ATB_SCHEMA_VERSION) != ATB_SCHEMA_VERSION:
        raise ValueError(f"unsupported ATB tweak config schema: {value.get('schemaVersion')}")
    enabled = value.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("ATB tweak enabled must be boolean")
    movement = _finite_number(value.get("movementMultiplier", 1.0), "movementMultiplier", minimum=0.0)
    roll = _finite_number(value.get("rollReduction", 0.0), "rollReduction", minimum=0.0)
    return {
        "schemaVersion": ATB_SCHEMA_VERSION,
        "enabled": enabled,
        "movementMultiplier": movement,
        "rollReduction": roll,
        "residentOverrides": _numeric_map(value.get("residentOverrides", {}), "residentOverrides"),
        "guardOverrides": _numeric_map(value.get("guardOverrides", {}), "guardOverrides"),
        "abilityCostOverrides": _numeric_map(
            value.get("abilityCostOverrides", {}), "abilityCostOverrides", integers=True),
    }


def load_atb_config(project_root: Path) -> dict:
    target = config_path(project_root)
    if not target.is_file():
        return _clone_default()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R ATB tweak config: {error}") from error
    return validate_atb_config(value)


def save_atb_config(project_root: Path, value: dict) -> dict:
    validated = validate_atb_config(value)
    target = config_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    reread = load_atb_config(project_root)
    if reread != validated:
        raise RuntimeError("FF7R ATB tweak config failed atomic readback")
    return reread


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _find_asset(index: dict, basename: str) -> dict | None:
    for row in index.get("assets", []):
        if row.get("synthetic"):
            continue
        if _basename(str(row.get("asset", ""))) == basename:
            return row
    return None


def _load_source_package(game_root: Path, data_root: Path, index: dict, row: dict) -> DataObjectPackage:
    uasset, uexp = extract_pair(game_root, data_root, index, row["asset"])
    return DataObjectPackage(uasset, uexp, asset=row["asset"])


def discover_atb_sources(game_root: Path, data_root: Path, index: dict) -> dict:
    """Discover authoritative installed ATB DataObject rows without project overlays."""
    result = {
        "resident": [],
        "guard": [],
        "abilities": [],
        "sourceAssets": {},
        "errors": [],
    }

    resident_row = _find_asset(index, RESIDENT_TABLE)
    if resident_row:
        try:
            package = _load_source_package(game_root, data_root, index, resident_row)
            props = {prop.name: prop for prop in package.properties}
            result["sourceAssets"]["resident"] = resident_row["asset"]
            for entry in package.entries:
                if "atb" not in entry.tag.casefold():
                    continue
                for prop_name in RESIDENT_VALUE_PROPERTIES:
                    prop = props.get(prop_name)
                    if not prop or prop.is_array or not prop.editable:
                        continue
                    key = f"{entry.tag}|{prop_name}"
                    result["resident"].append({
                        "key": key,
                        "asset": resident_row["asset"],
                        "entry": entry.index,
                        "tag": entry.tag,
                        "property": prop_name,
                        "type": prop.api()["type"],
                        "vanilla": entry.values[prop_name],
                    })
        except Exception as error:
            result["errors"].append(f"ResidentParameter: {error}")

    guard_row = _find_asset(index, GUARD_TABLE)
    if guard_row:
        try:
            package = _load_source_package(game_root, data_root, index, guard_row)
            props = {prop.name: prop for prop in package.properties}
            result["sourceAssets"]["guard"] = guard_row["asset"]
            for entry in package.entries:
                for prop_name in GUARD_PROPERTIES:
                    prop = props.get(prop_name)
                    values = entry.values.get(prop_name)
                    if not prop or not prop.is_array or not prop.editable or not isinstance(values, list):
                        continue
                    for array_index, vanilla in enumerate(values):
                        key = f"{entry.tag}|{prop_name}|{array_index}"
                        result["guard"].append({
                            "key": key,
                            "asset": guard_row["asset"],
                            "entry": entry.index,
                            "tag": entry.tag,
                            "property": prop_name,
                            "index": array_index,
                            "type": prop.api()["type"],
                            "vanilla": vanilla,
                        })
        except Exception as error:
            result["errors"].append(f"BattlePlayerParameter: {error}")

    ability_row = _find_asset(index, ABILITY_TABLE)
    if ability_row:
        try:
            package = _load_source_package(game_root, data_root, index, ability_row)
            props = {prop.name: prop for prop in package.properties}
            atb_prop = props.get("ATB")
            result["sourceAssets"]["abilities"] = ability_row["asset"]
            if atb_prop and not atb_prop.is_array and atb_prop.editable:
                for entry in package.entries:
                    result["abilities"].append({
                        "key": entry.tag,
                        "asset": ability_row["asset"],
                        "entry": entry.index,
                        "tag": entry.tag,
                        "property": "ATB",
                        "type": atb_prop.api()["type"],
                        "vanilla": entry.values["ATB"],
                    })
        except Exception as error:
            result["errors"].append(f"BattleAbility: {error}")

    return result


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def resource_spec(asset: str, game_root: Path, data_root: Path, project_root: Path, index: dict) -> dict:
    """Return a virtual-DataObject description for one ATB semantic resource."""
    if asset not in ATB_VIRTUAL_ASSETS:
        raise KeyError(f"Unknown FF7R ATB virtual asset: {asset}")
    discovery = discover_atb_sources(game_root, data_root, index)
    config = load_atb_config(project_root)
    source_fingerprint = _canonical_hash({
        "schema": ATB_SCHEMA_VERSION,
        "asset": asset,
        "sources": discovery,
    })
    active_fingerprint = _canonical_hash({"source": source_fingerprint, "config": config})

    if asset == ATB_SETTINGS_ASSET:
        return {
            "sourceSha256": source_fingerprint,
            "activeSha256": active_fingerprint,
            "properties": [
                {"name": "Enabled", "label": "ATB Tweaks Enabled", "type": "BOOL", "editable": True, "min": 0, "max": 1},
                {"name": "MovementMultiplier", "label": "Movement ATB Multiplier", "type": "FLOAT", "editable": True, "min": 0.0, "max": None},
                {"name": "RollReduction", "label": "Roll / Dodge ATB Reduction", "type": "FLOAT", "editable": True, "min": 0.0, "max": None},
                {"name": "ResidentRows", "label": "Installed ATB Resident Rows", "type": "INT32", "editable": False, "min": None, "max": None},
                {"name": "GuardRows", "label": "Installed Guard ATB Slots", "type": "INT32", "editable": False, "min": None, "max": None},
                {"name": "AbilityRows", "label": "Installed Ability ATB Costs", "type": "INT32", "editable": False, "min": None, "max": None},
                {"name": "ResearchNotes", "label": "Runtime Research Notes", "type": "STRING", "editable": False, "min": None, "max": None},
            ],
            "entries": [{
                "tag": "ATB Tweaks",
                "values": {
                    "Enabled": config["enabled"],
                    "MovementMultiplier": config["movementMultiplier"],
                    "RollReduction": config["rollReduction"],
                    "ResidentRows": len(discovery["resident"]),
                    "GuardRows": len(discovery["guard"]),
                    "AbilityRows": len(discovery["abilities"]),
                    "ResearchNotes": (
                        "Resident/guard/ability overrides are materialized only when Enabled is true. "
                        "MovementMultiplier and RollReduction require a validated native ATB hook before they can affect gameplay."
                    ),
                },
            }],
        }

    if asset == ATB_RESIDENT_ASSET:
        rows = discovery["resident"]
        overrides = config["residentOverrides"]
        return {
            "sourceSha256": source_fingerprint,
            "activeSha256": active_fingerprint,
            "properties": [
                {"name": "SourceTag", "label": "ResidentParameter ID", "type": "STRING", "editable": False, "min": None, "max": None},
                {"name": "SourceProperty", "label": "Source Property", "type": "STRING", "editable": False, "min": None, "max": None},
                {"name": "VanillaValue", "label": "Vanilla Value", "type": "FLOAT", "editable": False, "min": None, "max": None},
                {"name": "OverrideValue", "label": "ATB Override", "type": "FLOAT", "editable": True, "min": None, "max": None},
            ],
            "entries": [{
                "tag": row["key"],
                "values": {
                    "SourceTag": row["tag"],
                    "SourceProperty": row["property"],
                    "VanillaValue": float(row["vanilla"]),
                    "OverrideValue": float(overrides.get(row["key"], row["vanilla"])),
                },
            } for row in rows],
        }

    if asset == ATB_GUARD_ASSET:
        rows = discovery["guard"]
        overrides = config["guardOverrides"]
        return {
            "sourceSha256": source_fingerprint,
            "activeSha256": active_fingerprint,
            "properties": [
                {"name": "CharacterRow", "label": "Battle Player Row", "type": "STRING", "editable": False, "min": None, "max": None},
                {"name": "Reaction", "label": "Guard Reaction", "type": "STRING", "editable": False, "min": None, "max": None},
                {"name": "Slot", "label": "Array Slot", "type": "INT32", "editable": False, "min": None, "max": None},
                {"name": "VanillaValue", "label": "Vanilla ATB Gain", "type": "FLOAT", "editable": False, "min": None, "max": None},
                {"name": "OverrideValue", "label": "Guard ATB Gain", "type": "FLOAT", "editable": True, "min": None, "max": None},
            ],
            "entries": [{
                "tag": row["key"],
                "values": {
                    "CharacterRow": row["tag"],
                    "Reaction": row["property"],
                    "Slot": row["index"],
                    "VanillaValue": float(row["vanilla"]),
                    "OverrideValue": float(overrides.get(row["key"], row["vanilla"])),
                },
            } for row in rows],
        }

    rows = discovery["abilities"]
    overrides = config["abilityCostOverrides"]
    return {
        "sourceSha256": source_fingerprint,
        "activeSha256": active_fingerprint,
        "properties": [
            {"name": "AbilityID", "label": "Battle Ability ID", "type": "STRING", "editable": False, "min": None, "max": None},
            {"name": "VanillaATB", "label": "Vanilla ATB Cost", "type": "INT32", "editable": False, "min": None, "max": None},
            {"name": "OverrideATB", "label": "ATB Cost", "type": "INT32", "editable": True, "min": -2147483648, "max": 2147483647},
        ],
        "entries": [{
            "tag": row["tag"],
            "values": {
                "AbilityID": row["tag"],
                "VanillaATB": int(row["vanilla"]),
                "OverrideATB": int(overrides.get(row["key"], row["vanilla"])),
            },
        } for row in rows],
    }


def save_virtual_edits(game_root: Path, data_root: Path, project_root: Path, index: dict,
                       asset: str, *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict:
    spec = resource_spec(asset, game_root, data_root, project_root, index)
    if spec["sourceSha256"] != source_sha256:
        raise RuntimeError("Installed FF7R ATB source data changed; reload before saving")
    if spec["activeSha256"] != active_sha256:
        raise RuntimeError("FF7R ATB tweak config changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("ATB edits must be a list")

    config = load_atb_config(project_root)
    entries = spec["entries"]
    seen: set[tuple[int, str]] = set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("Each ATB edit must be an object")
        entry_index = int(edit.get("entry", -1))
        if entry_index < 0 or entry_index >= len(entries) or "index" in edit:
            raise ValueError("ATB virtual resources accept scalar edits on existing records only")
        prop = str(edit.get("property", ""))
        marker = (entry_index, prop)
        if marker in seen:
            raise ValueError("Duplicate ATB virtual property edit")
        seen.add(marker)
        value = edit.get("value")
        row_tag = entries[entry_index]["tag"]

        if asset == ATB_SETTINGS_ASSET:
            if entry_index != 0:
                raise ValueError("ATB settings have exactly one record")
            if prop == "Enabled":
                if not isinstance(value, bool):
                    raise ValueError("ATB Tweaks Enabled must be boolean")
                config["enabled"] = value
            elif prop == "MovementMultiplier":
                config["movementMultiplier"] = _finite_number(value, prop, minimum=0.0)
            elif prop == "RollReduction":
                config["rollReduction"] = _finite_number(value, prop, minimum=0.0)
            else:
                raise ValueError(f"ATB settings property is read-only or unknown: {prop}")
        elif asset == ATB_RESIDENT_ASSET:
            if prop != "OverrideValue":
                raise ValueError(f"ATB Resident property is read-only or unknown: {prop}")
            numeric = _finite_number(value, f"resident override {row_tag}")
            source = next(row for row in discover_atb_sources(game_root, data_root, index)["resident"] if row["key"] == row_tag)
            if source["type"] == "INT32" and int(numeric) != numeric:
                raise ValueError(f"{row_tag} is an integer ResidentParameter")
            if numeric == float(source["vanilla"]):
                config["residentOverrides"].pop(row_tag, None)
            else:
                config["residentOverrides"][row_tag] = int(numeric) if source["type"] == "INT32" else numeric
        elif asset == ATB_GUARD_ASSET:
            if prop != "OverrideValue":
                raise ValueError(f"ATB Guard property is read-only or unknown: {prop}")
            numeric = _finite_number(value, f"guard override {row_tag}")
            source = next(row for row in discover_atb_sources(game_root, data_root, index)["guard"] if row["key"] == row_tag)
            if numeric == float(source["vanilla"]):
                config["guardOverrides"].pop(row_tag, None)
            else:
                config["guardOverrides"][row_tag] = numeric
        else:
            if prop != "OverrideATB":
                raise ValueError(f"ATB Ability property is read-only or unknown: {prop}")
            numeric = _finite_number(value, f"ability ATB cost {row_tag}")
            integer = int(numeric)
            if integer != numeric or integer < -2147483648 or integer > 2147483647:
                raise ValueError("BattleAbility ATB cost must be an INT32")
            source = next(row for row in discover_atb_sources(game_root, data_root, index)["abilities"] if row["key"] == row_tag)
            if integer == int(source["vanilla"]):
                config["abilityCostOverrides"].pop(row_tag, None)
            else:
                config["abilityCostOverrides"][row_tag] = integer

    saved = save_atb_config(project_root, config)
    refreshed = resource_spec(asset, game_root, data_root, project_root, index)
    return {
        "asset": asset,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "activeSha256": refreshed["activeSha256"],
        "usingProject": True,
        "enabled": saved["enabled"],
    }


def _staging_pair(staging_root: Path, source_uasset: Path, source_uexp: Path,
                  asset: str) -> tuple[Path, Path]:
    root = Path(staging_root).resolve()
    uasset = (root / f"{asset}.uasset").resolve()
    uexp = (root / f"{asset}.uexp").resolve()
    if root not in uasset.parents or root not in uexp.parents:
        raise ValueError(f"Unsafe FF7R ATB staging path: {asset}")
    if uasset.is_file() != uexp.is_file():
        raise RuntimeError(f"ATB staging has an incomplete package pair for {asset}")
    if not uasset.is_file():
        uasset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_uasset, uasset)
        shutil.copy2(source_uexp, uexp)
    return uasset, uexp


def materialize_atb_overrides(game_root: Path, data_root: Path, project_root: Path,
                              index: dict, staging_root: Path) -> list[str]:
    """Apply enabled semantic ATB overrides into a temporary PAK staging tree."""
    config = load_atb_config(project_root)
    if not config["enabled"]:
        return []
    discovery = discover_atb_sources(game_root, data_root, index)
    by_key = {
        "resident": {row["key"]: row for row in discovery["resident"]},
        "guard": {row["key"]: row for row in discovery["guard"]},
        "abilities": {row["key"]: row for row in discovery["abilities"]},
    }
    edits_by_asset: dict[str, list[dict[str, Any]]] = {}

    def add(source: dict, value: Any) -> None:
        edit = {"entry": source["entry"], "property": source["property"], "value": value}
        if "index" in source:
            edit["index"] = source["index"]
        edits_by_asset.setdefault(source["asset"], []).append(edit)

    for key, value in config["residentOverrides"].items():
        if key not in by_key["resident"]:
            raise RuntimeError(f"Installed FF7R no longer contains ATB ResidentParameter row {key!r}")
        add(by_key["resident"][key], value)
    for key, value in config["guardOverrides"].items():
        if key not in by_key["guard"]:
            raise RuntimeError(f"Installed FF7R no longer contains guard ATB slot {key!r}")
        add(by_key["guard"][key], value)
    for key, value in config["abilityCostOverrides"].items():
        if key not in by_key["abilities"]:
            raise RuntimeError(f"Installed FF7R no longer contains BattleAbility {key!r}")
        add(by_key["abilities"][key], value)

    materialized: list[str] = []
    for asset, edits in edits_by_asset.items():
        source_uasset, source_uexp = extract_pair(game_root, data_root, index, asset)
        target_uasset, target_uexp = _staging_pair(
            staging_root, source_uasset, source_uexp, asset)
        package = DataObjectPackage(target_uasset, target_uexp, asset=asset)
        package.apply_edits(edits)
        original_size = target_uexp.stat().st_size
        package.write_uexp(target_uexp)
        if target_uexp.stat().st_size != original_size:
            raise RuntimeError(f"ATB materialization changed fixed-size payload length for {asset}")
        # Binary reread verifies the staged result remains parseable.
        DataObjectPackage(target_uasset, target_uexp, asset=asset)
        materialized.append(asset)
    return sorted(materialized)


def has_enabled_data_overrides(project_root: Path) -> bool:
    config = load_atb_config(project_root)
    return bool(config["enabled"] and (
        config["residentOverrides"]
        or config["guardOverrides"]
        or config["abilityCostOverrides"]
    ))
