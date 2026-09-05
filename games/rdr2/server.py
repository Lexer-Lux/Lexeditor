"""Lexeditor RDR2 plugin service.

Parses the mod's XML data files (catalog_sp.ymt, loot tables, loot matrix),
serves them as JSON to editor.html, and writes edits back to disk.

Datasets:
  mine       -> ..\MyOverhaul       (editable)
  prices1899 -> ..\datasets\1899   (read-only price/reward reference)
  kiddos     -> ..\datasets\kiddos (read-only economy/loot reference)
  vanilla    -> ..\datasets\vanilla (read-only reference)

Lexeditor starts and supervises this service through its RDR2 plugin. Direct
execution remains available for development checks.
"""
import copy
import csv
import gzip
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# keep the game's xi: prefix on XInclude tags (ET would rename to ns0:)
ET.register_namespace("xi", "http://www.w3.org/2001/XInclude")
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    from .paths import EDITABLE_MOD_ROOT, EXTRACT_ROOT, GAME_ROOT, LEXEDITOR_ROOT, PLUGIN_ROOT, PROJECT_ROOT
except ImportError:
    from paths import EDITABLE_MOD_ROOT, EXTRACT_ROOT, GAME_ROOT, LEXEDITOR_ROOT, PLUGIN_ROOT, PROJECT_ROOT

try:
    from .alcohol_strengths import (
        get_alcohol_strengths as _get_alcohol_strengths,
        save_alcohol_strengths as _save_alcohol_strengths,
    )
except ImportError:
    from alcohol_strengths import (
        get_alcohol_strengths as _get_alcohol_strengths,
        save_alcohol_strengths as _save_alcohol_strengths,
    )

try:
    from .custom_crafting import (
        Ingredient as _CraftIngredient,
        Recipe as _CraftRecipe,
        catalog_item_keys as _craft_catalog_item_keys,
        load_recipes as _load_craft_recipes,
        save_recipes as _save_craft_recipes,
        validate_recipes as _validate_craft_recipes,
    )
except ImportError:
    from custom_crafting import (
        Ingredient as _CraftIngredient,
        Recipe as _CraftRecipe,
        catalog_item_keys as _craft_catalog_item_keys,
        load_recipes as _load_craft_recipes,
        save_recipes as _save_craft_recipes,
        validate_recipes as _validate_craft_recipes,
    )

try:
    from .bounty_hunters import (read_bounty_hunters as _read_bounty_hunters,
                                 apply_bounty_hunter_edits as _apply_bounty_hunter_edits,
                                 ensure_bounty_hunter_metadata as _ensure_bounty_hunter_metadata)
except ImportError:
    from bounty_hunters import (read_bounty_hunters as _read_bounty_hunters,
                                apply_bounty_hunter_edits as _apply_bounty_hunter_edits,
                                ensure_bounty_hunter_metadata as _ensure_bounty_hunter_metadata)

try:
    from .projectile_speed import cartridge_mapping as _cartridge_mapping, load_multipliers as _load_speed_multipliers, serialize_multipliers as _serialize_speed_multipliers
except ImportError:
    from projectile_speed import cartridge_mapping as _cartridge_mapping, load_multipliers as _load_speed_multipliers, serialize_multipliers as _serialize_speed_multipliers

try:
    from .honor_actions import read_honor_actions as _read_honor_actions, save_honor_actions as _save_honor_actions
except ImportError:
    from honor_actions import read_honor_actions as _read_honor_actions, save_honor_actions as _save_honor_actions

try:
    from .data_map import build_data_map as _build_data_map
except ImportError:
    from data_map import build_data_map as _build_data_map

try:
    from .model_preview import (
        PreviewUnavailable as _PreviewUnavailable,
        cached_geometry_path as _cached_preview_geometry,
        cached_texture_path as _cached_preview_texture,
        clear_preview_cache as _clear_preview_cache,
        get_preview_settings as _get_preview_settings,
        model_preview_availability as _model_preview_availability,
        prepare_model_preview as _prepare_model_preview,
        save_preview_settings as _save_preview_settings,
    )
except ImportError:
    from model_preview import (
        PreviewUnavailable as _PreviewUnavailable,
        cached_geometry_path as _cached_preview_geometry,
        cached_texture_path as _cached_preview_texture,
        clear_preview_cache as _clear_preview_cache,
        get_preview_settings as _get_preview_settings,
        model_preview_availability as _model_preview_availability,
        prepare_model_preview as _prepare_model_preview,
        save_preview_settings as _save_preview_settings,
    )

ROOT = PLUGIN_ROOT
PLUGIN_ID = "rdr2"
PLUGIN_API_VERSION = 1
PLUGIN_HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED", "0") == "1"
DATASETS = {
    "mine": {"dir": EDITABLE_MOD_ROOT,
             "label": os.environ.get("LEXEDITOR_MOD_NAME", EDITABLE_MOD_ROOT.name or "My Mod"), "readonly": False,
             "scopes": ["all"]},
    "prices1899": {"dir": PROJECT_ROOT / "datasets" / "1899", "label": "1899 Prices (reference)", "readonly": True,
                   "scopes": ["prices", "loot_table_reward.meta"]},
    "kiddos": {"dir": PROJECT_ROOT / "datasets" / "kiddos", "label": "Kiddo's Hardcore 2.6 (reference)", "readonly": True,
               "scopes": ["prices", "carry", "craft", "effects", "loot", "matrix", "lootconfig", "cleanliness"]},
    "vanilla": {"dir": EXTRACT_ROOT, "label": "Vanilla (reference)", "readonly": True,
                "scopes": ["all"]},
    "crimeTweaks": {"dir": PROJECT_ROOT / "datasets" / "crimeTweaks", "label": "Crime Tweaks 4.0 (reference)", "readonly": True,
                     "scopes": ["crime"]},
}
PORT = int(os.environ.get("LEXEDITOR_PORT", "8765"))

CATALOG_FILE = "catalog_sp.ymt"
CATALOG_GAME_PATH = "platform:/data/itemdatabase/catalog_sp.ymt"
QUICK_SELECT_FILE = "quickselectitems.ymt"
QUICK_SELECT_GAME_PATH = "update:/x64/packs/base/data/ai/quickselectitems.ymt"
QUICK_SELECT_WEAPON_GROUP = "QUICK_SELECT_ITEM_TYPE_WEAPON"
QUICK_SELECT_SATCHEL_GROUP = "QUICK_SELECT_ITEM_TYPE_SATCHEL_ITEM"
QUICK_SELECT_EDITABLE_GROUPS = {
    QUICK_SELECT_WEAPON_GROUP,
    QUICK_SELECT_SATCHEL_GROUP,
}
ORIGIN_PROVENANCE_FILE = EDITABLE_MOD_ROOT / "online_content" / "lexeditor_provenance.json"
LOOT_FILES = [
    "loot_table_ped.meta",
    "loot_table_itemgroups.meta",
    "loot_table_reward.meta",
    "loot_table_container.meta",
    "loot_table_herb.meta",
]
MATRIX_FILE = "loot_items_matrix.meta"
CRIME_FILE = "crimeinformation.meta"
DISPATCH_FILE = "dispatch.meta"
BOUNTY_HUNTERS_FILE = "dispatchresponses/wilderness/bountyhunters.meta"
INCIDENTS_FILE = "tune/incidentstuning.meta"
GOALS_FILE = "goals_sp.meta"
CHALLENGES_FILE = "challenges_sp.meta"
SCRIPT_REFERENCE_DIRS = [
    PROJECT_ROOT / "_downloads" / "rdr3-decompiled-scripts" / "script_rel",
    PROJECT_ROOT / "_downloads" / "decompiled_collectibles",
]
SCRIPT_PROVENANCE_FILE = ROOT / "item_script_provenance.json.gz"
LOOT_USAGE_FILE = ROOT / "loot_usage.json"
COLLECTIBLE_LOCATIONS_FILE = PROJECT_ROOT / "GameplayTweaks" / "collectibles.csv"
KNOWN_CHALLENGE_SOURCE_PAIRS = [
    {"base": "KILLS", "permutation": "STEALTH", "label": "Stealth kills"},
    {"base": "KNOCKOUTS", "permutation": "STEALTH", "label": "Stealth knockouts"},
    {"base": "KILLS", "permutation": "UNAWARE", "label": "Kills on unaware enemies"},
    {"base": "KILLED", "permutation": "AT_BAT", "label": "Bats killed"},
]
DATA_MAP_FILE = PROJECT_ROOT / "DATA_MAP.md"
LABELS_FILE = ROOT / "labels.json"
SETTINGS_SCHEMA_FILE = ROOT / "settings_schema.json"
VANILLA_LOCALIZATION_FILE = ROOT / "vanilla_localization.json"
ONLINE_LOCALIZATION_FILE = EXTRACT_ROOT / "localization" / "american_global.json"
LOCALIZATION_FILE = "strings.gxt2"
GAMEPLAY_INI_FILE = Path(os.environ.get(
    "LEXEDITOR_GAMEPLAY_INI", PROJECT_ROOT / "GameplayTweaks" / "GameplayTweaks.ini"
)).resolve()
ALCOHOL_FILE = (PROJECT_ROOT / "GameplayTweaks" / "alcohol_strengths.csv").resolve()
CUSTOM_CRAFTING_FILE = Path(os.environ.get(
    "LEXEDITOR_CUSTOM_CRAFTING_FILE", GAMEPLAY_INI_FILE.parent / "custom_crafting_recipes.tsv"
)).resolve()
VANILLA_CRAFTING_FILE = Path(os.environ.get(
    "LEXEDITOR_VANILLA_CRAFTING_FILE", GAMEPLAY_INI_FILE.parent / "vanilla_crafting_recipes.tsv"
)).resolve()
BUYER_STATE_FILE = EDITABLE_MOD_ROOT / "merchant_buyers.json"
BUYER_DATA_FILE = EDITABLE_MOD_ROOT / "parseddata" / "0x0BA63B3D.ymt"
BUYER_DUMP_FILE = GAME_ROOT / "vanilla_shop_buyers.csv"
BUYER_OVERRIDE_FILE = Path(os.environ.get(
    "LEXEDITOR_BUYER_OVERRIDE_FILE", PROJECT_ROOT / "GameplayTweaks" / "merchant_buy_overrides.csv"
)).resolve()
BUYER_SHOPS = [
    "ST_BAIT", "ST_BARBER", "ST_BUTCHER", "ST_CLOTHING", "ST_DOCTOR",
    "ST_EXOTIC", "ST_FENCE", "ST_FRENCH_MARKET", "ST_GENERAL", "ST_GUNSMITH",
    "ST_HAIR", "ST_HORSE_SHOP", "ST_HORSE_TRAINER", "ST_MARKET",
    "ST_NEWSPAPER_BOY", "ST_PEARSON", "ST_QUARTERMASTER", "ST_TAILOR",
    "ST_TRAIN_STATION", "ST_TRAPPER",
]
WEAPON_REF_DIR = PROJECT_ROOT / "datasets" / "weaponRebalance"
WEAPONS_FILE = "weapons.ymt"
WEAPONS_GAME_PATH = "update:/x64/packs/base/data/ai/weapons.ymt"
PROJECTILE_SPEED_FILE = Path(os.environ.get(
    "LEXEDITOR_PROJECTILE_SPEED_FILE", PROJECT_ROOT / "GameplayTweaks" / "projectile_speed_multipliers.csv"
)).resolve()
HONOR_ACTIONS_FILE = Path(os.environ.get(
    "LEXEDITOR_HONOR_ACTIONS_FILE", PROJECT_ROOT / "GameplayTweaks" / "honor_actions.csv"
)).resolve()


def get_honor_actions():
    return _read_honor_actions(HONOR_ACTIONS_FILE)


def save_honor_actions(edits):
    if not isinstance(edits, list):
        raise ValueError("edits must be a list")
    return _save_honor_actions(HONOR_ACTIONS_FILE, edits)
# The game LAYERS weapon data: the base weapons.ymt plus per-weapon override
# files in pack_patch/ plus weaponcomponents.meta layers. Replacing only the
# base file reverts Rockstar's own weapon patches (repeater double-fire,
# lantern pose, off-hand holster regressions - discovered 2026-07-20). Any
# weapons edit therefore ships the COMPLETE stack; every file below must
# exist in the mod before any weapons replacement is activated.
WEAPON_STACK = [
    ("update:/x64/packs/base/data/ai/weapons.ymt", "weapons.ymt"),
    ("update:/x64/pack_patch/dlc_content_extra/data/ai/weapon_pistol_m1899.ymt", "weapon_pistol_m1899.ymt"),
    ("update:/x64/pack_patch/dlc_content_extra/data/ai/weapon_repeater_evans.ymt", "weapon_repeater_evans.ymt"),
    ("update:/x64/pack_patch/dlc_content_extra/data/ai/weapon_revolver_lemat.ymt", "weapon_revolver_lemat.ymt"),
    ("update:/x64/pack_patch/dlc_content_extra/data/ai/weapon_revolver_doubleaction_gambler.ymt", "weapon_revolver_doubleaction_gambler.ymt"),
    ("update:/x64/pack_patch/mp006/data/ai/weapon_revolver_navy.ymt", "weapon_revolver_navy.ymt"),
    ("update:/x64/pack_patch/mp007/data/ai/weapon_rifle_elephant.ymt", "weapon_rifle_elephant.ymt"),
    ("update:/common/packs/base/data/ai/weaponcomponents.meta", "weaponcomponents.meta"),
    ("update:/pack_patch/dlc_content_extra/common/data/ai/weaponcomponents.meta", "patch_weaponcomponents.meta"),
    ("update:/pack_patch/dlc_content_extra/common/data/ai/003_weaponcomponents.meta", "003_weaponcomponents.meta"),
    ("dlcpacks/dlc_content_extra/common/data/ai/004_weaponcomponents.meta", "004_weaponcomponents.meta"),
]


def missing_weapon_stack_files():
    """Stack files not yet present in the editable mod folder."""
    return [local for _, local in WEAPON_STACK
            if not (EDITABLE_MOD_ROOT / local).exists()]
WEAPON_SCHEMA_TYPES = {
    "0x072C658E": "CRumbleInfo",
    "0x867DEDAF": "CWeaponDegradationInfo",
    "0xB0FF7A4C": "CWeaponDamageFallOffInfo",
    "0xCFEE9058": "CVehicleWeaponInfo",
}

_PROVENANCE_CACHE = {}
_SCRIPT_INDEX_CACHE = None
_ORIGIN_MARKER_CACHE = {}
WEAPON_SCHEMA_FIELDS = {
    "UNK_MEMBER_0x1A782082": "Distances",
    "UNK_MEMBER_0x8E00F0C6": "DegradeOnTotalShots",
    "UNK_MEMBER_0x33E1EA1F": "DegradeOnDurationWet",
    "UNK_MEMBER_0x0F9140CA": "DegradeOnDurationDirty",
    "UNK_MEMBER_0xDB3F8A6B": "TotalShotsForSootAndRustBuildup",
    "UNK_MEMBER_0x19FCD8C4": "DurationWetForRustBuildup",
    "UNK_MEMBER_0xF18EFF07": "DurationDirtyForDirtBuildup",
    "UNK_MEMBER_0x6AA1A875": "PermanentDegradationThreshold",
    "UNK_MEMBER_0xB3A203D7": "FireInitial",
    "UNK_MEMBER_0x3B6428DD": "Fire",
    "UNK_MEMBER_0xF80E9B63": "Cock",
    "UNK_MEMBER_0xC2806E8C": "Reload",
    "UNK_MEMBER_0xA9F22EF9": "IntensityTrigger",
    "UNK_MEMBER_0x58867B20": "DurationFPS",
    "UNK_MEMBER_0x5E84BCBD": "IntensityFPS",
    "UNK_MEMBER_0x0530C364": "KickbackAmplitude",
    "UNK_MEMBER_0x9FB116C7": "KickbackImpulse",
    "UNK_MEMBER_0xA9D7C30B": "KickbackOverrideTiming",
}
UCO_REF_DIR = PROJECT_ROOT / "datasets" / "uco"
AI_FILES = {
    "profiles": ["ai/combatbehaviour.meta", "ai/pedperception.meta"],
    "global": ["ai/pedaccuracy.meta", "ai/peddistraction.meta", "ai/peddamage.meta", "ai/noisetuning.meta"],
}
PED_PERCEPTION_FILE = "ai/pedperception.meta"
PED_PERCEPTION_GAME_PATH = "common:/data/pedperception.meta"
VANILLA_PED_PERCEPTION_FILE = (
    EXTRACT_ROOT / "common_0_data" / "pedperception.meta"
)

# ---- Mobs tab (#190) ----
# Enemy "stats" are two unrelated files and the editor must not pretend they are
# one. combatbehaviour.meta holds per-faction CCombatInfo profiles (this is where
# WeaponAccuracy lives - GANG_ODRISCOLLS is 0.6, PLAYER is 0.1). pedhealth.meta
# holds per-archetype health/armour/thresholds. Nothing in either file joins them:
# the ped model -> profile/archetype binding happens in dispatch specs, scenario
# data and script, so no join is invented here.
COMBAT_FILE = "ai/combatbehaviour.meta"
COMBAT_GAME_PATH = "update:/common/data/ai/combatbehaviour.meta"
VANILLA_COMBAT_FILE = (
    EXTRACT_ROOT / "update_1_common" / "common" / "data" / "ai" / "combatbehaviour.meta"
)
PEDHEALTH_FILE = "pedhealth.meta"
PEDHEALTH_GAME_PATH = "update:/common/data/pedhealth.meta"
VANILLA_PEDHEALTH_FILE = (
    EXTRACT_ROOT / "update_1_common" / "common" / "data" / "pedhealth.meta"
)
PEDHEALTH_SECTIONS = ["HealthConfig", "StaminaConfig", "SpecialAbilityConfig",
                      "HealthRechargeConfig", "EnergyConfig"]
# Classification is derived from the actual record names in the shipped files,
# not from a guess: combatbehaviour.meta has exactly two non-human profiles
# (COMBAT_ANIMAL, COMBAT_ALLIGATOR) out of 40. Unmatched names are reported as
# "other" rather than forced into a group.
MOB_ANIMAL_HINTS = ("ANIMAL", "ALLIGATOR", "GATOR", "BIRD", "SNAKE", "HORSE",
                    "DONKEY", "BEAR", "COUGAR", "DEER", "WOLF", "LEGENDARY")
MOB_HUMAN_HINTS = ("PLAYER", "GANG", "LAW", "COMPANION", "BOUNTY", "GUARD",
                   "TOWNSFOLK", "TRAVELER", "DUELIST", "ENEMY", "PED", "JOHN",
                   "DEFAULT", "MARSHAL", "DEPUTY", "SHERIFF")

# (ds, name) -> {"root": Element, "bom": bool, "decl": str}
_files = {}
_lock = threading.Lock()


def ds_dir(ds):
    if ds not in DATASETS:
        raise ValueError(f"unknown dataset: {ds}")
    return DATASETS[ds]["dir"]


def install_replacements():
    """Return the active LML replacement map for the editable mod."""
    path = ds_dir("mine") / "install.xml"
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    return {
        (node.findtext("GamePath") or "").strip().casefold():
        (node.findtext("FilePath") or "").strip().replace("\\", "/")
        for node in root.findall(".//FileReplacement")
        if (node.findtext("GamePath") or "").strip()
        and (node.findtext("FilePath") or "").strip()
    }


def _safe_mod_path(relative):
    root = ds_dir("mine").resolve()
    path = (root / relative).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"install.xml replacement escapes the mod folder: {relative}")
    return path


def data_file_path(name, ds="mine"):
    """Resolve files that LML replaces through install.xml.

    The root catalog is authoritative. Resolving the install map keeps the
    editor and Story on the same file and fails safely if that rule changes.
    """
    replacement_paths = {
        CATALOG_FILE: CATALOG_GAME_PATH,
        QUICK_SELECT_FILE: QUICK_SELECT_GAME_PATH,
    }
    if ds == "mine" and name in replacement_paths:
        relative = install_replacements().get(replacement_paths[name].casefold())
        if relative:
            path = _safe_mod_path(relative)
            if path.exists():
                return path
    return ds_dir(ds) / name


def _parse_gameplay_settings(text):
    sections, sections_by_name, setting_indexes = [], {}, {}
    current, comments = None, []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(";"):
            comments.append(line.lstrip("; "))
        elif line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            identity = name.casefold()
            current = sections_by_name.get(identity)
            if current is None:
                current = {"name": name, "help": " ".join(comments), "settings": []}
                sections.append(current)
                sections_by_name[identity] = current
                setting_indexes[identity] = {}
            elif comments and not current["help"]:
                current["help"] = " ".join(comments)
            comments = []
        elif current is not None and "=" in raw and not line.startswith(("#", ";")):
            key, value = raw.split("=", 1)
            key, value = key.strip(), value.strip()
            indexes = setting_indexes[current["name"].casefold()]
            existing = indexes.get(key.casefold())
            setting = {"key": key, "value": value, "help": " ".join(comments)}
            if existing is None:
                indexes[key.casefold()] = len(current["settings"])
                current["settings"].append(setting)
            else:
                # Win32 INI section and key lookup is case-insensitive. Match that
                # behavior and expose the final authored value only once.
                current["settings"][existing] = setting
            comments = []
        elif not line:
            comments = []
    return sections


def _gameplay_settings_schema():
    """Presentation schema for the INI: layout, labels, help, dev flags.

    Purely cosmetic. GameplayTweaks.ini stays the source of truth for which
    settings exist; a missing or malformed schema degrades to the plain
    section-per-category rendering rather than hiding anything.
    """
    try:
        return json.loads(SETTINGS_SCHEMA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _clamp_displayed_settings(sections, ranges):
    """Never show a value the game will not actually use.

    Saving already clamps to the schema range, but reading did not, so a stored
    out-of-range value was displayed back verbatim until that exact field was
    re-saved. `[HumanMovement] BaseMoveRate=2` was shown as 2 while the engine's
    move-rate native caps at 1.15, so the editor stated a setting the game was
    not applying. Clamp on read as well, and mark the row so the UI can say the
    stored value was out of range rather than silently rewriting history.
    """
    for section in sections:
        for setting in section["settings"]:
            bounds = ranges.get(f"{section['name']}|{setting['key']}")
            if not isinstance(bounds, dict):
                continue
            try:
                number = float(setting["value"])
            except (TypeError, ValueError):
                continue
            clamped = number
            if "min" in bounds:
                clamped = max(float(bounds["min"]), clamped)
            if "max" in bounds:
                clamped = min(float(bounds["max"]), clamped)
            if clamped != number:
                setting["value"] = f"{clamped:g}"
                setting["storedValue"] = f"{number:g}"
                setting["clampedOnRead"] = True
    return sections


def get_gameplay_settings():
    if not GAMEPLAY_INI_FILE.exists():
        return {"available": False, "file": str(GAMEPLAY_INI_FILE), "sections": [],
                "schema": _gameplay_settings_schema()}
    schema = _gameplay_settings_schema()
    sections = _clamp_displayed_settings(
        _parse_gameplay_settings(GAMEPLAY_INI_FILE.read_text(encoding="utf-8-sig")),
        schema.get("ranges", {}))
    return {"available": True, "file": str(GAMEPLAY_INI_FILE), "sections": sections,
            "schema": schema}


def save_gameplay_settings(edits):
    if not GAMEPLAY_INI_FILE.exists():
        raise ValueError("GameplayTweaks.ini is not installed for this editor profile")
    ranges = _gameplay_settings_schema().get("ranges", {})
    wanted_authored = {}
    for edit in edits:
        section, key = str(edit.get("section", "")), str(edit.get("key", ""))
        value = str(edit.get("value", ""))
        bounds = ranges.get(f"{section}|{key}")
        if isinstance(bounds, dict):
            try:
                number = float(value)
                if "min" in bounds:
                    number = max(float(bounds["min"]), number)
                if "max" in bounds:
                    number = min(float(bounds["max"]), number)
                value = f"{number:g}"
            except (TypeError, ValueError):
                raise ValueError(f"{section}/{key} must be a number")
        wanted_authored[(section, key)] = value
    wanted = {(section.casefold(), key.casefold()): value
              for (section, key), value in wanted_authored.items()}
    lines, section, changed = GAMEPLAY_INI_FILE.read_text(encoding="utf-8-sig").splitlines(), "", 0
    for index, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif "=" in raw and not stripped.startswith(("#", ";")):
            key = raw.split("=", 1)[0].strip()
            lookup = (section.casefold(), key.casefold())
            if lookup in wanted:
                lines[index] = f"{key}={wanted[lookup]}"; changed += 1
    available = {(s["name"].casefold(), setting["key"].casefold())
                 for s in get_gameplay_settings()["sections"] for setting in s["settings"]}
    missing = set(wanted) - available
    if missing:
        authored_missing = [(s, k) for s, k in wanted_authored
                            if (s.casefold(), k.casefold()) in missing]
        raise ValueError("Unknown INI setting(s): " + ", ".join(f"{s}/{k}" for s, k in sorted(authored_missing)))
    GAMEPLAY_INI_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    installed = GAME_ROOT / "GameplayTweaks.ini"
    if (GAME_ROOT / "GameplayTweaks.asi").exists() and not (installed.exists() and os.path.samefile(GAMEPLAY_INI_FILE, installed)):
        shutil.copy2(GAMEPLAY_INI_FILE, installed)
    return changed


def get_alcohol_strengths():
    return _get_alcohol_strengths()


def save_alcohol_strengths(entries):
    return _save_alcohol_strengths(entries)


def _craft_recipe_json(recipe):
    return {
        "recipe_id": recipe.recipe_id,
        "category": recipe.category,
        "title": recipe.title,
        "description": recipe.description,
        "station": recipe.station,
        "output_item": recipe.output_item,
        "output_quantity": recipe.output_quantity,
        "ingredients": [{"item": part.item, "quantity": part.quantity}
                        for part in recipe.ingredients],
        "unlock": recipe.unlock,
    }


def _craft_recipe_from_json(row):
    if not isinstance(row, dict):
        raise ValueError("every custom recipe must be an object")
    ingredients = row.get("ingredients", [])
    if not isinstance(ingredients, list):
        raise ValueError(f"{row.get('recipe_id', 'recipe')}: ingredients must be a list")
    try:
        return _CraftRecipe(
            recipe_id=str(row.get("recipe_id", "")).strip(),
            category=str(row.get("category", "")).strip(),
            title=str(row.get("title", "")).strip(),
            description=str(row.get("description", "")).strip(),
            station=str(row.get("station", "")).strip(),
            output_item=str(row.get("output_item", "")).strip(),
            output_quantity=int(row.get("output_quantity", 1)),
            ingredients=[_CraftIngredient(str(part.get("item", "")).strip(),
                                          int(part.get("quantity", 1)))
                         for part in ingredients if isinstance(part, dict)],
            unlock=str(row.get("unlock", "")).strip(),
        )
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{row.get('recipe_id', 'recipe')}: quantities must be whole numbers") from ex


def get_custom_crafting():
    available = CUSTOM_CRAFTING_FILE.parent.exists() and VANILLA_CRAFTING_FILE.exists()
    vanilla = _load_craft_recipes(VANILLA_CRAFTING_FILE) if VANILLA_CRAFTING_FILE.exists() else []
    custom = _load_craft_recipes(CUSTOM_CRAFTING_FILE)
    catalog = ds_dir("mine") / CATALOG_FILE
    catalog_keys = _craft_catalog_item_keys(catalog) if catalog.exists() else None
    return {
        "available": available,
        "customFile": str(CUSTOM_CRAFTING_FILE),
        "vanillaFile": str(VANILLA_CRAFTING_FILE),
        "vanilla": [_craft_recipe_json(recipe) for recipe in vanilla],
        "custom": [_craft_recipe_json(recipe) for recipe in custom],
        "errors": _validate_craft_recipes(custom, catalog_keys),
    }


def save_custom_crafting(rows):
    if not isinstance(rows, list):
        raise ValueError("recipes must be a list")
    recipes = [_craft_recipe_from_json(row) for row in rows]
    catalog = ds_dir("mine") / CATALOG_FILE
    catalog_keys = _craft_catalog_item_keys(catalog) if catalog.exists() else None
    errors = _validate_craft_recipes(recipes, catalog_keys)
    if errors:
        raise ValueError("\n".join(errors))
    _save_craft_recipes(CUSTOM_CRAFTING_FILE, recipes)
    return len(recipes)


def _raw_labels():
    if not LABELS_FILE.exists():
        return {}
    return json.loads(LABELS_FILE.read_text(encoding="utf-8"))


def get_labels():
    labels = _raw_labels()
    effects = labels.get("effects", {})
    # Catalog normalization converts recovered EFFECT_* references to their
    # canonical JOAAT keys. Keep editor labels attached across that conversion.
    for key, value in list(effects.items()):
        if not key.startswith("0x"):
            effects.setdefault(f"0x{joaat(key):08X}", value)
    return labels


def save_label(scope, key, value):
    labels = _raw_labels()
    scoped = labels.setdefault(scope, {})
    if value.strip():
        scoped[key] = value.strip()
    else:
        scoped.pop(key, None)
    LABELS_FILE.write_text(json.dumps(labels, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1


def parse_gxt2(path):
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if " = " in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split(" = ", 1)
            if key.strip():
                values[key.strip()] = value
    return values


def valid_gxt_key(key):
    """LML accepts symbolic keys or exactly eight hexadecimal digits."""
    key = (key or "").strip()
    return bool(re.fullmatch(r"(?:0x[0-9A-Fa-f]{8}|[A-Za-z][A-Za-z0-9_]{0,127})", key))


def canonical_localization_key(key):
    key = (key or "").strip()
    return f"0x{key[2:].upper()}" if re.fullmatch(r"0x[0-9A-Fa-f]{8}", key) else key


def _read_online_localization():
    try:
        values = json.loads(ONLINE_LOCALIZATION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {
        canonical_localization_key(key): value
        for key, value in values.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _catalog_localization_aliases(ds, source_values):
    """Map blank primary UI keys to the Online alternate text they reference."""
    try:
        root = ET.parse(data_file_path(CATALOG_FILE, ds)).getroot()
    except (OSError, ET.ParseError):
        return {}
    aliases = {}
    type_targets = {
        "LABEL_TYPE_ALT_NAME": "key",
        "LABEL_TYPE_ALT_DESC": "description",
    }
    for item in root.findall("./catalog/items/item"):
        ui = item.find("ui")
        if ui is None:
            continue
        for target_tag in ("key", "description"):
            primary = canonical_localization_key(txt(ui, target_tag))
            if not primary or source_values.get(primary):
                continue
            hashed = f"0x{joaat(primary):08X}"
            if source_values.get(hashed):
                aliases[primary] = source_values[hashed]
        localization = ui.find("localization")
        if localization is None:
            continue
        for alternate in localization.findall("item"):
            target_tag = type_targets.get(txt(alternate, "type"))
            primary = canonical_localization_key(txt(ui, target_tag)) if target_tag else ""
            if not primary or source_values.get(primary):
                continue
            for value_node in alternate.findall("./values/item"):
                alternate_key = canonical_localization_key(value_node.text)
                value = source_values.get(alternate_key, "")
                if value:
                    aliases[primary] = value
                    break
    return aliases


def _localization_baseline(ds="mine"):
    story = json.loads(VANILLA_LOCALIZATION_FILE.read_text(encoding="utf-8"))
    online = _read_online_localization()
    direct = {**story, **online}
    aliases = _catalog_localization_aliases(ds, direct)
    return {**direct, **aliases}, story, online, aliases


def get_localization(ds="mine"):
    baseline, story, online, aliases = _localization_baseline(ds)
    overrides = parse_gxt2(ds_dir(ds) / LOCALIZATION_FILE)
    return {"values": {**baseline, **overrides}, "vanilla": baseline,
            "overrides": overrides, "file": LOCALIZATION_FILE,
            "storyCount": len(story), "onlineCount": len(online),
            "alternateAliases": len(aliases)}


def ensure_localization_install():
    """Ensure LML actually loads the localization file edited by LEXEDITOR."""
    install_path = ds_dir("mine") / "install.xml"
    if not install_path.exists():
        return
    tree = ET.parse(install_path)
    resources = tree.getroot().find("Resources")
    if resources is None:
        raise ValueError(f"Missing Resources element in {install_path}")
    if any((node.text or "").strip().lower() == LOCALIZATION_FILE.lower()
           for node in resources.findall("./Resource/DataFile")):
        return
    resource = ET.Element("Resource")
    ET.SubElement(resource, "DataFile").text = LOCALIZATION_FILE
    resources.insert(0, resource)
    ET.indent(tree, space="    ")
    tree.write(install_path, encoding="utf-8", xml_declaration=False)


def ensure_file_replacement(game_path, file_path):
    """Add one LML replacement mapping without disturbing existing mappings."""
    install_path = ds_dir("mine") / "install.xml"
    if not install_path.exists():
        raise ValueError(f"Missing install.xml in {ds_dir('mine')}")
    tree = ET.parse(install_path)
    root = tree.getroot()
    if any((node.findtext("GamePath") or "").strip() == game_path
           and (node.findtext("FilePath") or "").strip() == file_path
           for node in root.findall(".//FileReplacement")):
        return False
    resources = root.find("Resources")
    if resources is None:
        raise ValueError(f"Missing Resources element in {install_path}")
    resource = next((node for node in resources.findall("Resource")
                     if node.find("FileReplacement") is not None), None)
    if resource is None:
        resource = ET.SubElement(resources, "Resource")
    replacement = ET.SubElement(resource, "FileReplacement")
    ET.SubElement(replacement, "GamePath").text = game_path
    ET.SubElement(replacement, "FilePath").text = file_path
    ET.indent(tree, space="    ")
    tree.write(install_path, encoding="utf-8", xml_declaration=False)
    return True


def remove_file_replacement(game_path, file_path):
    """Remove an exact LML replacement mapping while preserving its siblings."""
    install_path = ds_dir("mine") / "install.xml"
    if not install_path.exists():
        return False
    tree = ET.parse(install_path)
    root = tree.getroot()
    changed = False
    for resource in root.findall(".//Resource"):
        for node in list(resource.findall("FileReplacement")):
            if ((node.findtext("GamePath") or "").strip() == game_path and
                    (node.findtext("FilePath") or "").strip() == file_path):
                resource.remove(node)
                changed = True
    if changed:
        ET.indent(tree, space="    ")
        tree.write(install_path, encoding="utf-8", xml_declaration=False)
    return changed


def save_localization(edits):
    path = ds_dir("mine") / LOCALIZATION_FILE
    values = parse_gxt2(path)
    vanilla, _, _, _ = _localization_baseline("mine")
    for edit in edits:
        key, value = edit.get("key", "").strip(), edit.get("value", "")
        if key:
            if not valid_gxt_key(key):
                raise ValueError(f"Invalid localization key for LML: {key}")
            value = value.replace("\r", " ").replace("\n", " ")
            if value == vanilla.get(key, ""):
                values.pop(key, None)
            else:
                values[key] = value
    invalid = [key for key in values if not valid_gxt_key(key)]
    if invalid:
        raise ValueError("Invalid localization keys already on disk: " + ", ".join(invalid))
    lines = ["[LEXEDITOR OVERRIDES]", ""]
    lines.extend(f"{key} = {values[key]}" for key in sorted(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ensure_localization_install()
    return len(edits)


def load_file(name, ds="mine"):
    key = (ds, name)
    path = data_file_path(name, ds)
    disk_mtime = path.stat().st_mtime_ns
    if (key in _files and _files[key].get("mtime") == disk_mtime
            and _files[key].get("path") == path):
        return _files[key]
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    decl = text.split("\n", 1)[0].strip() if text.lstrip().startswith("<?xml") else '<?xml version="1.0" encoding="UTF-8"?>'
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(text, parser=parser)
    normalized_name = str(name).replace("\\", "/")
    weapon_filename = Path(normalized_name).name.casefold()
    if weapon_filename.startswith("weapon") and weapon_filename.endswith(".ymt"):
        for item in root.iter("Item"):
            resolved = WEAPON_SCHEMA_TYPES.get(item.get("type"))
            if resolved:
                item.set("type", resolved)
        for node in root.iter():
            resolved = WEAPON_SCHEMA_FIELDS.get(node.tag)
            if resolved:
                node.tag = resolved
    if ds in {"prices1899", "kiddos"} and name == CATALOG_FILE:
        normalize_reference_catalog(root)
    _files[key] = {"root": root, "bom": bom, "decl": decl,
                   "mtime": disk_mtime, "path": path}
    return _files[key]


def normalize_reference_catalog(root):
    """Normalize CodeX-style reference catalogs in memory only.

    The supplied 1899 catalog uses capitalized <Item> elements and lowercase
    identifiers, while our parser and key joins use CodeX's lowercase <item>
    element form with uppercase identifiers. The dataset is read-only, so this
    canonicalization cannot modify the third-party source file on disk.
    """
    def ident(value):
        if not value:
            return value
        if value.lower().startswith("0x"):
            return "0x" + value[2:].upper()
        return value.upper()

    for elem in root.iter():
        if elem.tag == "Item":
            elem.tag = "item"
        if elem.tag in {
            "key", "category", "group", "item", "costtype", "slotid", "id",
            "durationcategory",
        } and elem.text:
            elem.text = ident(elem.text.strip())
        if "key" in elem.attrib:
            elem.set("key", ident(elem.get("key")))


def save_file(name, ds="mine"):
    if DATASETS[ds]["readonly"]:
        raise PermissionError(f"dataset '{ds}' is read-only")
    entry = _files[(ds, name)]
    if name == WEAPONS_FILE and ds == "mine":
        _assert_weapon_projectile_flags(
            entry["root"], load_file(WEAPONS_FILE, "vanilla")["root"])
    path = entry.get("path") or data_file_path(name, ds)
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    body = ET.tostring(entry["root"], encoding="unicode")
    out = entry["decl"] + "\n" + body
    data = out.encode("utf-8")
    if entry["bom"]:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    entry["mtime"] = path.stat().st_mtime_ns


def joaat(s):
    h = 0
    for c in s.lower().encode("latin-1"):
        h = (h + c) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def canonical_effect_key(key):
    key = (key or "").strip()
    return f"0x{key[2:].upper()}" if key.lower().startswith("0x") else f"0x{joaat(key):08X}"


_label_cache = None


def effect_label_map(all_ids):
    """Some effect keys exist only as hashes even in Rockstar's data. They
    usually follow <FAMILY>_<SUFFIX> naming, so brute-force every readable
    effect family x suffix combination and index by hash — a hash match is
    proof the guessed name is the original string."""
    global _label_cache
    if _label_cache is not None:
        return _label_cache
    suffixes = [""] + [f"_{n}" for n in range(0, 51)] + \
        ["_GOLD", "_EMPTY", "_MAX", "_MIN", "_FULL", "_OVERPOWERED", "_DRAIN",
         "_SMALL", "_MEDIUM", "_LARGE", "_LOW", "_HIGH", "_ALL"]
    extra = ["_GOLD", "_HORSE", "_CORE"]
    families = set()
    for i in all_ids:
        if i and not i.startswith("0x"):
            families.add(i)
            for e in extra:
                families.add(i + e)
    _label_cache = {}
    for fam in families:
        for suf in suffixes:
            name = fam + suf
            _label_cache[joaat(name)] = name
    return _label_cache


def txt(elem, tag, default=""):
    child = elem.find(tag)
    return (child.text or default) if child is not None and child.text else default


ITEM_TOKEN_PATTERN = r"\b(?:AMMO|CLOTHING|CONSUMABLE|DOCUMENT|KIT|LEX|PROVISION|REWARD|UPGRADE|WEAPON)_[A-Z0-9_]+\b"
ITEM_TOKEN_RE = re.compile(ITEM_TOKEN_PATTERN)
SCRIPT_GRANT_HINT_RE = re.compile(
    r"(INVENTORY|GIVE|GRANT|REWARD|AWARD|ADD|CREATE_ITEM|LOOT|PICKUP)", re.I
)


def catalog_model(it):
    for tag in ("model", "modelName", "archetype"):
        child = it.find(tag)
        if child is not None and child.text:
            return child.text
    return ""


def catalog_item_model(item_key, ds="mine"):
    """Return the exact model field for one catalog item."""
    root = load_file(CATALOG_FILE, ds)["root"]
    catalog = root.find("catalog")
    items = catalog.find("items") if catalog is not None else None
    for item in items.findall("item") if items is not None else []:
        key = item.get("key") or txt(item, "key")
        if key == item_key:
            return catalog_model(item)
    raise ValueError(f"Unknown catalog item: {item_key}")


def catalog_preview_components(item_key, model, ds="mine"):
    """Find one baseline component per model suffix group from catalog data."""
    root = load_file(CATALOG_FILE, ds)["root"]
    records = root.findall("./catalog/items/item")
    base = next((item for item in records
                 if (item.get("key") or txt(item, "key")) == item_key), None)
    if base is None or txt(base, "group") != "WEAPON":
        return ()
    prefix = model.casefold() + "_"
    choices = {}
    for item in records:
        if txt(item, "group") != "WEAPON_MOD":
            continue
        candidate = catalog_model(item)
        if not candidate.casefold().startswith(prefix):
            continue
        suffix = candidate.casefold()[len(prefix):]
        match = re.fullmatch(r"([a-z][a-z_]*?)(\d+)", suffix)
        if match is None:
            continue
        family, number = match.group(1), int(match.group(2))
        current = choices.get(family)
        ranked = (number, candidate.casefold(), candidate)
        if current is None or ranked < current:
            choices[family] = ranked
    return tuple(choices[family][2] for family in sorted(choices))


def provenance_cache_key(ds):
    paths = [ds_dir(ds) / name for name in [CATALOG_FILE, CHALLENGES_FILE, GOALS_FILE, MATRIX_FILE] + LOOT_FILES]
    paths += [SCRIPT_PROVENANCE_FILE, LOOT_USAGE_FILE, COLLECTIBLE_LOCATIONS_FILE]
    paths += [p for d in SCRIPT_REFERENCE_DIRS if d.exists() for p in d.glob("*.c")]
    stats = []
    for path in paths:
        try:
            stat = path.stat()
            stats.append((str(path), stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            continue
    return tuple(stats)


def add_provenance(bucket, key, source_type, file, record="", detail="", confidence="confirmed",
                   acquisition=True, repeatable=None, quantity=""):
    if not key:
        return
    bucket.setdefault(key, []).append({
        "type": source_type,
        "file": file,
        "record": record,
        "detail": detail,
        "confidence": confidence,
        "acquisition": bool(acquisition),
        "repeatable": repeatable,
        "quantity": quantity,
    })


def build_challenge_reward_provenance(ds, valid_keys):
    out = {}
    path = ds_dir(ds) / CHALLENGES_FILE
    if not path.exists():
        return out
    root = load_file(CHALLENGES_FILE, ds)["root"]
    for strand in root.findall(".//challenges/Item"):
        strand_name = txt(strand, "name")
        ranks = strand.find("ranks")
        if ranks is None:
            continue
        for rank_number, rank in enumerate(ranks.findall("Item"), 1):
            goals = [node.text for node in rank.findall("./goalHashes/Item") if node.text]
            record = f"{strand_name} rank {rank_number}"
            if goals:
                record += f" ({', '.join(goals)})"
            for reward in rank.findall(".//reward/rewards/Item"):
                unlock = txt(reward, "unlock")
                reward_type = txt(reward, "rewardType")
                if unlock in valid_keys:
                    add_provenance(out, unlock, "Challenge reward", CHALLENGES_FILE, record,
                                   reward_type or "unlock", "confirmed", True, False, "1")
                elif reward_type in valid_keys:
                    add_provenance(out, reward_type, "Challenge reward", CHALLENGES_FILE, record,
                                   "rewardType", "confirmed", True, False, "1")
    return out


def build_script_reference_provenance(valid_keys):
    out = {}
    if not valid_keys:
        return out
    if SCRIPT_PROVENANCE_FILE.exists():
        try:
            indexed = load_script_provenance_index()
            for key, rows in indexed.get("items", {}).items():
                if key not in valid_keys:
                    continue
                for row in rows:
                    # Incidental hits are loaded on demand by the Sources dialog.
                    # Keeping tens of thousands of them in /api/catalog made every
                    # ordinary Items render pay a large payload and memory cost.
                    if not row.get("acquisition"):
                        continue
                    add_provenance(out, key, row.get("type", "Script reference"),
                                   row.get("file", ""), row.get("record", ""),
                                   row.get("detail", ""), row.get("confidence", "incidental"),
                                   row.get("acquisition", False), row.get("repeatable"),
                                   row.get("quantity", ""))
            return out
        except (OSError, ValueError, TypeError):
            pass
    max_refs_per_item = 40
    existing_dirs = [d for d in SCRIPT_REFERENCE_DIRS if d.exists()]
    if existing_dirs:
        try:
            proc = subprocess.run(
                ["rg", "-n", "--no-heading", "-I", ITEM_TOKEN_PATTERN] + [str(d) for d in existing_dirs],
                cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore",
                timeout=12, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode in (0, 1):
                for raw in proc.stdout.splitlines():
                    parts = raw.split(":", 2)
                    if len(parts) != 3:
                        continue
                    file_name, line_number, line = parts
                    hits = set(ITEM_TOKEN_RE.findall(line)) & valid_keys
                    if not hits:
                        continue
                    grant_like = bool(SCRIPT_GRANT_HINT_RE.search(line))
                    confidence = "candidate" if grant_like else "incidental"
                    source_type = "Script grant candidate" if grant_like else "Script reference"
                    detail = line.strip()
                    if len(detail) > 180:
                        detail = detail[:177] + "..."
                    for key in hits:
                        if len(out.get(key, [])) >= max_refs_per_item:
                            continue
                        add_provenance(out, key, source_type, file_name, f"line {line_number}", detail,
                                       confidence, grant_like, None, "")
                return out
        except (OSError, subprocess.TimeoutExpired):
            out = {}
    for directory in SCRIPT_REFERENCE_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("*.c"):
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            rel = str(path.relative_to(PROJECT_ROOT))
            for line_number, line in enumerate(lines, 1):
                hits = set(ITEM_TOKEN_RE.findall(line)) & valid_keys
                if not hits:
                    continue
                grant_like = bool(SCRIPT_GRANT_HINT_RE.search(line))
                confidence = "candidate" if grant_like else "incidental"
                source_type = "Script grant candidate" if grant_like else "Script reference"
                detail = line.strip()
                if len(detail) > 180:
                    detail = detail[:177] + "..."
                for key in hits:
                    if len(out.get(key, [])) >= max_refs_per_item:
                        continue
                    add_provenance(out, key, source_type, rel, f"line {line_number}", detail,
                                   confidence, grant_like, None, "")
    return out


def load_script_provenance_index():
    global _SCRIPT_INDEX_CACHE
    if _SCRIPT_INDEX_CACHE is None:
        if SCRIPT_PROVENANCE_FILE.exists():
            with gzip.open(SCRIPT_PROVENANCE_FILE, "rt", encoding="utf-8") as handle:
                _SCRIPT_INDEX_CACHE = json.load(handle)
        else:
            _SCRIPT_INDEX_CACHE = {"items": {}}
    return _SCRIPT_INDEX_CACHE


def get_item_script_provenance(key):
    rows = load_script_provenance_index().get("items", {}).get(key, [])
    return {"item": key, "rows": rows, "count": len(rows),
            "generated": load_script_provenance_index().get("generated")}


def normalized_name(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def build_fixed_placement_provenance(ds, items):
    out = {}
    if not COLLECTIBLE_LOCATIONS_FILE.exists():
        return out
    localization = get_localization(ds)
    names = {}
    for item in items:
        current = localization["values"].get(item.get("nameKey"), "")
        vanilla = localization["vanilla"].get(item.get("nameKey"), "")
        for name in (current, vanilla):
            if normalized_name(name):
                names.setdefault(normalized_name(name), set()).add(item["key"])
    with COLLECTIBLE_LOCATIONS_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            matches = names.get(normalized_name(row.get("name")), set())
            if len(matches) != 1:
                continue
            key = next(iter(matches))
            category = (row.get("category") or "collectible").replace("_", " ").title()
            coords = f"{row.get('x', '?')}, {row.get('y', '?')}"
            add_provenance(out, key, "Fixed world placement", "GameplayTweaks/collectibles.csv",
                           row.get("name", ""), f"{category} at map coordinates {coords}",
                           "confirmed", True, False, "1")
    return out


def parse_number(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_number(value):
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_loot_chain_provenance(ds, valid_keys):
    """Resolve table-to-table chains to their catalog leaves and trigger sites."""
    out = {}
    tables = {}
    for file in LOOT_FILES:
        if not (ds_dir(ds) / file).exists():
            continue
        for table in get_loot(file, ds)["tables"]:
            tables[table["key"]] = {"file": file, **table}
    usage = {}
    if LOOT_USAGE_FILE.exists():
        try:
            usage = json.loads(LOOT_USAGE_FILE.read_text(encoding="utf-8")).get("tables", {})
        except (OSError, ValueError, TypeError):
            usage = {}

    def roots_for(table_key, table):
        info = usage.get(table_key, {})
        roots = []
        for prop in info.get("pickups", []):
            roots.append(("World loot prop", prop, "confirmed", True))
        for script in info.get("scripts", []):
            roots.append(("Scripted loot", script, "confirmed", True))
        for script in info.get("mpScripts", []):
            roots.append(("RDO script reference", script, "incidental", False))
        semantic = {
            "loot_table_ped.meta": "Ped loot",
            "loot_table_container.meta": "Container loot",
            "loot_table_herb.meta": "Plant harvest",
            "loot_table_reward.meta": "Reward loot",
        }.get(table["file"])
        if semantic:
            roots.append((semantic, table_key, "confirmed", True))
        if not roots and table["file"] != "loot_table_itemgroups.meta":
            roots.append(("Engine-bound loot", table_key, "candidate", True))
        return roots

    def walk(root_key, current_key, path, rate, quantities, conditions, depth=0):
        if depth > 12 or current_key in path:
            return []
        table = tables.get(current_key)
        if not table:
            return []
        found = []
        next_path = path + [current_key]
        for entry in table["entries"]:
            entry_rate = rate * parse_number(entry.get("rate"), 1.0)
            quantity = entry.get("min") or entry.get("max")
            next_quantities = quantities + ([f"{entry.get('min') or 'default'}-{entry.get('max') or entry.get('min') or 'default'}"] if quantity else [])
            next_conditions = conditions + ([entry["rewardcondition"]] if entry.get("rewardcondition") else [])
            name = entry.get("name", "")
            if entry.get("type") == "Table":
                found.extend(walk(root_key, name, next_path, entry_rate, next_quantities,
                                  next_conditions, depth + 1))
            elif name in valid_keys and entry.get("type") in ("Item", "Collectible"):
                found.append((name, next_path, entry_rate, next_quantities, next_conditions))
        return found

    seen = set()
    for table_key, table in tables.items():
        roots = roots_for(table_key, table)
        if not roots:
            continue
        for key, path, rate, quantities, conditions in walk(table_key, table_key, [], 1.0, [], []):
            chain = " -> ".join(path)
            for source_type, record, confidence, acquisition in roots:
                signature = (key, source_type, record, chain, format_number(rate))
                if signature in seen or len(out.get(key, [])) >= 120:
                    continue
                seen.add(signature)
                detail = f"{chain}; cumulative roll rate {format_number(rate)}"
                if conditions:
                    detail += "; conditions: " + ", ".join(dict.fromkeys(conditions))
                add_provenance(out, key, source_type, table["file"], record, detail,
                               confidence, acquisition, None,
                               " x ".join(quantities) if quantities else "default")
    return out


def provenance_coverage(ds):
    scripts = sum(len(list(path.glob("*.c"))) for path in SCRIPT_REFERENCE_DIRS if path.exists())
    return [
        {"layer": "Catalog shops and recipes", "status": "complete", "detail": CATALOG_FILE},
        {"layer": "Loot, containers, peds, plants and nested groups", "status": "complete", "detail": f"{len(LOOT_FILES)} loot files plus trigger index"},
        {"layer": "Skinning yields", "status": "complete", "detail": MATRIX_FILE},
        {"layer": "Challenge rewards", "status": "complete", "detail": CHALLENGES_FILE},
        {"layer": "Known fixed collectible placements", "status": "complete" if COLLECTIBLE_LOCATIONS_FILE.exists() else "unavailable", "detail": str(COLLECTIBLE_LOCATIONS_FILE)},
        {"layer": "Story script and mission references", "status": "complete" if SCRIPT_PROVENANCE_FILE.exists() else "partial", "detail": f"{scripts} decompiled scripts; indirect grants remain confidence-labelled"},
        {"layer": "Engine-only dynamic grants", "status": "partial", "detail": "No public exhaustive runtime registry; candidates remain explicitly unconfirmed"},
    ]


def build_static_provenance(ds, items):
    valid_keys = {item["key"] for item in items}
    cache_key = (ds, provenance_cache_key(ds))
    cached = _PROVENANCE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    out = {}
    sources = [build_challenge_reward_provenance(ds, valid_keys),
               build_loot_chain_provenance(ds, valid_keys),
               build_fixed_placement_provenance(ds, items)]
    if ds == "mine":
        sources.append(build_script_reference_provenance(valid_keys))
    for source in sources:
        for key, rows in source.items():
            out.setdefault(key, []).extend(rows)
    _PROVENANCE_CACHE.clear()
    _PROVENANCE_CACHE[cache_key] = out
    return out


def attr_value(elem, tag, default=None):
    child = elem.find(tag)
    if child is None:
        return default
    return child.get("value", default)


# ---------------- catalog ----------------

def _origin_provenance_data():
    if not ORIGIN_PROVENANCE_FILE.exists():
        return {}
    data = json.loads(ORIGIN_PROVENANCE_FILE.read_text(encoding="utf-8"))
    if data.get("schema") not in {1, 2}:
        return {}
    return data


def _write_origin_provenance(data):
    """Atomically save display-only origin metadata."""
    data["schema"] = 2
    for field in (
        "catalogItems", "catalogEffects", "customCatalogItems",
        "customCatalogEffects", "weapons", "ammo", "weaponHashes", "ammoHashes",
    ):
        data[field] = sorted(set(data.get(field, [])))
    ORIGIN_PROVENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ORIGIN_PROVENANCE_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(ORIGIN_PROVENANCE_FILE)
    _ORIGIN_MARKER_CACHE.clear()


def record_custom_catalog_origin(section, key):
    """Persist a record created through LEXEDITOR without changing its key."""
    field = {
        "items": "customCatalogItems",
        "effects": "customCatalogEffects",
    }.get(section)
    if field is None:
        raise ValueError(f"Unknown custom catalog origin section: {section}")
    with _lock:
        data = _origin_provenance_data()
        values = set(data.get(field, []))
        values.add(key)
        data[field] = sorted(values)
        _write_origin_provenance(data)


def catalog_origin_marker_sets(ds="mine"):
    """Return Online and local origins from the authoritative root catalog.

    Provenance comes from canonical source-record comparison. The marker file
    is display metadata only; it does not alter catalog keys or saved values.
    """
    if ds != "mine":
        return {
            "rdoItems": set(), "rdoEffects": set(),
            "customItems": set(), "customEffects": set(),
        }
    active = data_file_path(CATALOG_FILE, ds)
    baseline = ds_dir(ds) / CATALOG_FILE
    if active.resolve() != baseline.resolve():
        return {
            "rdoItems": set(), "rdoEffects": set(),
            "customItems": set(), "customEffects": set(),
        }
    if not ORIGIN_PROVENANCE_FILE.exists():
        return {
            "rdoItems": set(), "rdoEffects": set(),
            "customItems": set(), "customEffects": set(),
        }
    cache_key = ORIGIN_PROVENANCE_FILE.stat().st_mtime_ns
    cached = _ORIGIN_MARKER_CACHE.get(cache_key)
    if cached is not None:
        return cached
    data = _origin_provenance_data()
    result = {
        "rdoItems": set(data.get("catalogItems", [])),
        "rdoEffects": {canonical_effect_key(key) for key in data.get("catalogEffects", [])},
        "customItems": set(data.get("customCatalogItems", [])),
        "customEffects": {
            canonical_effect_key(key) for key in data.get("customCatalogEffects", [])
        },
    }
    _ORIGIN_MARKER_CACHE.clear()
    _ORIGIN_MARKER_CACHE[cache_key] = result
    return result

def cost_list(container):
    """Parse an <acquirecosts>/<sellprices> element into a list of costs."""
    out = []
    if container is None:
        return out
    for cost in container.findall("item"):
        parts = []
        items_el = cost.find("items")
        if items_el is not None:
            for part in items_el.findall("item"):
                parts.append({
                    "item": txt(part, "item"),
                    "qty": int(float(part.find("quantity").get("value", "0"))) if part.find("quantity") is not None else 0,
                })
        q = cost.find("quantity")
        unlocks = []
        unlock_el = cost.find("unlocks")
        if unlock_el is not None:
            unlocks = [txt(u, "key") for u in unlock_el.findall("item") if txt(u, "key")]
        out.append({
            "key": txt(cost, "key"),
            "costtype": txt(cost, "costtype"),
            "yield": int(float(q.get("value", "1"))) if q is not None else 1,
            "parts": parts,
            "unlocks": unlocks,
        })
    return out


def get_catalog(ds="mine"):
    root = load_file(CATALOG_FILE, ds)["root"]
    origin_markers = catalog_origin_marker_sets(ds)
    shop_listings = {}
    shops_el = root.find("shopsinventories")
    for shop in shops_el.findall("item") if shops_el is not None else []:
        shop_type = txt(shop, "type")
        items_el = shop.find("items")
        for entry in items_el.findall("item") if items_el is not None else []:
            counts = []
            groups = entry.find("requirementgroups")
            for group in groups.findall("item") if groups is not None else []:
                count = attr_value(group, "count")
                if count is not None:
                    counts.append(int(float(count)))
            shop_listings.setdefault(txt(entry, "item"), []).append({
                "shop": shop_type, "quantities": sorted(set(counts)) or [1]
            })
    items = []
    for it in root.find("catalog").find("items").findall("item"):
        tags = parse_catalog_tags(it.find("tags"))
        effects = []
        eff_el = it.find("effectids")
        if eff_el is not None:
            for e in eff_el.findall("item"):
                effects.append(canonical_effect_key(txt(e, "key")))
        carry = []
        mult_el = it.find("multiplicity")
        if mult_el is not None:
            for m in mult_el.findall("item"):
                q = m.find("quantity")
                carry.append({
                    "slot": txt(m, "slotid"),
                    "qty": q.get("value", "0") if q is not None else "0",
                })
        items.append({
            "key": it.get("key") or txt(it, "key"),
            "rdoAdded": (it.get("key") or txt(it, "key")) in origin_markers["rdoItems"],
            "customAdded": (it.get("key") or txt(it, "key")) in origin_markers["customItems"],
            "category": txt(it, "category"),
            "group": txt(it, "group"),
            "tags": tags,
            "buy": cost_list(it.find("acquirecosts")),
            "sell": cost_list(it.find("sellprices")),
            "effects": effects,
            "carry": carry,
            "nameKey": txt(it.find("ui"), "key") if it.find("ui") is not None else "",
            "descriptionKey": txt(it.find("ui"), "description") if it.find("ui") is not None else "",
            "model": catalog_model(it),
            "textures": [{
                "id": txt(texture, "id"),
                "dict": txt(texture, "dict"),
                "type": txt(texture, "type"),
            } for texture in it.findall("./ui/textures/item") if txt(texture, "id")],
            "shopListings": shop_listings.get(it.get("key") or txt(it, "key"), []),
        })
    eff_elems = root.find("effectsids").findall("item")
    labels = effect_label_map([txt(e, "id") for e in eff_elems])
    custom_symbols = _raw_labels().get("effectSymbols", {}) if ds == "mine" else {}
    effects = []
    for e in eff_elems:
        key = canonical_effect_key(txt(e, "key"))
        entry = {
            "key": key,
            "rdoAdded": key in origin_markers["rdoEffects"],
            "customAdded": key in origin_markers["customEffects"],
            "id": txt(e, "id"),
            "value": attr_value(e, "value", "0"),
            "percent": attr_value(e, "percent", "0"),
            "time": attr_value(e, "time", "0"),
            "timeunits": attr_value(e, "timeunits", "0"),
            "durationcategory": txt(e, "durationcategory"),
        }
        if key.startswith("0x"):
            label = labels.get(int(key, 16))
            if label:
                entry["label"] = label
        if custom_symbols.get(key):
            entry["symbol"] = custom_symbols[key]
        effects.append(entry)
    by_key = {item["key"]: item for item in items}
    for item in items:
        item["lootSources"] = []
        item["skinningSources"] = []
        item["provenanceSources"] = []
    for file in LOOT_FILES:
        if not (ds_dir(ds) / file).exists():
            continue
        for table in get_loot(file, ds)["tables"]:
            for entry in table["entries"]:
                # Herb orchids and some other direct catalog drops are tagged
                # Collectible rather than Item, but still name a catalog record.
                target = by_key.get(entry.get("name")) if entry.get("type") in ("Item", "Collectible") else None
                if target is not None:
                    target["lootSources"].append({
                        "file": file, "table": table["key"], "rate": entry.get("rate"),
                        "min": entry.get("min"), "max": entry.get("max"),
                        "condition": entry.get("rewardcondition"),
                    })
    if (ds_dir(ds) / MATRIX_FILE).exists():
        for animal in get_matrix(ds)["animals"]:
            for row in animal["rows"]:
                target = by_key.get(row.get("item"))
                if target is not None:
                    target["skinningSources"].append({
                        "animal": animal["key"], "damage": row.get("damage"),
                        "skin": row.get("skin"), "qty": row.get("qty") or "1",
                    })
    indexed = build_static_provenance(ds, items)
    script_counts = ({key: len(rows) for key, rows in load_script_provenance_index().get("items", {}).items()}
                     if ds == "mine" else {})
    for key, rows in indexed.items():
        target = by_key.get(key)
        if target is not None:
            target["provenanceSources"].extend(rows)
    coverage = provenance_coverage(ds)
    exhaustive = all(layer["status"] == "complete" for layer in coverage)
    for item in items:
        confirmed = len(item["shopListings"]) + sum(
            1 for cost in item["buy"] if cost.get("costtype") == "COST_TYPE_CRAFT"
        )
        confirmed += len(item["skinningSources"])
        confirmed += sum(1 for row in item["provenanceSources"] if row.get("acquisition") and row.get("confidence") == "confirmed")
        candidates = sum(1 for row in item["provenanceSources"] if row.get("acquisition") and row.get("confidence") != "confirmed")
        item["scriptReferenceCount"] = script_counts.get(item["key"], 0)
        item["sourceSummary"] = {
            "confirmed": confirmed,
            "candidates": candidates,
            "references": sum(1 for row in item["provenanceSources"] if not row.get("acquisition")) + item["scriptReferenceCount"],
            "status": "confirmed" if confirmed else ("candidate" if candidates else "unknown"),
            "possibleCutContent": bool(exhaustive and not confirmed and not candidates),
        }
    return {
        "items": items,
        "effects": effects,
        "activeFile": str(data_file_path(CATALOG_FILE, ds)),
        "rdoAddedCounts": {
            "items": len(origin_markers["rdoItems"]),
            "effects": len(origin_markers["rdoEffects"]),
        },
        "customAddedCounts": {
            "items": len(origin_markers["customItems"]),
            "effects": len(origin_markers["customEffects"]),
        },
        "provenanceCoverage": coverage,
        "tagCatalog": build_tag_catalog(items),
    }


def _quick_select_group_nodes(root):
    groups = root.find("ItemGroups")
    return groups.findall("Item") if groups is not None else []


def _quick_select_entry(root, item_key):
    for group in _quick_select_group_nodes(root):
        items = group.find("Items")
        for item in items.findall("Item") if items is not None else []:
            if (item.get("key") or "").strip() == item_key:
                return group, items, item
    return None, None, None


def _quick_select_slots(item):
    rows = []
    slots = item.find("Slots") if item is not None else None
    for slot in slots.findall("Item") if slots is not None else []:
        order = slot.find("SortOrder")
        try:
            sort_order = int(order.get("value", "0")) if order is not None else 0
        except ValueError:
            sort_order = 0
        rows.append({"id": (slot.findtext("Id") or "").strip(),
                     "sortOrder": sort_order})
    return rows


def _quick_select_slots_by_group(root):
    result = {}
    for group in _quick_select_group_nodes(root):
        group_key = (group.get("key") or "").strip()
        if group_key not in QUICK_SELECT_EDITABLE_GROUPS:
            continue
        known = result.setdefault(group_key, set())
        items = group.find("Items")
        for item in items.findall("Item") if items is not None else []:
            known.update(row["id"] for row in _quick_select_slots(item) if row["id"])
    return {group: sorted(slots) for group, slots in result.items()}


def get_quick_select(ds="mine"):
    """Return item-to-radial-slot assignments from the active replacement."""
    path = data_file_path(QUICK_SELECT_FILE, ds)
    if not path.is_file():
        return {"available": False, "activeFile": str(path), "items": {},
                "slotsByGroup": {}, "reason": "quickselectitems.ymt is unavailable"}
    root = load_file(QUICK_SELECT_FILE, ds)["root"]
    items = {}
    for group in _quick_select_group_nodes(root):
        group_key = (group.get("key") or "").strip()
        if group_key not in QUICK_SELECT_EDITABLE_GROUPS:
            continue
        entries = group.find("Items")
        for item in entries.findall("Item") if entries is not None else []:
            key = (item.get("key") or "").strip()
            if key:
                items[key] = {"group": group_key, "slots": _quick_select_slots(item)}
    return {
        "available": True,
        "activeFile": str(path),
        "items": items,
        "slotsByGroup": _quick_select_slots_by_group(root),
        "reason": "",
    }


def _next_quick_select_sort_order(root, group_key, slot_id):
    group = next((node for node in _quick_select_group_nodes(root)
                  if (node.get("key") or "").strip() == group_key), None)
    orders = []
    items = group.find("Items") if group is not None else None
    for item in items.findall("Item") if items is not None else []:
        for row in _quick_select_slots(item):
            if row["id"] == slot_id:
                orders.append(row["sortOrder"])
    return max(orders, default=0) + 10


def _replace_quick_select_slots(item, rows):
    slots = item.find("Slots")
    if slots is None:
        slots = ET.Element("Slots")
        item.insert(0, slots)
    for child in list(slots):
        slots.remove(child)
    slots.text = "\n            "
    for index, row in enumerate(rows):
        entry = ET.SubElement(slots, "Item")
        entry.text = "\n              "
        slot_id = ET.SubElement(entry, "Id")
        slot_id.text = row["id"]
        slot_id.tail = "\n              "
        order = ET.SubElement(entry, "SortOrder", {"value": str(row["sortOrder"])})
        order.tail = "\n            "
        entry.tail = "\n            " if index < len(rows) - 1 else "\n          "


def apply_quick_select_edits(edits):
    """Replace complete slot lists while preserving all other item fields."""
    if not edits:
        return 0
    if not isinstance(edits, list):
        raise ValueError("quickSelect edits must be a list")
    entry = load_file(QUICK_SELECT_FILE)
    original_root = entry["root"]
    root = copy.deepcopy(original_root)
    allowed_by_group = {group: set(slots)
                        for group, slots in _quick_select_slots_by_group(root).items()}
    catalog_ids = set(_catalog_ids())
    changed = 0
    for edit in edits:
        item_key = str(edit.get("item", "")).strip().upper()
        if item_key not in catalog_ids:
            raise ValueError(f"Unknown catalog item: {item_key or '(blank)'}")
        group, items, item = _quick_select_entry(root, item_key)
        current_group = (group.get("key") or "").strip() if group is not None else ""
        if current_group and current_group not in QUICK_SELECT_EDITABLE_GROUPS:
            raise ValueError(f"Unsupported quick-select item group: {current_group}")
        group_key = current_group or (
            QUICK_SELECT_WEAPON_GROUP if item_key.startswith("WEAPON_")
            else QUICK_SELECT_SATCHEL_GROUP
        )
        incoming = edit.get("slots", [])
        if not isinstance(incoming, list) or len(incoming) > 16:
            raise ValueError("Quick-select slots must be a list of at most 16 assignments")
        normalized = []
        seen = set()
        for row in incoming:
            slot_id = str(row.get("id", "")).strip().upper()
            if slot_id not in allowed_by_group.get(group_key, set()):
                raise ValueError(f"Unknown quick-select slot for {group_key}: {slot_id or '(blank)'}")
            if slot_id in seen:
                raise ValueError(f"Duplicate quick-select slot for {item_key}: {slot_id}")
            seen.add(slot_id)
            raw_order = row.get("sortOrder")
            if raw_order is None:
                sort_order = _next_quick_select_sort_order(root, group_key, slot_id)
            else:
                try:
                    sort_order = int(raw_order)
                except (TypeError, ValueError) as error:
                    raise ValueError("Quick-select sort order must be a whole number") from error
                if not 0 <= sort_order <= 1_000_000:
                    raise ValueError("Quick-select sort order is outside the supported range")
            normalized.append({"id": slot_id, "sortOrder": sort_order})
        current = _quick_select_slots(item)
        if item is not None and current == normalized:
            continue
        if not normalized:
            if item is not None:
                items.remove(item)
                changed += 1
            continue
        if item is None:
            group = next((node for node in _quick_select_group_nodes(root)
                          if (node.get("key") or "").strip() == group_key), None)
            if group is None:
                raise ValueError(f"Missing quick-select item group: {group_key}")
            items = group.find("Items")
            if items is None:
                raise ValueError(f"Missing Items collection for {group_key}")
            previous = items.findall("Item")
            item = ET.Element("Item", {"key": item_key})
            if previous:
                item.tail = previous[-1].tail
                previous[-1].tail = "\n        "
            items.append(item)
        _replace_quick_select_slots(item, normalized)
        changed += 1
    if changed:
        entry["root"] = root
        try:
            save_file(QUICK_SELECT_FILE)
        except Exception:
            entry["root"] = original_root
            raise
    return changed


def read_shop_requirement_groups(entry):
    groups_out = []
    groups = entry.find("requirementgroups")
    for group in groups.findall("item") if groups is not None else []:
        requirements = []
        reqs = group.find("requirements")
        for req in reqs.findall("item") if reqs is not None else []:
            requirements.append({
                "type": txt(req, "type"),
                "key": txt(req, "key"),
                "state": attr_value(req, "state", "1"),
                "lock": attr_value(req, "lock", "false"),
            })
        groups_out.append({
            "count": attr_value(group, "count", "1"),
            "requirements": requirements,
        })
    return groups_out


def normalize_shop_requirement_groups(raw_groups, item_key):
    if raw_groups is None:
        return None
    if not isinstance(raw_groups, list) or len(raw_groups) > 128:
        raise ValueError(f"{item_key}: requirement groups must be a list of at most 128 groups")
    normalized = []
    for group_index, group in enumerate(raw_groups, 1):
        if not isinstance(group, dict):
            raise ValueError(f"{item_key}: availability group {group_index} is invalid")
        count = str(group.get("count", "1")).strip()
        if not re.fullmatch(r"-?\d+", count):
            raise ValueError(f"{item_key}: availability group {group_index} count must be a whole number")
        raw_requirements = group.get("requirements", [])
        if not isinstance(raw_requirements, list) or len(raw_requirements) > 128:
            raise ValueError(f"{item_key}: availability group {group_index} has too many conditions")
        requirements = []
        for requirement_index, requirement in enumerate(raw_requirements, 1):
            if not isinstance(requirement, dict):
                raise ValueError(f"{item_key}: condition {group_index}.{requirement_index} is invalid")
            condition_type = str(requirement.get("type", "")).strip()
            key = str(requirement.get("key", "")).strip()
            state = str(requirement.get("state", "1")).strip()
            lock_value = requirement.get("lock", "false")
            lock = str(lock_value).strip().lower() if not isinstance(lock_value, bool) else ("true" if lock_value else "false")
            if not condition_type or not key:
                raise ValueError(f"{item_key}: condition {group_index}.{requirement_index} needs a type and key")
            if not re.fullmatch(r"-?\d+", state):
                raise ValueError(f"{item_key}: condition {group_index}.{requirement_index} state must be a whole number")
            if lock not in {"true", "false"}:
                raise ValueError(f"{item_key}: condition {group_index}.{requirement_index} lock must be true or false")
            requirements.append({"type": condition_type, "key": key, "state": state, "lock": lock})
        normalized.append({"count": count, "requirements": requirements})
    return normalized


def write_shop_requirement_groups(entry, groups):
    current = read_shop_requirement_groups(entry)
    if current == groups:
        return 0
    container = entry.find("requirementgroups")
    if container is None:
        container = ET.SubElement(entry, "requirementgroups")
    tail = container.tail
    container.clear()
    for group in groups:
        group_el = ET.SubElement(container, "item")
        ET.SubElement(group_el, "count", {"value": group["count"]})
        requirements_el = ET.SubElement(group_el, "requirements")
        for requirement in group["requirements"]:
            requirement_el = ET.SubElement(requirements_el, "item")
            ET.SubElement(requirement_el, "type").text = requirement["type"]
            ET.SubElement(requirement_el, "key").text = requirement["key"]
            ET.SubElement(requirement_el, "state", {"value": requirement["state"]})
            ET.SubElement(requirement_el, "lock", {"value": requirement["lock"]})
    ET.indent(container, space="  ", level=5)
    container.tail = tail
    return 1


def get_shops(ds="mine"):
    root = load_file(CATALOG_FILE, ds)["root"]
    listing_pages, categories = catalogue_listing_metadata(root)
    shops = []
    container = root.find("shopsinventories")
    if container is None:
        return {"shops": []}
    for shop in container.findall("item"):
        rows = []
        items_el = shop.find("items")
        for entry in items_el.findall("item") if items_el is not None else []:
            requirement_groups = read_shop_requirement_groups(entry)
            requirements = [requirement for group in requirement_groups for requirement in group["requirements"]]
            item_key = txt(entry, "item")
            rows.append({"item": item_key, "requirementGroups": requirement_groups,
                         "requirements": requirements,
                         "cataloguePages": listing_pages.get((txt(shop, "type"), item_key), [])})
        shop_type = txt(shop, "type")
        shops.append({"type": shop_type, "items": rows,
                      "catalogueCategories": categories.get(shop_type, [])})
    return {"shops": shops}


def apply_shop_edits(edits):
    normalized_edits = []
    for edit in edits:
        shop_type = str(edit.get("type", "")).strip()
        normalized_items = []
        seen = set()
        for raw_item in edit.get("items", []):
            if isinstance(raw_item, str):
                item_key = raw_item.strip()
                groups = None
            elif isinstance(raw_item, dict):
                item_key = str(raw_item.get("item", "")).strip()
                groups = normalize_shop_requirement_groups(raw_item.get("requirementGroups"), item_key)
                catalogue_category = str(raw_item.get("catalogueCategory", "")).strip() or None
            else:
                raise ValueError(f"{shop_type}: invalid shop item")
            if isinstance(raw_item, str):
                catalogue_category = None
            if not item_key:
                raise ValueError(f"{shop_type}: shop item ID is required")
            if item_key in seen:
                raise ValueError(f"{shop_type}: duplicate shop item {item_key}")
            seen.add(item_key)
            normalized_items.append({"item": item_key, "requirementGroups": groups,
                                     "catalogueCategory": catalogue_category})
        normalized_edits.append({"type": shop_type, "items": normalized_items})

    root = load_file(CATALOG_FILE)["root"]
    container = root.find("shopsinventories")
    changed = 0
    for edit in normalized_edits:
        shop = next((s for s in container.findall("item") if txt(s, "type") == edit.get("type")), None)
        if shop is None:
            continue
        items_el = shop.find("items")
        if items_el is None:
            items_el = ET.SubElement(shop, "items")
        wanted_rows = edit.get("items", [])
        wanted = [row["item"] for row in wanted_rows]
        existing = {txt(e, "item"): e for e in items_el.findall("item")}
        # Resolve every new printed destination before the first mutation. A
        # missing category must not leave an in-memory stock row that can leak
        # into a later save.
        for row in wanted_rows:
            if row["item"] not in existing:
                plan = catalogue_placement_plan(
                    root, row["item"], edit.get("type"), row["catalogueCategory"]
                )
                if plan["requiresDestination"]:
                    raise ValueError(plan["reason"])
        for key in list(existing):
            if key not in wanted:
                result = set_item_shop_presence(root, key, edit.get("type"), False)
                changed += result["stock"] + result["catalogue"]
        for key in wanted:
            if key in existing:
                continue
            row = next(candidate for candidate in wanted_rows if candidate["item"] == key)
            result = set_item_shop_presence(
                root, key, edit.get("type"), True, row["catalogueCategory"]
            )
            changed += result["stock"] + result["catalogue"]
        existing = {txt(e, "item"): e for e in items_el.findall("item")}
        for row in wanted_rows:
            groups = row["requirementGroups"]
            if groups is not None and row["item"] in existing:
                changed += write_shop_requirement_groups(existing[row["item"]], groups)
    if changed:
        save_file(CATALOG_FILE)
    return changed


# Catalog tags are typed (key + type). Type hashes are engine family IDs; names
# below are editor labels only. Alcohol drink-class tags are exclusive and drive
# drink interaction / intoxication class — presented as "Alcohol Strength".
TAG_TYPE_LABELS = {
    "0x42D03BDE": "Item flag",
    "0x48FA3731": "Satchel folder",
    "0xC76BC07D": "Document / inspect / drink",
    "0xE599E90D": "Clothing component",
    "0x33634061": "Clothing meta",
    "0xE4521CDF": "Clothing style",
    "0x30ECAC7E": "Weapon engraving design",
    "0x6534EAA0": "Clothing material",
    "0x7E334732": "Clothing palette",
    "0x9E74B133": "Clothing tint",
    "0x912DE0BA": "Clothing decal",
    "0x83752C8C": "Clothing asset",
    "0x7EE8BE10": "Clothing layer",
}

# Exclusive drink-class tags (type 0xC76BC07D) observed on CI_TAG_ITEM_ALCOHOL items.
# Hashes without recovered names keep usage-derived labels — never free-typed.
ALCOHOL_STRENGTH_TAGS = [
    {"key": "CI_TAG_DRINKING_BEER", "type": "0xC76BC07D", "label": "Beer (light)", "rank": 1},
    {"key": "0x435E057A", "type": "0xC76BC07D", "label": "Whiskey", "rank": 2},
    {"key": "0x3B952FEE", "type": "0xC76BC07D", "label": "Rum", "rank": 2},
    {"key": "0xEFAD85F3", "type": "0xC76BC07D", "label": "Spirits (gin / brandy / moonshine)", "rank": 3},
    {"key": "0x88B79CD0", "type": "0xC76BC07D", "label": "Saloon whiskey", "rank": 2},
]
ALCOHOL_STRENGTH_KEYS = {row["key"] for row in ALCOHOL_STRENGTH_TAGS}

# Human labels for a few frequent unresolved flag keys used outside alcohol.
TAG_KEY_LABELS = {
    "0x435E057A": "Alcohol · Whiskey",
    "0x3B952FEE": "Alcohol · Rum",
    "0xEFAD85F3": "Alcohol · Spirits",
    "0x88B79CD0": "Alcohol · Saloon whiskey",
}


def _is_hash_token(value):
    text = str(value or "").strip()
    return bool(re.fullmatch(r"0x[0-9A-Fa-f]{1,8}", text, flags=re.I))


def _normalize_tag_token(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if _is_hash_token(text):
        return "0x" + text[2:].upper().zfill(8)
    return text


def parse_catalog_tags(tags_el):
    tags = []
    if tags_el is None:
        return tags
    for tag in tags_el.findall("item"):
        key = _normalize_tag_token(txt(tag, "key"))
        typ = _normalize_tag_token(txt(tag, "type"))
        if key:
            tags.append({"key": key, "type": typ})
    return tags


def tag_key_label(key):
    key = _normalize_tag_token(key)
    if key in TAG_KEY_LABELS:
        return TAG_KEY_LABELS[key]
    if key.startswith("CI_TAG_"):
        return key.replace("CI_TAG_", "").replace("_", " ").title()
    return key


def tag_type_label(typ):
    typ = _normalize_tag_token(typ)
    return TAG_TYPE_LABELS.get(typ, typ or "(no type)")


def tag_purpose_group(key, typ):
    key = _normalize_tag_token(key)
    typ = _normalize_tag_token(typ)
    if key in ALCOHOL_STRENGTH_KEYS or key == "CI_TAG_ITEM_ALCOHOL":
        return "Alcohol"
    if key.startswith("CI_TAG_ITEM_"):
        return "Item class"
    if key.startswith("CI_TAG_CATEGORY_"):
        return "Category"
    if key.startswith("CI_TAG_SHOP_"):
        return "Shop"
    if key.startswith("CI_TAG_FOLDER_"):
        return "Satchel folder"
    if key.startswith("CI_TAG_PAPER_") or key.startswith("CI_TAG_INSPECT_") or key.startswith("CI_TAG_POCKET_"):
        return "Document & inspect"
    if key.startswith("CI_TAG_WEAPON_") or key.startswith("CI_TAG_LONG_"):
        return "Weapon"
    if key.startswith("CI_TAG_DRINKING_") or key.startswith("CI_TAG_APPLY_") or key.startswith("CI_TAG_REMOVE_"):
        return "Interaction"
    if key.startswith("CI_TAG_"):
        return "Other named"
    if typ in TAG_TYPE_LABELS:
        return f"Unresolved · {TAG_TYPE_LABELS[typ]}"
    return "Unresolved"


def build_tag_catalog(items):
    """Unique observed tags for controlled picking (no free-entry hashes)."""
    seen = {}
    for item in items:
        for tag in item.get("tags") or []:
            key = _normalize_tag_token(tag.get("key"))
            typ = _normalize_tag_token(tag.get("type"))
            if not key:
                continue
            id_ = f"{key}|{typ}"
            row = seen.get(id_)
            if row is None:
                resolved = not _is_hash_token(key)
                seen[id_] = {
                    "key": key,
                    "type": typ,
                    "label": tag_key_label(key),
                    "typeLabel": tag_type_label(typ),
                    "group": tag_purpose_group(key, typ),
                    "resolved": resolved,
                    "count": 1,
                    "pickable": resolved or key in ALCOHOL_STRENGTH_KEYS,
                }
            else:
                row["count"] += 1
    # Ensure alcohol strength options always appear even if a dataset lacks them.
    for row in ALCOHOL_STRENGTH_TAGS:
        id_ = f"{row['key']}|{row['type']}"
        if id_ not in seen:
            seen[id_] = {
                "key": row["key"],
                "type": row["type"],
                "label": row["label"],
                "typeLabel": tag_type_label(row["type"]),
                "group": "Alcohol",
                "resolved": not _is_hash_token(row["key"]),
                "count": 0,
                "pickable": True,
            }
        else:
            seen[id_]["label"] = row["label"]
            seen[id_]["group"] = "Alcohol"
            seen[id_]["pickable"] = True
    catalog = sorted(seen.values(), key=lambda r: (r["group"], r["label"], r["key"], r["type"]))
    return {
        "tags": catalog,
        "types": [{"type": t, "label": tag_type_label(t)} for t in sorted(TAG_TYPE_LABELS)],
        "alcoholStrength": ALCOHOL_STRENGTH_TAGS,
    }


def write_catalog_tags(it, tags):
    """Replace an item's <tags> children with a controlled list of {key,type}."""
    tags_el = it.find("tags")
    if tags_el is None:
        tags_el = ET.SubElement(it, "tags")
    for child in list(tags_el):
        tags_el.remove(child)
    clean = []
    for tag in tags or []:
        key = _normalize_tag_token(tag.get("key") if isinstance(tag, dict) else tag)
        typ = _normalize_tag_token(tag.get("type") if isinstance(tag, dict) else "")
        if key:
            clean.append({"key": key, "type": typ})
    if not clean:
        tags_el.text = None
        return
    tags_el.text = "\n          "
    for i, tag in enumerate(clean):
        entry = ET.SubElement(tags_el, "item")
        entry.text = "\n            "
        k = ET.SubElement(entry, "key")
        k.text = tag["key"]
        k.tail = "\n            "
        t = ET.SubElement(entry, "type")
        t.text = tag["type"]
        t.tail = "\n          "
        entry.tail = "\n          " if i < len(clean) - 1 else "\n        "



def _catalog_ids():
    root = load_file(CATALOG_FILE)["root"]
    return [(it.get("key") or txt(it, "key")) for it in root.findall("./catalog/items/item")]


def _buyer_catalog_reverse():
    return {f"{joaat(key):08X}": key for key in _catalog_ids() if key}


def _resolve_buyer_token(token, reverse):
    """Resolve runtime PDATA hashes to catalog IDs while retaining unknown hashes."""
    token = str(token).strip().upper()
    if not token.startswith("0X"):
        return token
    raw_hash = token[2:].zfill(8)
    return reverse.get(raw_hash, f"0X{raw_hash}")


def _import_buyer_dump():
    """Import our one-shot runtime vanilla dump without discarding unresolved hashes."""
    if BUYER_STATE_FILE.exists() or not BUYER_DUMP_FILE.exists():
        return
    reverse = _buyer_catalog_reverse()
    buyers = {shop: [] for shop in BUYER_SHOPS}
    for raw in BUYER_DUMP_FILE.read_text(encoding="utf-8-sig").splitlines()[1:]:
        shop, sep, token = raw.partition(",")
        if sep and shop in buyers:
            buyers[shop].append(_resolve_buyer_token(token, reverse))
    BUYER_STATE_FILE.write_text(json.dumps({"source": "runtime vanilla dump", "buyers": buyers}, indent=2) + "\n", encoding="utf-8")


def get_shop_buyers():
    _import_buyer_dump()
    if not BUYER_STATE_FILE.exists():
        return {"available": False, "buyers": {}, "shops": BUYER_SHOPS,
                "reason": "Vanilla buyer baseline will be captured automatically on the next Story Mode startup."}
    data = json.loads(BUYER_STATE_FILE.read_text(encoding="utf-8"))
    reverse = _buyer_catalog_reverse()
    buyers = {shop: [_resolve_buyer_token(value, reverse)
                     for value in data.get("buyers", {}).get(shop, [])]
              for shop in BUYER_SHOPS}
    vanilla_source = data.get("vanillaBuyers", data.get("buyers", {}))
    vanilla = {shop: [_resolve_buyer_token(value, reverse)
                      for value in vanilla_source.get(shop, [])]
               for shop in BUYER_SHOPS}
    overrides = {shop: {str(item).strip().upper(): mode
                        for item, mode in data.get("overrides", {}).get(shop, {}).items()
                        if mode in ("accept", "reject")}
                 for shop in BUYER_SHOPS}
    return {"available": True, "buyers": buyers, "vanillaBuyers": vanilla,
            "overrides": overrides, "shops": BUYER_SHOPS,
            "file": str(BUYER_DATA_FILE), "runtimeFile": str(BUYER_OVERRIDE_FILE)}


def get_shop_acceptance_report():
    """Report only merchant acceptance states that the available data proves.

    Rockstar's buyer PDATA is a sparse exception list, not a complete category
    whitelist. Anything sellable but absent from that list therefore remains
    explicitly unknown instead of being misreported as rejected.
    """
    buyer_data = get_shop_buyers()
    if not buyer_data.get("available"):
        return {"available": False, "shops": BUYER_SHOPS, "summary": {},
                "rows": [], "unresolvedListed": {},
                "reason": buyer_data.get("reason", "No merchant baseline captured yet.")}

    root = load_file(CATALOG_FILE)["root"]
    items = {}
    for item in root.findall("./catalog/items/item"):
        key = (item.get("key") or txt(item, "key")).strip().upper()
        if not key:
            continue
        sellable = any(
            txt(cost, "key") == "SELL_SHOP_DEFAULT" and
            txt(cost, "costtype") == "COST_TYPE_PRICE" and
            any(txt(part, "item") == "CURRENCY_CASH"
                for part in cost.findall("./items/item"))
            for cost in item.findall("./sellprices/item")
        )
        items[key] = sellable

    rows = []
    summary = {}
    unresolved = {}
    for shop in BUYER_SHOPS:
        listed = {str(value).strip().upper()
                  for value in buyer_data["buyers"].get(shop, []) if str(value).strip()}
        overrides = buyer_data["overrides"].get(shop, {})
        unresolved[shop] = sorted(listed - set(items))
        counts = {key: 0 for key in ("EXPLICIT_ACCEPT", "LISTED_NO_PRICE",
                                     "BLOCKED", "UNSELLABLE", "ENGINE_DEFAULT_UNKNOWN")}
        for item, sellable in items.items():
            mode = overrides.get(item, "default")
            if mode == "reject":
                verdict = "BLOCKED"
                source = "merchant_buy_overrides.csv"
            elif item in listed:
                verdict = "EXPLICIT_ACCEPT" if sellable else "LISTED_NO_PRICE"
                source = "merchant buyer PDATA"
            elif not sellable:
                verdict = "UNSELLABLE"
                source = "catalog sellprices"
            else:
                verdict = "ENGINE_DEFAULT_UNKNOWN"
                source = "compiled merchant category rule"
            counts[verdict] += 1
            # The UI renders the complete per-shop counts and only needs row
            # detail for actionable contradictions. Returning every unknown
            # shop/item pair made this small report a 100k-row response.
            if verdict == "LISTED_NO_PRICE":
                rows.append({"shop": shop, "item": item, "verdict": verdict,
                             "source": source})
        summary[shop] = counts
    return {"available": True, "shops": BUYER_SHOPS, "summary": summary,
            "rows": rows, "unresolvedListed": unresolved}


def _buyer_attr(parent, name, value, index, content_type="0x665E1B60"):
    node = ET.SubElement(parent, "item")
    ET.SubElement(node, "name").text = name
    ET.SubElement(node, "valueHash").text = value
    ET.SubElement(node, "contentIndex", {"value": str(index)})
    ET.SubElement(node, "contentType").text = content_type
    ET.SubElement(node, "isEnabled", {"value": "true"})


def _buyer_node(parent, name, parent_i, child_i, sibling_i, previous_i, attr_start, attr_count):
    node = ET.SubElement(parent, "item")
    ET.SubElement(node, "name").text = name
    for tag, value in (("parentIndex", parent_i), ("childIndex", child_i),
                       ("siblingIndex", sibling_i), ("previousSiblingIndex", previous_i),
                       ("attributeStart", attr_start), ("attributeCount", attr_count)):
        ET.SubElement(node, tag, {"value": str(value)})
    ET.SubElement(node, "isEnabled", {"value": "true"})


def write_shop_buyer_data(buyers, vanilla_buyers=None, overrides=None):
    """Write explicit PDATA buyer lists without inventing empty shop overrides."""
    root = ET.Element("UNK_MEMBER_0xDE396FE2")
    attrs = ET.SubElement(root, "attributes")
    _buyer_attr(attrs, "RELEASE", "1", 1, "0x2339EEB0")
    strings = []
    attr_index = 1
    normalized = {}
    for shop in BUYER_SHOPS:
        values = sorted(set(str(v).strip().upper() for v in buyers.get(shop, []) if str(v).strip()))
        normalized[shop] = values
        if not values:
            continue
        strings.extend(values)
        strings.append(shop)
        _buyer_attr(attrs, "SHOPTYPE", shop, len(strings) - 1)
        attr_index += 1
        for value in values:
            _buyer_attr(attrs, "ITEMID", value, strings.index(value))
            attr_index += 1
    store = ET.SubElement(root, "attributeValueStringStore")
    for value in strings:
        ET.SubElement(store, "item").text = value
    ET.SubElement(root, "attributeValueVecStore")
    nodes = ET.SubElement(root, "dataNodes")
    _buyer_node(nodes, "ROOT", 65535, 1, 65535, 65535, 65535, 0)
    active_shops = [shop for shop in BUYER_SHOPS if normalized[shop]]
    first_shop_node = 2 if active_shops else 65535
    _buyer_node(nodes, "SHOPINVENTORIES", 65535, first_shop_node, 65535, 65535, 0, 1)
    node_index = 2
    attribute_start = 1
    shop_nodes = []
    for shop in active_shops:
        item_count = len(normalized[shop])
        shop_nodes.append((node_index, shop, item_count, attribute_start))
        node_index += 1 + item_count
        attribute_start += 1 + item_count
    for pos, (shop_node, shop, item_count, start) in enumerate(shop_nodes):
        child = shop_node + 1 if item_count else 65535
        sibling = shop_nodes[pos + 1][0] if pos + 1 < len(shop_nodes) else 65535
        previous = shop_nodes[pos - 1][0] if pos else 65535
        _buyer_node(nodes, "SHOPSELLABLEITEMS", 1, child, sibling, previous, start, 1)
        for i in range(item_count):
            current = shop_node + 1 + i
            _buyer_node(nodes, "INVITEM", shop_node, 65535,
                        current + 1 if i + 1 < item_count else 65535,
                        current - 1 if i else 65535, start + 1 + i, 1)
    BUYER_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    BUYER_DATA_FILE.write_text('<?xml version="1.0" encoding="utf-8" standalone="no"?>\n' +
                               ET.tostring(root, encoding="unicode") + "\n", encoding="utf-8")
    if vanilla_buyers is None or overrides is None:
        old = json.loads(BUYER_STATE_FILE.read_text(encoding="utf-8")) if BUYER_STATE_FILE.exists() else {}
        vanilla_buyers = old.get("vanillaBuyers", old.get("buyers", normalized))
        overrides = old.get("overrides", {})
    vanilla_normalized = {
        shop: sorted(set(str(v).strip().upper() for v in vanilla_buyers.get(shop, []) if str(v).strip()))
        for shop in BUYER_SHOPS
    }
    override_normalized = {
        shop: {str(item).strip().upper(): mode for item, mode in overrides.get(shop, {}).items()
               if str(item).strip() and mode in ("accept", "reject")}
        for shop in BUYER_SHOPS
    }
    BUYER_STATE_FILE.write_text(json.dumps({"source": "runtime vanilla dump",
        "vanillaBuyers": vanilla_normalized, "buyers": normalized,
        "overrides": override_normalized}, indent=2) + "\n", encoding="utf-8")
    BUYER_OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["shop,item,mode"]
    for shop in BUYER_SHOPS:
        for item, mode in sorted(override_normalized[shop].items()):
            lines.append(f"{shop},{item},{mode}")
    BUYER_OVERRIDE_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    install = EDITABLE_MOD_ROOT / "install.xml"
    if install.exists():
        tree = ET.parse(install); install_root = tree.getroot()
        game_path = "update:/x64/levels/rdr3/script/parseddata/0x0BA63B3D.ymt"
        if not any((node.findtext("GamePath") or "") == game_path for node in install_root.findall(".//FileReplacement")):
            resource = install_root.find("./Resources/Resource")
            replacement = ET.SubElement(resource, "FileReplacement")
            ET.SubElement(replacement, "GamePath").text = game_path
            ET.SubElement(replacement, "FilePath").text = "parseddata/0x0BA63B3D.ymt"
            ET.indent(install_root, space="    ")
            install.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(install_root, encoding="unicode") + "\n", encoding="utf-8")


def apply_shop_buyer_edits(edits):
    current = get_shop_buyers()
    if not current["available"]:
        raise ValueError(current["reason"])
    buyers = current["buyers"]
    vanilla = current["vanillaBuyers"]
    overrides = current["overrides"]
    changed = 0
    for edit in edits:
        shop = edit.get("shop")
        item = str(edit.get("item", "")).strip().upper()
        mode = str(edit.get("mode", "default")).strip().lower()
        if shop not in buyers or not item:
            continue
        if mode not in ("default", "accept", "reject"):
            raise ValueError(f"Invalid merchant override mode: {mode}")
        present = item in buyers[shop]
        desired = item in vanilla[shop] if mode == "default" else mode == "accept"
        prior_mode = overrides[shop].get(item, "default")
        if desired and not present:
            buyers[shop].append(item)
        elif not desired and present:
            buyers[shop].remove(item)
        if mode == "default":
            overrides[shop].pop(item, None)
        else:
            overrides[shop][item] = mode
        if present != desired or prior_mode != mode:
            changed += 1
    if changed:
        write_shop_buyer_data(buyers, vanilla, overrides)
    return changed


def find_catalog_item(root, key):
    for it in root.find("catalog").find("items").findall("item"):
        if (it.get("key") or txt(it, "key")) == key:
            return it
    return None


def create_catalog_item(data):
    """Create an ordinary custom crafting/material item from our minimal
    known-working Gunpowder record, without inheriting its recipes or prices."""
    key = str(data.get("key", "")).strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", key):
        raise ValueError("Item ID must be 3-64 uppercase letters, numbers, or underscores")
    root = load_file(CATALOG_FILE)["root"]
    if find_catalog_item(root, key) is not None:
        raise ValueError(f"Item already exists: {key}")
    template = find_catalog_item(root, "LEX_GUNPOWDER")
    if template is None:
        raise ValueError("LEX_GUNPOWDER template is missing")
    item = copy.deepcopy(template)
    item.set("key", key)
    item.find("key").text = key
    item.find("category").text = str(data.get("category") or "CI_CATEGORY_MATERIALS")
    item.find("group").text = str(data.get("group") or "PROVISION")
    for tag in ("acquirecosts", "sellprices", "effectids"):
        node = item.find(tag)
        if node is not None:
            node.clear()
    mult = item.find("multiplicity")
    if mult is not None:
        for child in list(mult):
            mult.remove(child)
        rule = ET.SubElement(mult, "item")
        ET.SubElement(rule, "quantity", {"value": str(max(1, int(data.get("capacity", 20))))})
        ET.SubElement(rule, "slotid").text = "SLOTID_ANY"
    ui = item.find("ui")
    if ui is None:
        ui = ET.SubElement(item, "ui")
    name_key, description_key = key, key + "_DESC"
    name_node = ui.find("key")
    if name_node is None:
        name_node = ET.SubElement(ui, "key")
    name_node.text = name_key
    desc_node = ui.find("description")
    if desc_node is None:
        desc_node = ET.SubElement(ui, "description")
    desc_node.text = description_key
    root.find("catalog").find("items").append(item)
    save_file(CATALOG_FILE)
    record_custom_catalog_origin("items", key)
    save_localization([
        {"key": name_key, "value": str(data.get("name") or key)},
        {"key": description_key, "value": str(data.get("description") or "")},
    ])
    return {"key": key}


def create_catalog_effect(data):
    """Create a new catalog effect using an engine behavior already present
    in the catalog. New effect records are data; new behaviors require code."""
    requested_key = str(data.get("key", "")).strip().upper()
    if not re.fullmatch(r"(?:0X[0-9A-F]{8}|[A-Z][A-Z0-9_]{2,63})", requested_key):
        raise ValueError("Effect ID must be a symbolic name or an 8-digit 0x hash")
    key = canonical_effect_key(requested_key)
    root = load_file(CATALOG_FILE)["root"]
    effects_root = root.find("effectsids")
    if effects_root is None:
        raise ValueError("catalog_sp.ymt has no effectsids section")
    definitions = effects_root.findall("item")
    if any(canonical_effect_key(txt(effect, "key")) == key for effect in definitions):
        raise ValueError(f"Effect already exists: {key}")
    behavior = str(data.get("behavior", "")).strip()
    known_behaviors = {txt(effect, "id") for effect in definitions if txt(effect, "id")}
    if behavior not in known_behaviors:
        raise ValueError("Behavior ID must be selected from an existing engine behavior")
    duration = str(data.get("durationcategory") or "EFFECT_DURATION_CATEGORY_NONE").strip()
    known_durations = {txt(effect, "durationcategory") for effect in definitions}
    if duration not in known_durations:
        raise ValueError("Duration category must be selected from an existing category")
    effect = ET.Element("item")
    ET.SubElement(effect, "key").text = key
    ET.SubElement(effect, "id").text = behavior
    ET.SubElement(effect, "value", {"value": str(int(float(data.get("value", 0))))})
    ET.SubElement(effect, "percent", {"value": f'{float(data.get("percent", 0)):.8f}'})
    ET.SubElement(effect, "time", {"value": str(int(float(data.get("time", 0))))})
    ET.SubElement(effect, "timeunits", {"value": str(int(float(data.get("timeunits", 0))))})
    ET.SubElement(effect, "durationcategory").text = duration
    effects_root.append(effect)
    ordered = sorted(effects_root.findall("item"),
                     key=lambda item: int(canonical_effect_key(txt(item, "key")), 16))
    for item in list(effects_root):
        effects_root.remove(item)
    for item in ordered:
        effects_root.append(item)
    save_file(CATALOG_FILE)
    record_custom_catalog_origin("effects", key)
    label = str(data.get("label", "")).strip()
    if not requested_key.startswith("0X"):
        save_label("effectSymbols", key, requested_key)
    if label:
        save_label("effects", key, label)
    return {"key": key, "label": label, "symbol": requested_key if not requested_key.startswith("0X") else ""}


def shop_stock_types(root, item_key):
    """Shop types whose <shopsinventories> currently stock this item."""
    out = []
    inv = root.find("shopsinventories")
    if inv is None:
        return out
    for shop in inv.findall("item"):
        stype = txt(shop, "type")
        for entry in shop.findall("./items/item"):
            if txt(entry, "item") == item_key:
                out.append(stype)
                break
    return out


def set_item_shop_stock(root, item_key, stocked):
    """Add or remove an item from every shop that vanilla stocks it in.

    This is the only thing that controls whether an item appears in a shop's
    catalogue. Prices and CI_TAG_SHOP_* tags do not.
    """
    inv = root.find("shopsinventories")
    if inv is None:
        return 0
    changed = 0
    if not stocked:
        for shop in inv.findall("item"):
            items = shop.find("items")
            if items is None:
                continue
            for entry in list(items.findall("item")):
                if txt(entry, "item") == item_key:
                    items.remove(entry)
                    changed += 1
        return changed
    # restoring: re-stock in exactly the shops vanilla used
    vanilla_root = load_file(CATALOG_FILE, "vanilla")["root"]
    wanted = set(shop_stock_types(vanilla_root, item_key))
    if not wanted:
        return 0
    for shop in inv.findall("item"):
        if txt(shop, "type") not in wanted:
            continue
        items = shop.find("items")
        if items is None:
            items = ET.SubElement(shop, "items")
        if any(txt(x, "item") == item_key for x in items.findall("item")):
            continue
        entry = ET.SubElement(items, "item")
        ET.SubElement(entry, "item").text = item_key
        ET.SubElement(entry, "requirementgroups")
        changed += 1
    return changed


def catalog_page_shops(root, item_key):
    """Shop types whose CATALOGUE BOOK prints this item."""
    out = []
    lay = root.find("cataloglayout")
    if lay is None:
        return out
    for shop in lay.findall("item"):
        stype = txt(shop, "shoptype")
        for page in shop.iter("items"):
            if any(txt(x, "key") == item_key for x in page.findall("item")):
                if stype not in out:
                    out.append(stype)
    return out


def _catalogue_key(value):
    return str(value or "").strip().casefold()


def _catalogue_leaf_categories(shop):
    """Return exact leaf-menu paths and their page-reference containers."""
    result = []

    def visit(menus, path=()):
        if menus is None:
            return
        for menu in menus.findall("item"):
            key = txt(menu, "key")
            current = path + (key,)
            nested = menu.findall("./menus/item")
            refs = menu.find("pages")
            if refs is not None and not nested:
                result.append({
                    "key": key,
                    "path": list(current),
                    "menuType": txt(menu, "menutype"),
                    "menuDesc": txt(menu, "menudesc"),
                    "_refs": refs,
                })
            if nested:
                visit(menu.find("menus"), current)

    visit(shop.find("menus"))
    return result


def catalog_page_capacity(layout):
    """Return only a capacity declared by the page layout name."""
    match = re.search(r"(?:GRID_OF_)(\d+)", layout)
    if match:
        return int(match.group(1))
    if "FULLPAGE" in layout:
        return 1
    return None


def _catalogue_page_fact(shop, category, page):
    layout = txt(page, "layout")
    return {
        "shopId": txt(shop, "shopid"),
        "category": category["key"] if category else None,
        "categoryPath": list(category["path"]) if category else [],
        "page": txt(page, "key"),
        "layout": layout,
        "occupancy": len(page.findall("./items/item")),
        "capacity": catalog_page_capacity(layout),
        "reachable": category is not None,
        "generated": txt(page, "key").startswith(("LEX_PAGE_", "LEX_OVERFLOW_")),
    }


def _catalogue_category_fact(shop, category, pages_by_key):
    pages = []
    for ref in category["_refs"].findall("item"):
        page = pages_by_key.get(_catalogue_key(txt(ref, "key")))
        if page is not None:
            pages.append(_catalogue_page_fact(shop, category, page))
    return {
        "shopId": txt(shop, "shopid"),
        "key": category["key"],
        "path": list(category["path"]),
        "menuType": category["menuType"],
        "menuDesc": category["menuDesc"],
        "pages": pages,
    }


def catalogue_listing_metadata(root):
    """Index printed-page facts once for the Shops response."""
    listing_pages = {}
    category_facts = {}
    layouts = root.find("cataloglayout")
    if layouts is None:
        return listing_pages, category_facts
    seen_pages = set()
    seen_categories = set()
    for shop in layouts.findall("item"):
        shop_type = txt(shop, "shoptype")
        pages = list(shop.findall("./pages/item"))
        pages_by_key = {_catalogue_key(txt(page, "key")): page for page in pages}
        categories = _catalogue_leaf_categories(shop)
        refs = {}
        for category in categories:
            fact = _catalogue_category_fact(shop, category, pages_by_key)
            identity = (shop_type, fact["shopId"], tuple(fact["path"]))
            if identity not in seen_categories:
                category_facts.setdefault(shop_type, []).append(fact)
                seen_categories.add(identity)
            for ref in category["_refs"].findall("item"):
                refs.setdefault(_catalogue_key(txt(ref, "key")), []).append(category)
        for page in pages:
            page_categories = refs.get(_catalogue_key(txt(page, "key"))) or [None]
            for category in page_categories:
                fact = _catalogue_page_fact(shop, category, page)
                for entry in page.findall("./items/item"):
                    item_key = txt(entry, "key")
                    identity = (
                        shop_type, item_key, fact["shopId"], fact["category"], fact["page"]
                    )
                    if identity in seen_pages:
                        continue
                    listing_pages.setdefault((shop_type, item_key), []).append(fact)
                    seen_pages.add(identity)
    return listing_pages, category_facts


def catalog_page_templates(root, item_key):
    """Return every reachable same-item page template with its real category."""
    layouts = root.find("cataloglayout")
    if layouts is None:
        return []
    candidates = []
    for shop_order, shop in enumerate(layouts.findall("item")):
        canonical_shop = txt(shop, "shopid") == txt(shop, "shoptype")
        categories = _catalogue_leaf_categories(shop)
        refs = {}
        for category in categories:
            for ref in category["_refs"].findall("item"):
                refs.setdefault(_catalogue_key(txt(ref, "key")), []).append(category)
        for page_order, page in enumerate(shop.findall("./pages/item")):
            page_categories = refs.get(_catalogue_key(txt(page, "key")), [])
            layout = txt(page, "layout")
            if not page_categories or not layout:
                continue
            for entry in page.findall("./items/item"):
                if txt(entry, "key") != item_key:
                    continue
                unlinked = not txt(entry, "linkshopid") and not txt(entry, "linkmenuid")
                generated = txt(page, "key").startswith(("LEX_PAGE_", "LEX_OVERFLOW_"))
                score = (not generated, unlinked, canonical_shop, -shop_order, -page_order)
                for category in page_categories:
                    candidates.append({
                        "layout": layout,
                        "flags": copy.deepcopy(page.find("flags")),
                        "entry": copy.deepcopy(entry),
                        "page": copy.deepcopy(page),
                        "sourceShopId": txt(shop, "shopid"),
                        "sourceShopType": txt(shop, "shoptype"),
                        "sourcePage": txt(page, "key"),
                        "category": category["key"],
                        "categoryPath": list(category["path"]),
                        "_score": score,
                    })
    return sorted(candidates, key=lambda candidate: candidate["_score"], reverse=True)


def catalog_page_template(root, item_key):
    """Return the strongest reachable same-item page template."""
    templates = catalog_page_templates(root, item_key)
    return templates[0] if templates else None


def _catalogue_add_target(root, shop_type):
    layouts = root.find("cataloglayout")
    matching = [shop for shop in layouts.findall("item")
                if txt(shop, "shoptype") == shop_type] if layouts is not None else []
    if not matching:
        return None
    canonical = next((shop for shop in matching if txt(shop, "shopid") == shop_type), None)
    return canonical or max(matching, key=lambda shop: (
        len(shop.findall("./pages/item")), len(shop.findall("./menus/item"))))


def _public_catalogue_plan(plan):
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def catalogue_placement_plan(root, item_key, shop_type, destination_category=None):
    """Resolve a printed-page destination without mutating the catalogue."""
    shop = _catalogue_add_target(root, shop_type)
    categories = _catalogue_leaf_categories(shop) if shop is not None else []
    pages = list(shop.findall("./pages/item")) if shop is not None else []
    pages_by_key = {_catalogue_key(txt(page, "key")): page for page in pages}
    category_facts = [_catalogue_category_fact(shop, category, pages_by_key)
                      for category in categories] if shop is not None else []

    # Stock can be absent while the printed page already exists. That is an
    # already-resolved destination and does not require a category question.
    for category in categories:
        for ref in category["_refs"].findall("item"):
            page = pages_by_key.get(_catalogue_key(txt(ref, "key")))
            if page is None or not any(
                txt(entry, "key") == item_key for entry in page.findall("./items/item")
            ):
                continue
            fact = _catalogue_page_fact(shop, category, page)
            return {
                "item": item_key, "shop": shop_type, "automatic": True,
                "requiresDestination": False, "reason": "",
                "source": None, "destination": {**fact, "newPage": False},
                "categories": category_facts,
                "_targetShop": shop, "_category": category,
                "_template": None, "_page": page,
            }

    templates = catalog_page_templates(root, item_key)
    if not templates:
        raise ValueError(
            f"Cannot add {item_key} to {shop_type}: no reachable catalogue page prints this item"
        )
    if shop is None or not categories:
        return {
            "item": item_key, "shop": shop_type, "automatic": False,
            "requiresDestination": True,
            "reason": f"Cannot add {item_key} to {shop_type}: this shop has no catalogue category",
            "source": None, "destination": None, "categories": category_facts,
            "_targetShop": shop, "_category": None, "_template": None, "_page": None,
        }

    requested = str(destination_category or "").strip()
    chosen_category = None
    chosen_template = None
    automatic = False
    if requested:
        chosen_category = next(
            (category for category in categories
             if _catalogue_key(category["key"]) == _catalogue_key(requested)), None
        )
        if chosen_category is None:
            raise ValueError(
                f"Cannot add {item_key} to {shop_type}: {requested} is not a real catalogue category"
            )
        category_layouts = {
            txt(page, "layout")
            for ref in chosen_category["_refs"].findall("item")
            for page in [pages_by_key.get(_catalogue_key(txt(ref, "key")))]
            if page is not None
        }
        chosen_template = max(
            templates,
            key=lambda template: (template["layout"] in category_layouts, template["_score"]),
        )
    else:
        matches = [
            (template, category)
            for template in templates
            for category in categories
            if _catalogue_key(template["category"]) == _catalogue_key(category["key"])
        ]
        if not matches:
            source = templates[0]
            return {
                "item": item_key, "shop": shop_type, "automatic": False,
                "requiresDestination": True,
                "reason": (
                    f"{shop_type} has no {source['category']} catalogue category; "
                    "select one of this shop's real destinations"
                ),
                "source": {
                    "shopId": source["sourceShopId"], "shopType": source["sourceShopType"],
                    "category": source["category"], "categoryPath": source["categoryPath"],
                    "page": source["sourcePage"], "layout": source["layout"],
                },
                "destination": None, "categories": category_facts,
                "_targetShop": shop, "_category": None,
                "_template": source, "_page": None,
            }
        def automatic_score(match):
            template, category = match
            category_layouts = {
                txt(page, "layout")
                for ref in category["_refs"].findall("item")
                for page in [pages_by_key.get(_catalogue_key(txt(ref, "key")))]
                if page is not None
            }
            return template["layout"] in category_layouts, template["_score"]

        chosen_template, chosen_category = max(matches, key=automatic_score)
        automatic = True

    referenced_pages = [
        pages_by_key.get(_catalogue_key(txt(ref, "key")))
        for ref in chosen_category["_refs"].findall("item")
    ]
    open_pages = []
    for page in referenced_pages:
        if page is None or txt(page, "layout") != chosen_template["layout"]:
            continue
        capacity = catalog_page_capacity(txt(page, "layout"))
        occupancy = len(page.findall("./items/item"))
        if capacity is not None and occupancy < capacity:
            open_pages.append(page)
    page = max(open_pages, default=None, key=lambda value: len(value.findall("./items/item")))
    destination = _catalogue_page_fact(shop, chosen_category, page) if page is not None else {
        "shopId": txt(shop, "shopid"),
        "category": chosen_category["key"],
        "categoryPath": list(chosen_category["path"]),
        "page": None,
        "layout": chosen_template["layout"],
        "occupancy": 0,
        "capacity": catalog_page_capacity(chosen_template["layout"]),
        "reachable": True,
        "generated": True,
    }
    return {
        "item": item_key, "shop": shop_type, "automatic": automatic,
        "requiresDestination": False, "reason": "",
        "source": {
            "shopId": chosen_template["sourceShopId"],
            "shopType": chosen_template["sourceShopType"],
            "category": chosen_template["category"],
            "categoryPath": chosen_template["categoryPath"],
            "page": chosen_template["sourcePage"],
            "layout": chosen_template["layout"],
        },
        "destination": {**destination, "newPage": page is None},
        "categories": category_facts,
        "_targetShop": shop, "_category": chosen_category,
        "_template": chosen_template, "_page": page,
    }


def get_catalogue_placement(item_key, shop_type, destination_category=None):
    plan = catalogue_placement_plan(
        load_file(CATALOG_FILE)["root"], item_key, shop_type, destination_category
    )
    return _public_catalogue_plan(plan)


def catalog_leaf_menu(shop, pages, layout):
    """Compatibility helper: choose a real leaf that already uses a layout."""
    pages_by_key = {_catalogue_key(txt(page, "key")): page for page in pages}
    candidates = []
    for order, category in enumerate(_catalogue_leaf_categories(shop)):
        same_layout = sum(
            page is not None and txt(page, "layout") == layout
            for page in (
                pages_by_key.get(_catalogue_key(txt(ref, "key")))
                for ref in category["_refs"].findall("item")
            )
        )
        candidates.append((same_layout, -order, category["_refs"]))
    return max(candidates, default=(0, 0, None), key=lambda candidate: candidate[:2])[2]


def set_item_in_catalogue(root, item_key, shop_type, present, destination_category=None):
    """Add/remove an item from a shop's printed catalogue pages.

    A shop item needs BOTH a stock entry (<shopsinventories>) and a page
    entry (<cataloglayout>). Stock without a page = invisible and unbuyable.
    Page without stock = printed but 'SOLD OUT' at 0c.
    """
    lay = root.find("cataloglayout")
    if lay is None:
        return 0
    changed = 0
    matching = [shop for shop in lay.findall("item") if txt(shop, "shoptype") == shop_type]
    # Rockstar may retain an empty hashed placeholder beside the real symbolic
    # shop layout. Additions belong in exactly one canonical layout; removals
    # still scan every match so stale entries cannot survive.
    add_target = None
    if present and matching:
        add_target = next((shop for shop in matching if txt(shop, "shopid") == shop_type), None)
        if add_target is None:
            add_target = max(matching, key=lambda shop: (
                len(shop.findall("./pages/item")), len(shop.findall("./menus/item"))))
    for shop in matching:
        if present and shop is not add_target:
            continue
        pages_root = shop.find("pages")
        if pages_root is None:
            continue
        pages = list(pages_root.findall("item"))
        if not present:
            for page in list(pages):
                items = page.find("items")
                if items is None:
                    continue
                for entry in list(items.findall("item")):
                    if txt(entry, "key") == item_key:
                        items.remove(entry)
                        changed += 1
                if len(items.findall("item")) == 0:
                    page_key = txt(page, "key")
                    pages_root.remove(page)
                    changed += 1
                    for refs in shop.findall("./menus//pages"):
                        for ref in list(refs.findall("item")):
                            if txt(ref, "key") == page_key:
                                refs.remove(ref)
                                changed += 1
        else:
            if any(txt(entry, "key") == item_key for page in pages for entry in page.findall("./items/item")):
                continue
            plan = catalogue_placement_plan(root, item_key, shop_type, destination_category)
            if plan["requiresDestination"]:
                raise ValueError(plan["reason"])
            template = plan["_template"]
            page = plan["_page"]
            if page is None:
                page = copy.deepcopy(template["page"])
                used_keys = {_catalogue_key(txt(candidate, "key")) for candidate in pages}
                salt = 0
                while True:
                    identity = f"{shop_type}:{plan['_category']['key']}:{item_key}:{salt}"
                    page_key = f"LEX_PAGE_{joaat(identity):08X}"
                    if _catalogue_key(page_key) not in used_keys:
                        break
                    salt += 1
                key_node = page.find("key")
                if key_node is None:
                    raise ValueError(f"Cannot add {item_key} to {shop_type}: source page has no key")
                key_node.text = page_key
                items = page.find("items")
                if items is None:
                    raise ValueError(f"Cannot add {item_key} to {shop_type}: source page has no items container")
                for existing_entry in list(items.findall("item")):
                    items.remove(existing_entry)
                pages_root.append(page)
                ref = ET.SubElement(plan["_category"]["_refs"], "item")
                ET.SubElement(ref, "key").text = page_key
                changed += 1
            items = page.find("items")
            items.append(copy.deepcopy(template["entry"]))
            changed += 1
    return changed


def set_item_shop_presence(root, item_key, shop_type, present, destination_category=None):
    """Stock AND print an item in one shop - the complete operation."""
    # Validate and create the printed page before adding stock. A page-template
    # failure must not leave an in-memory stock row that a later save can leak.
    page_changed = set_item_in_catalogue(
        root, item_key, shop_type, True, destination_category
    ) if present else 0
    inv = root.find("shopsinventories")
    stock_changed = 0
    if inv is not None:
        for shop in inv.findall("item"):
            if txt(shop, "type") != shop_type:
                continue
            items = shop.find("items")
            if items is None:
                items = ET.SubElement(shop, "items")
            existing = [x for x in items.findall("item") if txt(x, "item") == item_key]
            if present and not existing:
                entry = ET.SubElement(items, "item")
                ET.SubElement(entry, "item").text = item_key
                ET.SubElement(entry, "requirementgroups")
                stock_changed += 1
            elif not present:
                for x in existing:
                    items.remove(x)
                    stock_changed += 1
    if not present:
        page_changed = set_item_in_catalogue(root, item_key, shop_type, False)
    return {"stock": stock_changed, "catalogue": page_changed}


def apply_catalog_edits(edits):
    """edits: {prices: [{item, section, costKey, partItem, qty}],
              yields: [{item, section, costKey, qty}],
              effects: [{key, field, value}],
              itemEffects: [{item, effects: [keys]}],
              itemTags: [{item, tags: [{key, type}]}],
              descriptions: [{item, key}],
              quickSelect: [{item, slots: [{id, sortOrder}]}]}"""
    root = load_file(CATALOG_FILE)["root"]
    # Allowed tag pairs = observed tags from this mod + vanilla/kiddos references
    # + curated alcohol-strength options. New free-typed hashes are rejected.
    allowed_tag_pairs = set()
    for ds_name in ("mine", "vanilla", "kiddos"):
        try:
            ds_root = root if ds_name == "mine" else load_file(CATALOG_FILE, ds_name)["root"]
        except Exception:
            continue
        catalog_items = ds_root.find("catalog")
        catalog_items = catalog_items.find("items") if catalog_items is not None else None
        for it in catalog_items.findall("item") if catalog_items is not None else []:
            for tag in parse_catalog_tags(it.find("tags")):
                allowed_tag_pairs.add((tag["key"], tag["type"]))
    for row in ALCOHOL_STRENGTH_TAGS:
        allowed_tag_pairs.add((_normalize_tag_token(row["key"]), _normalize_tag_token(row["type"])))
    changed = 0
    for e in edits.get("buyability", []):
        present = bool(e.get("buyable"))
        shop_types = set(shop_stock_types(root, e["item"]))
        shop_types.update(catalog_page_shops(root, e["item"]))
        if present:
            vanilla_root = load_file(CATALOG_FILE, "vanilla")["root"]
            shop_types.update(shop_stock_types(vanilla_root, e["item"]))
            shop_types.update(catalog_page_shops(vanilla_root, e["item"]))
        for shop_type in shop_types:
            result = set_item_shop_presence(root, e["item"], shop_type, present)
            changed += result["stock"] + result["catalogue"]
    for e in edits.get("sellability", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        section = it.find("sellprices")
        if section is None:
            section = ET.SubElement(it, "sellprices")
        for cost in list(section.findall("item")):
            if txt(cost, "costtype") == "COST_TYPE_PRICE" and any(txt(p, "item") == "CURRENCY_CASH" for p in cost.findall("./items/item")):
                section.remove(cost)
        if e.get("sellable"):
            cost = ET.SubElement(section, "item")
            ET.SubElement(cost, "key").text = "SELL_SHOP_DEFAULT"
            ET.SubElement(cost, "quantity", {"value": "1"})
            ET.SubElement(cost, "costtype").text = "COST_TYPE_PRICE"
            items = ET.SubElement(cost, "items"); part = ET.SubElement(items, "item")
            ET.SubElement(part, "item").text = "CURRENCY_CASH"
            ET.SubElement(part, "quantity", {"value": str(max(0, int(e.get("cents", 100))))})
            ET.SubElement(cost, "unlocks")
        changed += 1
    for e in edits.get("prices", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        section = it.find("acquirecosts" if e["section"] == "buy" else "sellprices")
        if section is None:
            continue
        for cost in section.findall("item"):
            if txt(cost, "key") != e["costKey"]:
                continue
            items_el = cost.find("items")
            if items_el is None:
                continue
            for part in items_el.findall("item"):
                if txt(part, "item") == e["partItem"]:
                    q = part.find("quantity")
                    if q is not None:
                        q.set("value", str(int(e["qty"])))
                        changed += 1
    for e in edits.get("yields", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        section = it.find("acquirecosts" if e["section"] == "buy" else "sellprices")
        if section is None:
            continue
        for cost in section.findall("item"):
            if txt(cost, "key") == e["costKey"]:
                quantity = cost.find("quantity")
                if quantity is not None:
                    quantity.set("value", str(max(1, int(e["qty"]))))
                    changed += 1
    known_effect_behaviors = {txt(item, "id") for item in root.find("effectsids").findall("item") if txt(item, "id")}
    for e in edits.get("effects", []):
        for eff in root.find("effectsids").findall("item"):
            if txt(eff, "key") == e["key"]:
                field = e["field"]
                if field in ("value", "percent", "time", "timeunits"):
                    el = eff.find(field)
                    if el is not None:
                        raw = e["value"]
                        if field in ("value", "time", "timeunits"):
                            raw = str(int(float(raw)))
                        else:
                            raw = str(float(raw))
                        el.set("value", raw)
                        changed += 1
                elif field == "durationcategory":
                    el = eff.find(field)
                    if el is not None:
                        el.text = str(e["value"])
                        changed += 1
                elif field == "id":
                    value = str(e["value"]).strip()
                    if value not in known_effect_behaviors:
                        raise ValueError("Behavior ID must be selected from an existing engine behavior")
                    el = eff.find("id")
                    if el is not None:
                        el.text = value
                        changed += 1
    effects_root = root.find("effectsids")
    if effects_root is not None:
        definitions = list(effects_root.findall("item"))
        ordered = sorted(definitions, key=lambda item: int(canonical_effect_key(txt(item, "key")), 16))
        if definitions != ordered:
            for item in definitions:
                effects_root.remove(item)
            for index, item in enumerate(ordered):
                item.tail = "\n    " if index < len(ordered) - 1 else "\n  "
                effects_root.append(item)
            changed += 1
    # Container purchase output is owned by its item-group loot entry, not by
    # the catalog purchase record. Save it from the same editor transaction so
    # the Items cell edits what it displays.
    bundle_files = set()
    for e in edits.get("bundles", []):
        try:
            name, table_key, item_key = e["key"].split("|", 2)
            qty = str(max(1, int(e["qty"])))
        except (KeyError, TypeError, ValueError):
            raise ValueError("invalid bundle-output edit")
        if name not in LOOT_FILES:
            raise ValueError(f"unknown bundle loot file: {name}")
        loot_root = load_file(name)["root"]
        found = False
        for table in loot_root.find("LootTables").findall("Item"):
            if table.get("key") != table_key:
                continue
            entries = table.find("Entries")
            for entry in entries.findall("Item") if entries is not None else []:
                if txt(entry, "Name") != item_key:
                    continue
                for field in ("Min", "Max"):
                    node = entry.find(field)
                    if node is None:
                        node = ET.SubElement(entry, field)
                    node.set("value", qty)
                found = True
                changed += 1
        if not found:
            raise ValueError(f"bundle entry not found: {table_key}/{item_key}")
        bundle_files.add(name)
    for e in edits.get("craft", []):
        # full replace of an item's CRAFTING cost entries (shop prices untouched)
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        ac = it.find("acquirecosts")
        if ac is None:
            ac = ET.SubElement(it, "acquirecosts")
            ac.text = "\n        "
            ac.tail = "\n        "
        for cost in list(ac.findall("item")):
            if txt(cost, "costtype") == "COST_TYPE_CRAFT" or "CRAFT" in txt(cost, "key"):
                ac.remove(cost)
        entries = []
        for incoming in e.get("entries", []):
            entry = dict(incoming)
            if entry.get("key") in {"COST_CRAFTING_TRAPPER", "COST_CRAFTING_FENCE"}:
                entry["key"] = "COST_CRAFTING"
                entry["parts"] = [part for part in entry.get("parts", [])
                                  if part.get("item") != "CURRENCY_CASH"]
            entries.append(entry)
        if len(ac.findall("item")) == 0 and not entries:
            ac.text = None
        for i, entry in enumerate(entries):
            cost = ET.SubElement(ac, "item")
            cost.text = "\n            "
            k = ET.SubElement(cost, "key"); k.text = entry.get("key") or "COST_CRAFTING_FIRE"
            k.tail = "\n            "
            q = ET.SubElement(cost, "quantity"); q.set("value", str(int(entry.get("yield", 1))))
            q.tail = "\n            "
            ct = ET.SubElement(cost, "costtype"); ct.text = "COST_TYPE_CRAFT"
            ct.tail = "\n            "
            items_el = ET.SubElement(cost, "items")
            items_el.text = "\n              "
            parts = [p for p in entry.get("parts", []) if p.get("item")]
            for j, p in enumerate(parts):
                part = ET.SubElement(items_el, "item")
                part.text = "\n                "
                pi = ET.SubElement(part, "item"); pi.text = p["item"]
                pi.tail = "\n                "
                pq = ET.SubElement(part, "quantity"); pq.set("value", str(int(p.get("qty", 1))))
                pq.tail = "\n              "
                part.tail = "\n              " if j < len(parts) - 1 else "\n            "
            items_el.tail = "\n            "
            un = ET.SubElement(cost, "unlocks")
            unlocks = [u for u in entry.get("unlocks", []) if u]
            if unlocks:
                un.text = "\n              "
                for j, key in enumerate(unlocks):
                    unlock = ET.SubElement(un, "item")
                    unlock.text = "\n                "
                    uk = ET.SubElement(unlock, "key"); uk.text = key
                    uk.tail = "\n              "
                    unlock.tail = "\n              " if j < len(unlocks) - 1 else "\n            "
            un.tail = "\n          "
            cost.tail = "\n          " if i < len(entries) - 1 else "\n        "
        changed += 1
    for e in edits.get("carry", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        mult_el = it.find("multiplicity")
        if mult_el is None:
            mult_el = ET.SubElement(it, "multiplicity")
        found = False
        for m in mult_el.findall("item"):
            if txt(m, "slotid") == e["slot"]:
                q = m.find("quantity")
                if q is not None:
                    q.set("value", str(int(e["qty"])))
                    changed += 1
                    found = True
        if not found:
            m = ET.SubElement(mult_el, "item")
            q = ET.SubElement(m, "quantity")
            q.set("value", str(int(e["qty"])))
            slot = ET.SubElement(m, "slotid")
            slot.text = e["slot"]
            changed += 1
    for e in edits.get("itemEffects", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        eff_el = it.find("effectids")
        if eff_el is None:
            continue
        for child in list(eff_el):
            eff_el.remove(child)
        if e["effects"]:
            eff_el.text = "\n          "
            for i, key in enumerate(e["effects"]):
                entry = ET.SubElement(eff_el, "item")
                entry.text = "\n            "
                k = ET.SubElement(entry, "key")
                k.text = key
                k.tail = "\n          "
                entry.tail = "\n          " if i < len(e["effects"]) - 1 else "\n        "
        else:
            eff_el.text = None
        changed += 1
    for e in edits.get("itemTags", []):
        it = find_catalog_item(root, e["item"])
        if it is None:
            continue
        incoming = []
        for tag in e.get("tags") or []:
            key = _normalize_tag_token(tag.get("key") if isinstance(tag, dict) else tag)
            typ = _normalize_tag_token(tag.get("type") if isinstance(tag, dict) else "")
            if not key:
                continue
            # Symbolic CI_TAG_* names may be introduced when their type matches a
            # known family already used by that same key elsewhere, or any type
            # already observed for a symbolic key in the allowed set.
            if (key, typ) not in allowed_tag_pairs:
                if key.startswith("CI_TAG_") and any(k == key for k, _ in allowed_tag_pairs):
                    # reuse the majority/known type for this symbolic key
                    typ = next(t for k, t in allowed_tag_pairs if k == key)
                elif key.startswith("CI_TAG_") and typ in TAG_TYPE_LABELS:
                    allowed_tag_pairs.add((key, typ))
                else:
                    raise ValueError(
                        f"Refusing free-entry catalog tag {key} ({typ or 'no type'}). "
                        "Pick a known named tag or an alcohol-strength option."
                    )
            incoming.append({"key": key, "type": typ})
        # De-dupe while preserving order
        seen = set()
        unique = []
        for tag in incoming:
            id_ = (tag["key"], tag["type"])
            if id_ in seen:
                continue
            seen.add(id_)
            unique.append(tag)
        write_catalog_tags(it, unique)
        changed += 1
    for e in edits.get("descriptions", []):
        it = find_catalog_item(root, e["item"])
        key = str(e.get("key", "")).strip()
        if it is None or not key:
            continue
        ui = it.find("ui")
        if ui is None:
            ui = ET.SubElement(it, "ui")
        description = ui.find("description")
        if description is None:
            description = ET.SubElement(ui, "description")
        if (description.text or "").strip() != key:
            description.text = key
            changed += 1
    if changed:
        save_file(CATALOG_FILE)
        for name in bundle_files:
            save_file(name)
    return changed + apply_quick_select_edits(edits.get("quickSelect", []))


# ---------------- loot tables ----------------

ENTRY_FIELDS = ["Name", "Rate", "Type", "Min", "Max", "RewardCondition"]
VALUE_FIELDS = {"Rate", "Min", "Max"}  # stored as value="" attributes


def get_loot(name, ds="mine"):
    root = load_file(name, ds)["root"]
    tables = []
    for t in root.find("LootTables").findall("Item"):
        entries = []
        entries_el = t.find("Entries")
        if entries_el is not None:
            for en in entries_el.findall("Item"):
                row = {}
                for f in ENTRY_FIELDS:
                    if f in VALUE_FIELDS:
                        v = attr_value(en, f)
                        if v is not None:
                            row[f.lower()] = v
                    elif f == "RewardCondition":
                        condition = en.find(f)
                        v = condition.get("ref", "") if condition is not None else ""
                        if v:
                            row[f.lower()] = v
                    else:
                        v = txt(en, f)
                        if v:
                            row[f.lower()] = v
                entries.append(row)
        tables.append({
            "key": t.get("key", ""),
            "name": t.get("name", ""),
            "type": txt(t, "Type"),
            "entries": entries,
        })
    return {"tables": tables}


def apply_loot_edits(name, edits):
    """edits: [{tableKey, entries: [{name, rate, type, min, max, rewardcondition}]}]
    Rebuilds the <Entries> block of each edited table."""
    valid_items = {item["key"] for item in get_catalog()["items"]}
    valid_tables = {table["key"] for file in LOOT_FILES if (ds_dir("mine") / file).exists()
                    for table in get_loot(file)["tables"]}
    valid_conditions = {entry.get("rewardcondition") for file in LOOT_FILES if (ds_dir("mine") / file).exists()
                        for table in get_loot(file)["tables"] for entry in table["entries"]
                        if entry.get("rewardcondition")}
    catalog_entry_types = {"Item", "Collectible", "Money", "Ammo", "Horse", "Weapon"}
    for edit in edits:
        for row in edit.get("entries", []):
            row_type = row.get("type") or "Item"
            if row_type == "Table":
                valid_names = valid_tables
            elif row_type in catalog_entry_types:
                valid_names = valid_items
            else:
                raise ValueError(f"invalid loot entry type: {row_type}")
            if row.get("name") not in valid_names:
                raise ValueError(f"unknown loot {row_type.lower()} identifier: {row.get('name')}")
            if row.get("rewardcondition") and row["rewardcondition"] not in valid_conditions:
                raise ValueError(f"unknown loot condition: {row['rewardcondition']}")
    root = load_file(name)["root"]
    changed = 0
    for e in edits:
        for t in root.find("LootTables").findall("Item"):
            if t.get("key") != e["tableKey"]:
                continue
            entries_el = t.find("Entries")
            if entries_el is None:
                entries_el = ET.SubElement(t, "Entries")
            for child in list(entries_el):
                entries_el.remove(child)
            entries_el.text = "\n        "
            rows = e["entries"]
            for i, row in enumerate(rows):
                en = ET.SubElement(entries_el, "Item")
                en.text = "\n          "
                last = None
                for f in ENTRY_FIELDS:
                    v = row.get(f.lower())
                    if v is None or v == "":
                        continue
                    el = ET.SubElement(en, f)
                    if f in VALUE_FIELDS:
                        el.set("value", str(v))
                    elif f == "RewardCondition":
                        el.set("ref", str(v))
                    else:
                        el.text = str(v)
                    el.tail = "\n          "
                    last = el
                if last is not None:
                    last.tail = "\n        "
                en.tail = "\n        " if i < len(rows) - 1 else "\n      "
            entries_el.tail = "\n    "
            changed += 1
    if changed:
        save_file(name)
    return changed


def _normalize_loot_table_key(raw):
    key = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw or "").strip().upper())
    key = re.sub(r"_+", "_", key).strip("_")
    if not key:
        raise ValueError("table key is empty")
    if not re.match(r"^[A-Z]", key):
        key = "LEX_" + key
    return key


def create_loot_table(name, data):
    """Append a new empty loot table (item group or other) to a loot file."""
    if name not in LOOT_FILES:
        raise ValueError(f"unknown loot file: {name}")
    key = _normalize_loot_table_key(data.get("key", ""))
    display = (data.get("name") or key.replace("_", " ")).strip()
    table_type = (data.get("type") or "AggregateDrop").strip()
    if table_type not in {"AggregateDrop", "ContinuousLinearDrop"}:
        raise ValueError("type must be AggregateDrop or ContinuousLinearDrop")
    root = load_file(name)["root"]
    container = root.find("LootTables")
    if container is None:
        raise ValueError("LootTables root missing")
    existing = {t.get("key", "") for t in container.findall("Item")}
    if key in existing:
        raise ValueError(f"table key already exists: {key}")
    item = ET.SubElement(container, "Item")
    item.set("key", key)
    item.set("name", display)
    item.text = "\n      "
    type_el = ET.SubElement(item, "Type")
    type_el.text = table_type
    type_el.tail = "\n      "
    entries = ET.SubElement(item, "Entries")
    entries.text = "\n      "
    entries.tail = "\n    "
    item.tail = "\n    "
    # Keep a blank line style similar to Rockstar exports
    save_file(name)
    return {"key": key, "name": display, "type": table_type, "entries": []}


def delete_loot_table(name, key):
    """Remove a loot table if no other table references it as a Table entry."""
    if name not in LOOT_FILES:
        raise ValueError(f"unknown loot file: {name}")
    key = str(key or "").strip()
    if not key:
        raise ValueError("table key is empty")
    # Refuse delete while any loot file still points at this table.
    refs = []
    for file in LOOT_FILES:
        if not (ds_dir("mine") / file).exists():
            continue
        for table in get_loot(file)["tables"]:
            if table["key"] == key:
                continue
            for entry in table["entries"]:
                if entry.get("type") == "Table" and entry.get("name") == key:
                    refs.append(f"{file}:{table['key']}")
    if refs:
        raise ValueError(
            f"cannot delete {key}: still referenced as a Table entry by "
            + ", ".join(refs[:8])
            + ("…" if len(refs) > 8 else "")
        )
    root = load_file(name)["root"]
    container = root.find("LootTables")
    if container is None:
        raise ValueError("LootTables root missing")
    target = next((t for t in container.findall("Item") if t.get("key") == key), None)
    if target is None:
        raise ValueError(f"table not found: {key}")
    container.remove(target)
    save_file(name)
    return 1


# ---------------- loot matrix ----------------

def get_matrix(ds="mine"):
    root = load_file(MATRIX_FILE, ds)["root"]
    animals = []
    for a in root.find("Entries").findall("Item"):
        rows = []
        items_el = a.find("Items")
        if items_el is not None:
            for r in items_el.findall("Item"):
                rows.append({
                    "damage": txt(r, "DamageQuality"),
                    "skin": txt(r, "SkinQuality"),
                    "item": txt(r, "SatchelItem"),
                    "qty": attr_value(r, "Quantity"),
                })
        animals.append({"key": a.get("key", ""), "rows": rows})
    return {"animals": animals}


def apply_matrix_edits(edits):
    """edits: [{animalKey, rows: [{damage, skin, item, qty}]}]"""
    root = load_file(MATRIX_FILE)["root"]
    changed = 0
    for e in edits:
        for a in root.find("Entries").findall("Item"):
            if a.get("key") != e["animalKey"]:
                continue
            items_el = a.find("Items")
            if items_el is None:
                items_el = ET.SubElement(a, "Items")
            for child in list(items_el):
                items_el.remove(child)
            items_el.text = "\n        "
            rows = e["rows"]
            for i, row in enumerate(rows):
                r = ET.SubElement(items_el, "Item")
                r.text = "\n          "
                parts = [("DamageQuality", row.get("damage")), ("SkinQuality", row.get("skin")),
                         ("SatchelItem", row.get("item"))]
                els = []
                for tag, v in parts:
                    if not v:
                        continue
                    el = ET.SubElement(r, tag)
                    el.text = str(v)
                    el.tail = "\n          "
                    els.append(el)
                if row.get("qty") not in (None, ""):
                    el = ET.SubElement(r, "Quantity")
                    el.set("value", str(row["qty"]))
                    el.tail = "\n          "
                    els.append(el)
                if els:
                    els[-1].tail = "\n        "
                r.tail = "\n        " if i < len(rows) - 1 else "\n      "
            items_el.tail = "\n    "
            changed += 1
    if changed:
        save_file(MATRIX_FILE)
    return changed


# ---------------- challenge goals ----------------

CHALLENGE_SPLIT_RE = re.compile(r"^(SP_CHAL_.+_ROOT)_(\d+)$")


def challenge_groups(challenges_el):
    """Return logical strands, collapsing the one-root-per-rank parallel form."""
    groups = {}
    order = []
    for challenge in challenges_el.findall("Item"):
        name = txt(challenge, "name")
        match = CHALLENGE_SPLIT_RE.match(name)
        logical = match.group(1) if match else name
        if logical not in groups:
            groups[logical] = []
            order.append(logical)
        groups[logical].append((int(match.group(2)) if match else 0, challenge))
    return [(logical, sorted(groups[logical], key=lambda row: row[0])) for logical in order]

def get_challenges(ds="mine"):
    """Expose editable goal mechanics without pretending the schema is flat.

    A goal can contain sums and reset clauses, so each desiredGoal is returned
    as a separately indexed requirement with the nearest stat sources beneath
    the same score-param node.
    """
    root = load_file(GOALS_FILE, ds)["root"]
    challenge_root = load_file(CHALLENGES_FILE, ds)["root"]
    rank_map = {}
    strands = []
    allowed_rewards = set()
    for challenge_name, records in challenge_groups(challenge_root.find("challenges")):
        mode = "parallel" if records and all(rank_number > 0 for rank_number, _ in records) else "series"
        challenge = records[0][1]
        short = challenge_name.replace("SP_CHAL_", "").replace("_ROOT", "")
        challenge_ui = challenge.find("uiInfo")
        ranks = []
        rank_records = []
        for split_rank, record in records:
            record_ranks = record.findall("./ranks/Item")
            for local_rank, rank in enumerate(record_ranks, 1):
                rank_records.append((split_rank or local_rank, record, local_rank, rank))
        for rank_index, record, local_rank, rank in sorted(rank_records, key=lambda row: row[0]):
            goal_names = [((x.text or "").strip()) for x in rank.findall("./goalHashes/Item") if (x.text or "").strip()]
            rewards = []
            for reward in rank.findall("./reward/rewards/Item"):
                reward_type = reward.get("type", "")
                value = txt(reward, "unlock") or txt(reward, "rewardType")
                if value:
                    rewards.append({"type": reward_type, "value": value})
                    allowed_rewards.add((reward_type, value))
            rank_ui = rank.find("uiInfo")
            rank_info = {"rank": rank_index, "goals": goal_names, "rewards": rewards,
                         "owner": txt(record, "name"), "ownerRank": local_rank,
                         "nameLabel": txt(rank_ui, "challengeNameLabel") if rank_ui is not None else "",
                         "descriptionLabel": txt(rank_ui, "rankDescLabel") if rank_ui is not None else "",
                         "toastLabel": txt(rank_ui, "toastRankCompleteDescriptionLabel") if rank_ui is not None else ""}
            ranks.append(rank_info)
            for goal_name in goal_names:
                rank_map[goal_name] = {"strand": short, "rank": rank_index,
                                       "challenge": challenge_name, "rewards": rewards}
        strands.append({"key": short, "name": challenge_name, "mode": mode, "ranks": ranks,
                        "nameLabel": txt(challenge_ui, "challengeNameLabel") if challenge_ui is not None else "",
                        "descriptionLabel": txt(challenge_ui, "challengeDescLabel") if challenge_ui is not None else "",
                        "toolTipLabel": txt(challenge_ui, "toolTip") if challenge_ui is not None else ""})
    goals = []
    for goal in root.find("goals").findall("Item"):
        parent_map = {child: parent for parent in goal.iter() for child in parent}
        requirements = []
        for index, desired in enumerate(goal.iter("desiredGoal")):
            parent = next((p for p in goal.iter() if desired in list(p)), None)
            wrapper = parent_map.get(parent)
            behavior = txt(wrapper, "behavior") if wrapper is not None else ""
            role = "target"
            if parent is not None and parent.tag == "bindParam":
                role = "exclusion" if behavior == "CHECK_FOR_SCORE_WHEN_BIND_NOT_PROGRESS" else "condition"
            elif parent is not None and parent.tag == "resetParam":
                role = "reset"
            sources = []
            if parent is not None:
                for stat in parent.iter("statId"):
                    base = txt(stat, "BaseId")
                    permutation = txt(stat, "PermutationId")
                    if base or permutation:
                        sources.append({"base": base, "permutation": permutation})
            requirements.append({
                "index": index,
                "value": desired.get("value", ""),
                "compare": txt(parent, "compareType") if parent is not None else "",
                "role": role,
                "behavior": behavior,
                "sources": sources,
            })
        ui = goal.find("uiInfo")
        goal_name = txt(goal, "name")
        placement = rank_map.get(goal_name, {})
        conditions = []
        for node in goal.iter():
            condition_type = node.get("type", "")
            if not condition_type.startswith("CAICondition"):
                continue
            fields = {}
            for child in list(node):
                if len(child) == 0:
                    value = (child.text or "").strip() or child.get("value", "")
                    if value:
                        fields[child.tag] = value
            conditions.append({"index": len(conditions), "type": condition_type, "fields": fields})
        goals.append({
            "name": goal_name,
            "type": goal.get("type", ""),
            "description": txt(ui, "pauseMenuDescriptionLabel") if ui is not None else "",
            "descriptionFormat": txt(ui, "pauseMenuDescriptionFormatLabel") if ui is not None else "",
            "toastDescription": txt(ui, "toastDescriptionLabel") if ui is not None else "",
            "requirements": requirements,
            "conditions": conditions,
            "strand": placement.get("strand", "OTHER"),
            "rank": placement.get("rank", 0),
            "rewards": placement.get("rewards", []),
        })
    source_pairs = {(s["base"], s["permutation"]): {"base": s["base"], "permutation": s["permutation"],
                    "label": ""} for g in goals for r in g["requirements"] for s in r["sources"]
                    if s["base"] or s["permutation"]}
    for source in KNOWN_CHALLENGE_SOURCE_PAIRS:
        source_pairs[(source["base"], source["permutation"])] = dict(source)
    allowed_source_pairs = sorted(source_pairs.values(),
                                  key=lambda s: (s.get("label") or s["base"] or s["permutation"]))
    condition_values = {}
    for goal in goals:
        for condition in goal["conditions"]:
            for field, value in condition["fields"].items():
                condition_values.setdefault((condition["type"], field), set()).add(value)
    allowed_condition_values = [
        {"type": condition_type, "field": field, "values": sorted(values)}
        for (condition_type, field), values in sorted(condition_values.items())
    ]
    return {"goals": goals, "strands": strands, "allowedSourcePairs": allowed_source_pairs,
            "allowedRewards": [{"type": t, "value": v} for t, v in sorted(allowed_rewards)],
            "allowedConditionValues": allowed_condition_values}


def apply_challenge_edits(edits, reward_edits=None, ui_edits=None, condition_edits=None, mode_edits=None):
    vanilla = get_challenges("vanilla")
    allowed_sources = {(s.get("base", ""), s.get("permutation", ""))
                       for s in vanilla["allowedSourcePairs"]}
    allowed_rewards = {(r["type"], r["value"]) for r in vanilla["allowedRewards"]}
    allowed_conditions = {(row["type"], row["field"]): set(row["values"])
                          for row in vanilla["allowedConditionValues"]}
    for edit in edits:
        for source in edit.get("sources", []):
            if source.get("remove"):
                continue
            value = (source.get("base", ""), source.get("permutation", ""))
            if value not in allowed_sources:
                raise ValueError(f"unknown challenge score source: {value[0]} + {value[1]}")
    for edit in reward_edits or []:
        for reward in edit.get("rewards", []):
            if "CHALLENGE_REWARD_TYPE_MONEY_" in reward.get("value", ""):
                raise ValueError("MyOverhaul challenge money rewards are disabled")
            if (reward.get("type"), reward.get("value")) not in allowed_rewards:
                raise ValueError(f"unknown challenge reward: {reward.get('value')}")
    for edit in condition_edits or []:
        key = (edit.get("type", ""), edit.get("field", ""))
        if edit.get("value", "") not in allowed_conditions.get(key, set()):
            raise ValueError(f"unknown challenge condition value: {key[0]}.{key[1]}={edit.get('value')}")
    root = load_file(GOALS_FILE)["root"]
    by_name = {txt(g, "name"): g for g in root.find("goals").findall("Item")}
    changed = 0
    for edit in edits:
        goal = by_name.get(edit.get("name"))
        if goal is None:
            continue
        desired = list(goal.iter("desiredGoal"))
        index = int(edit.get("index", -1))
        if 0 <= index < len(desired):
            desired[index].set("value", str(edit.get("value", "")))
            changed += 1
            parent = next((p for p in goal.iter() if desired[index] in list(p)), None)
            stat_ids = list(parent.iter("statId")) if parent is not None else []
            remove_indices = []
            for source_edit in edit.get("sources", []):
                source_index = int(source_edit.get("index", -1))
                if not (0 <= source_index < len(stat_ids)):
                    continue
                if source_edit.get("remove"):
                    remove_indices.append(source_index)
                    continue
                stat = stat_ids[source_index]
                base = stat.find("BaseId")
                permutation = stat.find("PermutationId")
                if base is None:
                    base = ET.SubElement(stat, "BaseId")
                base.text = source_edit.get("base") or None
                if permutation is None and source_edit.get("permutation"):
                    permutation = ET.SubElement(stat, "PermutationId")
                if permutation is not None:
                    permutation.text = source_edit.get("permutation") or None
                changed += 1
            if remove_indices:
                # A summed requirement stores each counter in an Item directly
                # beneath scoreParams. Remove that whole branch, not just statId.
                parent_map = {child: node for node in parent.iter() for child in node}
                for source_index in sorted(set(remove_indices), reverse=True):
                    node = stat_ids[source_index]
                    while node in parent_map and parent_map[node].tag != "scoreParams":
                        node = parent_map[node]
                    container = parent_map.get(node)
                    if container is not None and container.tag == "scoreParams" and len(container) > 1:
                        container.remove(node)
                        changed += 1
    if changed:
        save_file(GOALS_FILE)
    condition_changed = 0
    for edit in condition_edits or []:
        goal = by_name.get(edit.get("goal"))
        if goal is None:
            continue
        nodes = [node for node in goal.iter()
                 if node.get("type", "").startswith("CAICondition")]
        index = int(edit.get("index", -1))
        if not (0 <= index < len(nodes)) or nodes[index].get("type") != edit.get("type"):
            continue
        field = nodes[index].find(edit.get("field", ""))
        if field is None:
            continue
        if "value" in field.attrib:
            field.set("value", str(edit.get("value", "")))
        else:
            field.text = str(edit.get("value", ""))
        condition_changed += 1
    if condition_changed:
        save_file(GOALS_FILE)
    reward_changed = 0
    if reward_edits:
        challenges = load_file(CHALLENGES_FILE)["root"]
        by_name = {txt(c, "name"): c for c in challenges.find("challenges").findall("Item")}
        for edit in reward_edits:
            challenge = by_name.get(edit.get("owner") or edit.get("challenge"))
            ranks_el = challenge.find("ranks") if challenge is not None else None
            ranks = ranks_el.findall("Item") if ranks_el is not None else []
            rank_index = int(edit.get("ownerRank") or edit.get("rank", 0)) - 1
            if not (0 <= rank_index < len(ranks)):
                continue
            rewards_el = ranks[rank_index].find("./reward/rewards")
            if rewards_el is None:
                continue
            for child in list(rewards_el):
                rewards_el.remove(child)
            rewards_el.text = "\n              "
            rows = edit.get("rewards", [])
            for i, row in enumerate(rows):
                item = ET.SubElement(rewards_el, "Item"); item.set("type", row["type"])
                item.text = "\n                "
                tag = "unlock" if row["type"] == "CUnlockReward" else "rewardType"
                value = ET.SubElement(item, tag); value.text = row["value"]
                value.tail = "\n              "; item.tail = "\n              " if i < len(rows)-1 else "\n            "
            reward_changed += 1
        if reward_changed:
            save_file(CHALLENGES_FILE)
    ui_changed = 0
    for edit in ui_edits or []:
        file_name, owner, field, value = edit.get("file"), edit.get("owner"), edit.get("field"), edit.get("value", "")
        root = load_file(file_name)["root"] if file_name in {GOALS_FILE, CHALLENGES_FILE} else None
        if root is None:
            continue
        collection = root.find("goals") if file_name == GOALS_FILE else root.find("challenges")
        record = next((x for x in collection.findall("Item") if txt(x, "name") == owner), None)
        if record is None:
            continue
        target = record.find("uiInfo")
        rank = int(edit.get("rank", 0))
        if rank and file_name == CHALLENGES_FILE:
            ranks = record.findall("./ranks/Item")
            target = ranks[rank - 1].find("uiInfo") if 0 < rank <= len(ranks) else None
        node = target.find(field) if target is not None else None
        if node is not None:
            node.text = value
            ui_changed += 1
    if ui_changed:
        if any(e.get("file") == GOALS_FILE for e in ui_edits or []): save_file(GOALS_FILE)
        if any(e.get("file") == CHALLENGES_FILE for e in ui_edits or []): save_file(CHALLENGES_FILE)
    mode_changed = 0
    if mode_edits:
        challenge_doc = load_file(CHALLENGES_FILE)["root"]
        challenges_el = challenge_doc.find("challenges")
        for edit in mode_edits:
            logical = edit.get("challenge", "")
            requested = edit.get("mode", "")
            if requested not in {"series", "parallel"}:
                raise ValueError(f"unknown challenge strand mode: {requested}")
            if requested == "parallel":
                raise ValueError("Parallel roots appear as duplicate challenge strands in game and are not supported")
            group = next((records for name, records in challenge_groups(challenges_el) if name == logical), None)
            if not group:
                continue
            is_parallel = all(number > 0 for number, _ in group)
            if requested == "parallel" and not is_parallel:
                source = group[0][1]
                source_ranks = source.findall("./ranks/Item")
                if len(source_ranks) < 2:
                    continue
                insert_at = list(challenges_el).index(source)
                challenges_el.remove(source)
                for rank_number, source_rank in enumerate(source_ranks, 1):
                    clone = copy.deepcopy(source)
                    clone.find("name").text = f"{logical}_{rank_number}"
                    clone_ranks = clone.find("ranks")
                    for child in list(clone_ranks):
                        clone_ranks.remove(child)
                    clone_ranks.append(copy.deepcopy(source_rank))
                    challenges_el.insert(insert_at + rank_number - 1, clone)
                mode_changed += 1
            elif requested == "series" and is_parallel:
                insert_at = min(list(challenges_el).index(record) for _, record in group)
                merged = copy.deepcopy(group[0][1])
                merged.find("name").text = logical
                merged_ranks = merged.find("ranks")
                for child in list(merged_ranks):
                    merged_ranks.remove(child)
                for _, record in group:
                    for rank in record.findall("./ranks/Item"):
                        merged_ranks.append(copy.deepcopy(rank))
                    challenges_el.remove(record)
                challenges_el.insert(insert_at, merged)
                mode_changed += 1
        if mode_changed:
            save_file(CHALLENGES_FILE)
    return changed + condition_changed + reward_changed + ui_changed + mode_changed


# ---------------- crime information ----------------

# scalar fields directly under CrimeInformation (value="" attributes)
CRIME_CI_FIELDS = ["CrimeValue", "PunishingCrimeValue", "ImmediateDetectionRange",
                   "Timeout", "MinTimeBeforeNotifyLawEnforcement",
                   "MinWantedLevelSP", "ForcedWantedLevelIncreaseSP", "Disabled"]
CRIME_WIT_FIELDS = ["NumWitnesses", "NumInvestigators", "NumLawInvestigators"]
CRIME_SEVERITIES = {"None", "Low", "Medium", "High"}


def _sp_variation(crime):
    """The SP variation of a crime (fallback: first variation)."""
    var_el = crime.find("Variations")
    if var_el is None:
        return None
    items = var_el.findall("Item")
    for v in items:
        if "SP" in (v.findtext("FilterFlags") or ""):
            return v
    return items[0] if items else None


def get_crime(ds="mine"):
    root = load_file(CRIME_FILE, ds)["root"]
    out = []
    for crime in root.find("CrimeInformations").findall("Item"):
        var = _sp_variation(crime)
        ci = var.find("CrimeInformation") if var is not None else None
        if ci is None:
            continue
        row = {"key": crime.get("key", ""), "severity": (ci.findtext("Severity") or "").strip()}
        for f in CRIME_CI_FIELDS:
            row[f] = attr_value(ci, f)
        wit = ci.find("WitnessInformation")
        for f in CRIME_WIT_FIELDS:
            row[f] = attr_value(wit, f) if wit is not None else None
        conf = ci.find("Confrontation")
        row["ConfrontChance"] = attr_value(conf, "Chances") if conf is not None else None
        out.append(row)
    return {"crimes": out, "fields": CRIME_CI_FIELDS + CRIME_WIT_FIELDS + ["ConfrontChance", "severity"]}


def apply_crime_edits(edits):
    """edits: [{key, field, value}] — applied to the SP variation."""
    root = load_file(CRIME_FILE)["root"]
    changed = 0
    for crime in root.find("CrimeInformations").findall("Item"):
        my = [e for e in edits if e["key"] == crime.get("key")]
        if not my:
            continue
        var = _sp_variation(crime)
        ci = var.find("CrimeInformation") if var is not None else None
        if ci is None:
            continue
        for e in my:
            f, v = e["field"], str(e["value"])
            if f == "severity":
                if v not in CRIME_SEVERITIES:
                    raise ValueError(f"invalid crime severity: {v}")
                el = ci.find("Severity")
                if el is not None:
                    el.text = v
                    changed += 1
            elif f == "ConfrontChance":
                conf = ci.find("Confrontation")
                el = conf.find("Chances") if conf is not None else None
                if el is not None:
                    el.set("value", v)
                    changed += 1
            elif f in CRIME_WIT_FIELDS:
                wit = ci.find("WitnessInformation")
                el = wit.find(f) if wit is not None else None
                if el is not None:
                    el.set("value", v)
                    changed += 1
            elif f in CRIME_CI_FIELDS:
                el = ci.find(f)
                if el is not None:
                    el.set("value", v)
                    changed += 1
    if changed:
        save_file(CRIME_FILE)
    return changed


# ---------------- dispatch (law response tuning) ----------------

DISPATCH_SCALARS = ["ParoleDuration", "ImmediateDetectionRange", "OnScreenImmediateDetectionRange"]
DISPATCH_GROUPS = ["SinglePlayerWantedLevelThresholds", "SingleplayerWantedLevelRadius",
                   "HiddenEvasionTimes", "CopsToPreserveAroundPlayer",
                   "LawSpawnDelayMin", "LawSpawnDelayMax"]
WANTED_INCIDENT_GROUP = "WantedIncidentEvasion"


def _bounty_incident_evasion(root):
    """Return CBountyIncident/Evasion without relying on its list position."""
    for item in root.findall("./Tunables/Item"):
        if (item.findtext("Name") or "").strip() == "CBountyIncident":
            return item.find("Evasion")
    return None


def get_dispatch(ds="mine"):
    root = load_file(DISPATCH_FILE, ds)["root"]
    rows = []
    for s in DISPATCH_SCALARS:
        el = root.find(s)
        if el is not None:
            rows.append({"group": "", "field": s, "value": el.get("value")})
    for g in DISPATCH_GROUPS:
        el = root.find(g)
        if el is not None:
            for c in el:
                if isinstance(c.tag, str) and c.get("value") is not None:
                    rows.append({"group": g, "field": c.tag, "value": c.get("value")})
    # Story Mode does not use dispatch.meta's zero-filled HiddenEvasionTimes
    # table for the visible pursuit/search countdown.  That setting lives in
    # CBountyIncident's tuning file and is kept in this response so the editor
    # can present the complete wanted loop in one place.
    incidents_path = ds_dir(ds) / INCIDENTS_FILE
    if incidents_path.exists():
        evasion = _bounty_incident_evasion(load_file(INCIDENTS_FILE, ds)["root"])
        escape = evasion.find("TimeEvadingForEscape") if evasion is not None else None
        if escape is not None and escape.get("value") is not None:
            rows.append({"group": WANTED_INCIDENT_GROUP,
                         "field": "TimeEvadingForEscape",
                         "value": escape.get("value")})
    return {"rows": rows}


def get_bounty_hunters(ds="mine"):
    response = ds_dir(ds) / BOUNTY_HUNTERS_FILE
    dispatch = ds_dir(ds) / DISPATCH_FILE
    if not response.exists() or not dispatch.exists():
        return {"available": False, "responseFile": str(response), "dispatchFile": str(dispatch)}
    return _ensure_bounty_hunter_metadata(_read_bounty_hunters(response, dispatch))


def apply_bounty_hunter_edits(edits):
    return _apply_bounty_hunter_edits(ds_dir("mine") / BOUNTY_HUNTERS_FILE,
                                      ds_dir("mine") / DISPATCH_FILE, edits)


def apply_dispatch_edits(edits):
    """edits: [{group, field, value}] (group '' = top-level scalar)"""
    root = load_file(DISPATCH_FILE)["root"]
    changed = dispatch_changed = incident_changed = 0
    for e in edits:
        if e["group"] == WANTED_INCIDENT_GROUP:
            if e["field"] != "TimeEvadingForEscape":
                continue
            incident_root = load_file(INCIDENTS_FILE)["root"]
            evasion = _bounty_incident_evasion(incident_root)
            el = evasion.find(e["field"]) if evasion is not None else None
            if el is not None and el.get("value") is not None:
                el.set("value", str(e["value"]))
                changed += 1
                incident_changed += 1
            continue
        parent = root if not e["group"] else root.find(e["group"])
        el = parent.find(e["field"]) if parent is not None else None
        if el is not None and el.get("value") is not None:
            el.set("value", str(e["value"]))
            changed += 1
            dispatch_changed += 1
    if dispatch_changed:
        save_file(DISPATCH_FILE)
    if incident_changed:
        save_file(INCIDENTS_FILE)
    return changed


# ---------------- researched data map ----------------

def get_data_map():
    text = DATA_MAP_FILE.read_text(encoding="utf-8")
    sections = []
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = {"title": line[3:].strip(), "lines": []}
            sections.append(current)
        elif current is not None:
            current["lines"].append(line)
    result = _build_data_map(DATA_MAP_FILE)
    result["sections"] = sections
    return result


def _scalar_descendants(node, prefix=""):
    out = []
    for child in node:
        if not isinstance(child.tag, str):
            continue
        path = f"{prefix}/{child.tag}" if prefix else child.tag
        value = child.get("value")
        if value is not None:
            out.append({"field": path, "value": value})
        elif len(child) == 0 and child.text and child.text.strip():
            out.append({"field": path, "value": child.text.strip()})
        else:
            out.extend(_scalar_descendants(child, path))
    return out


def _weapon_rows(item):
    """Flatten a weapon record to editable rows.

    Repeated list elements are all literally <Item>, so a bow's twelve damage
    modes used to produce twelve rows called "DamageModes/Item/Damage" with
    nothing to tell them apart. Anything keyed on the field name then collapsed
    them onto the LAST one, which is why every reference column read as the
    wound arrow. Label each list element with its own Name instead.
    """
    rows = []
    def label_of(child, index, siblings):
        if child.tag != "Item":
            return child.tag
        name = (child.findtext("Name") or "").strip()
        if name and sum(1 for s in siblings
                        if s.tag == "Item"
                        and (s.findtext("Name") or "").strip() == name) == 1:
            return name
        return f"Item {index + 1}" if sum(
            1 for s in siblings if s.tag == "Item") > 1 else "Item"
    def walk(node, path, tags):
        siblings = list(node)
        for index, child in enumerate(siblings):
            if not isinstance(child.tag, str):
                continue
            child_path = path + [index]
            child_tags = tags + [label_of(child, index, siblings)]
            value = child.get("value")
            kind = "attr"
            if value is None and len(child) == 0 and child.text and child.text.strip():
                value = child.text.strip(); kind = "text"
            if value is not None:
                rows.append({"path": child_path, "field": "/".join(child_tags),
                             "value": value, "kind": kind})
            elif len(child):
                walk(child, child_path, child_tags)
    walk(item, [], [])
    return rows


def _path_to(root, target):
    def walk(node, path):
        if node is target:
            return path
        for index, child in enumerate(list(node)):
            found = walk(child, path + [index])
            if found is not None:
                return found
        return None
    return walk(root, [])


def _linked_ammo_rows(root, ammo_name):
    """Ammo performance lives in per-weapon DamageInfos, not CAmmoInfo alone."""
    rows = []
    for weapon in root.iter("Item"):
        if weapon.get("type") != "CWeaponInfo":
            continue
        weapon_name = txt(weapon, "Name")
        for variant in weapon.iter("Item"):
            if txt(variant, "AmmoInfo") != ammo_name:
                continue
            base_path = _path_to(weapon, variant)
            for row in _weapon_rows(variant):
                if row["field"] == "AmmoInfo":
                    continue
                row.update({"path": base_path + row["path"], "targetType": "CWeaponInfo",
                            "targetName": weapon_name, "linked": True,
                            "field": f"{weapon_name} / Performance / {row['field']}"})
                rows.append(row)
            for tag, label in (("DamageFallOffInfo", "Range curve"),
                               ("AccuracyInfo", "Accuracy curve")):
                ref = txt(variant, tag)
                if not ref:
                    continue
                shared = next((item for item in root.iter("Item")
                               if txt(item, "Name") == ref), None)
                if shared is None:
                    continue
                record_type = shared.get("type")
                point_counts = {"Distance": 0, "Damage": 0}
                for row in _weapon_rows(shared):
                    if row["field"] == "Name":
                        continue
                    leaf = row["field"].rsplit("/", 1)[-1]
                    display_field = row["field"]
                    if label == "Range curve" and leaf in point_counts:
                        point_counts[leaf] += 1
                        display_field = f"Point {point_counts[leaf]} / {leaf}"
                    row.update({"targetType": record_type, "targetName": ref, "linked": True,
                                "field": f"{weapon_name} / {label} / {display_field}"})
                    rows.append(row)
    return rows


def _weapon_records(root, source_file=WEAPONS_FILE, rdo_names=None):
    records = {"weapons": [], "ammo": []}
    types = {"CWeaponInfo": "weapons", "CAmmoInfo": "ammo"}
    rdo_names = rdo_names or {"weapons": set(), "ammo": set()}
    for item in root.iter("Item"):
        section = types.get(item.get("type"))
        name = txt(item, "Name")
        if section and name:
            records[section].append({
                "name": name,
                "fields": _weapon_rows(item),
                "sourceFile": source_file,
                "rdoAdded": name in rdo_names.get(section, set()),
            })
    for record in records["ammo"]:
        record["fields"].extend(_linked_ammo_rows(root, record["name"]))
    return records


def _weapon_flag_token_key(token):
    """Normalize mixed readable/hash/unknown-bit flag syntax without losing bits."""
    match = re.fullmatch(r"\{BITSET,UNKNOWN_BIT_INDEX:(\d+)\}", token)
    if match:
        return ("bit", int(match.group(1)))
    if token.lower().startswith("0x"):
        return ("hash", int(token, 16))
    # Weapon schema enum hashes are case-sensitive; the general joaat() helper
    # intentionally lowercases and must not be used here.
    value = 0
    for byte in token.encode("utf-8"):
        value = (value + byte) & 0xFFFFFFFF
        value = (value + (value << 10)) & 0xFFFFFFFF
        value ^= value >> 6
    value = (value + (value << 3)) & 0xFFFFFFFF
    value ^= value >> 11
    value = (value + (value << 15)) & 0xFFFFFFFF
    return ("hash", value)


def _projectile_flags_by_ammo(root):
    fields = {}
    for item in root.iter("Item"):
        # Projectile/thrown ammo use CAmmoProjectileInfo and CAmmoThrownInfo,
        # not the CAmmoInfo base type used by ordinary firearm cartridges.
        if not (item.get("type") or "").startswith("CAmmo"):
            continue
        name = txt(item, "Name")
        node = item.find(".//ProjectileFlags")
        if name and node is not None:
            fields[name] = {
                _weapon_flag_token_key(token)
                for token in (node.text or "").split()
            }
    return fields


def _assert_weapon_projectile_flags(root, vanilla_root):
    """Refuse serialization if a vanilla projectile bit disappeared (#199)."""
    current = _projectile_flags_by_ammo(root)
    vanilla = _projectile_flags_by_ammo(vanilla_root)
    missing = [
        name for name, flags in vanilla.items()
        if name not in current or not flags.issubset(current[name])
    ]
    if missing:
        raise ValueError(
            "refusing weapons.ymt save: vanilla ProjectileFlags are missing "
            "from " + ", ".join(missing)
        )


def _weapon_shell_nodes(root):
    nodes = {}
    for item in root.iter("Item"):
        if item.get("type") != "CWeaponInfo":
            continue
        name = txt(item, "Name")
        shell = item.find(".//VfxWeaponShellInfoHashName")
        if name and shell is not None:
            nodes[name] = shell
    return nodes


def _weapon_shell_status(root, vanilla_root):
    current = _weapon_shell_nodes(root)
    vanilla = _weapon_shell_nodes(vanilla_root)
    targets = {name: node for name, node in vanilla.items() if (node.text or "").strip()}
    blank = sum(1 for name in targets
                if name in current and not (current[name].text or "").strip())
    return {"available": bool(targets), "blank": blank, "total": len(targets),
            "blanked": bool(targets) and blank == len(targets),
            "mixed": 0 < blank < len(targets)}


def _set_weapon_shell_vfx(root, vanilla_root, blanked):
    current = _weapon_shell_nodes(root)
    vanilla = _weapon_shell_nodes(vanilla_root)
    changed = 0
    for name, vanilla_node in vanilla.items():
        vanilla_value = (vanilla_node.text or "").strip()
        node = current.get(name)
        if node is None or not vanilla_value:
            continue
        value = "" if blanked else vanilla_value
        if (node.text or "").strip() != value:
            node.text = value or None
            changed += 1
    return changed


def _rdo_weapon_names():
    data = _origin_provenance_data()
    if not data:
        return {"weapons": set(), "ammo": set()}
    return {
        "weapons": set(data.get("weapons", [])) | set(data.get("weaponHashes", [])),
        "ammo": set(data.get("ammo", [])) | set(data.get("ammoHashes", [])),
    }


def weapon_layer_files(ds="mine"):
    if ds == "vanilla":
        # The prepared Vanilla dataset contains Rockstar's effective base file
        # plus all six active per-weapon overrides. Reading only weapons.ymt
        # hides the later definitions and does not represent the installed
        # game stack.
        layers = [relative for _, relative in WEAPON_STACK
                  if relative.casefold().endswith(".ymt")]
        return layers if all((ds_dir(ds) / relative).is_file()
                             for relative in layers) else []
    if ds != "mine":
        return [WEAPONS_FILE]
    files = []
    for game_path, relative in install_replacements().items():
        normalized = relative.replace("\\", "/")
        filename = Path(normalized).name.casefold()
        if ("/data/ai/" not in game_path.replace("\\", "/")
                or not filename.startswith("weapon") or not filename.endswith(".ymt")):
            continue
        if _safe_mod_path(normalized).is_file() and normalized not in files:
            files.append(normalized)
    if WEAPONS_FILE not in files and (ds_dir(ds) / WEAPONS_FILE).is_file():
        files.insert(0, WEAPONS_FILE)
    return files


def get_weapons(ds="mine"):
    layers = weapon_layer_files(ds)
    if not layers:
        return {"available": False, "weapons": [], "ammo": [], "file": WEAPONS_FILE}
    rdo_names = _rdo_weapon_names() if ds == "mine" else {"weapons": set(), "ammo": set()}
    records = {"weapons": {}, "ammo": {}}
    for source_file in layers:
        parsed = _weapon_records(load_file(source_file, ds)["root"], source_file, rdo_names)
        for section in records:
            for record in parsed[section]:
                records[section][record["name"]] = record
    root = load_file(WEAPONS_FILE, ds)["root"]
    result = {"available": True,
              "file": f"{len(layers)} active weapon file{'s' if len(layers) != 1 else ''}",
              "files": layers,
              "weapons": list(records["weapons"].values()),
              "ammo": list(records["ammo"].values())}
    vanilla_path = ds_dir("vanilla") / WEAPONS_FILE
    if vanilla_path.exists():
        result["shellVfx"] = _weapon_shell_status(
            root, load_file(WEAPONS_FILE, "vanilla")["root"])
    else:
        result["shellVfx"] = {"available": False, "blank": 0, "total": 0,
                              "blanked": False, "mixed": False}
    return result


def get_weapon_reference():
    path = WEAPON_REF_DIR / WEAPONS_FILE
    if not path.exists():
        return {"available": False, "weapons": [], "ammo": [], "file": WEAPONS_FILE}
    raw = path.read_text(encoding="utf-8-sig")
    root = ET.fromstring(raw[raw.index("<?xml"):])
    return {"available": True, "file": WEAPONS_FILE,
            **_weapon_records(root), "reference": "Realistic Weapon Rebalance 3.2"}


def _projectile_speed_base():
    settings = get_gameplay_settings()
    for section in settings.get("sections", []):
        if section["name"] == "ProjectileSpeed":
            for setting in section["settings"]:
                if setting["key"] == "GlobalFirearmSpeed":
                    return float(setting["value"])
    raise ValueError("GameplayTweaks.ini is missing ProjectileSpeed/GlobalFirearmSpeed")


def get_projectile_speeds(ds="mine"):
    if not (ds_dir(ds) / WEAPONS_FILE).exists():
        return {"available": False, "cartridges": [], "mappings": []}
    root = load_file(WEAPONS_FILE, ds)["root"]
    mappings = _cartridge_mapping(root)
    ammo_names = sorted({row["ammo"] for row in mappings})
    # Reference datasets show coherent defaults; only mine reads editable CSV.
    values = _load_speed_multipliers(PROJECTILE_SPEED_FILE, ammo_names) if ds == "mine" else _load_speed_multipliers(Path("__missing__"), ammo_names)
    base = _projectile_speed_base() if ds == "mine" else None
    by_ammo = {ammo: [] for ammo in ammo_names}
    for row in mappings:
        by_ammo[row["ammo"]].append({key: row[key] for key in ("weapon", "damageMode", "fireType")})
    return {
        "available": True,
        "file": str(PROJECTILE_SPEED_FILE),
        "baseSpeed": base,
        "runtimeSwitching": False,
        "runtimeStatus": "RDR2 stores Speed once per weapon. The editor persists real cartridge mappings and multipliers, but the ASI runtime switch is not installed yet.",
        "mappings": mappings,
        "cartridges": [
            {"ammo": ammo, "multiplier": values[ammo],
             "effectiveSpeed": base * values[ammo] if base is not None else None,
             "uses": by_ammo[ammo]}
            for ammo in ammo_names
        ],
    }


def save_projectile_speeds(entries):
    # Do not persist controls which have no player-visible effect. The issue
    # requires a real per-cartridge runtime switch, and CWeaponInfo currently
    # exposes only one restart-time Speed value per weapon.
    raise ValueError("per-cartridge projectile speed runtime switch is not installed")


def _save_projectile_speed_rows(entries):
    """Validated serializer retained for the runtime-switch implementation."""
    root = load_file(WEAPONS_FILE)["root"]
    mappings = _cartridge_mapping(root)
    ammo_names = sorted({row["ammo"] for row in mappings})
    supplied = {}
    for entry in entries:
        ammo = str(entry.get("ammo", "")).strip()
        if ammo not in ammo_names:
            raise ValueError(f"unknown ammunition {ammo!r}")
        if ammo in supplied:
            raise ValueError(f"duplicate ammunition {ammo}")
        try:
            value = float(entry.get("multiplier"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{ammo}: multiplier must be numeric") from exc
        if not 0.05 <= value <= 10.0:
            raise ValueError(f"{ammo}: multiplier must be 0.05..10")
        supplied[ammo] = value
    if set(supplied) != set(ammo_names):
        missing = sorted(set(ammo_names) - set(supplied))
        raise ValueError("missing cartridge multiplier(s): " + ", ".join(missing))
    PROJECTILE_SPEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROJECTILE_SPEED_FILE.write_text(
        _serialize_speed_multipliers(supplied, ammo_names), encoding="utf-8")
    return len(supplied)


def apply_weapon_edits(section, name, edits, source_file=WEAPONS_FILE):
    types = {"weapons": "CWeaponInfo", "ammo": "CAmmoInfo"}
    if section not in types:
        raise ValueError("unknown weapon section")
    if source_file not in weapon_layer_files("mine"):
        raise ValueError("weapon source is not an active install.xml layer")
    root = load_file(source_file)["root"]
    record = next((item for item in root.iter("Item")
                   if item.get("type") == types[section] and txt(item, "Name") == name), None)
    if record is None:
        raise ValueError("unknown weapon/ammo record")
    changed = 0
    for edit in edits:
        target_type = edit.get("targetType") or types[section]
        target_name = edit.get("targetName") or name
        target = record if target_type == types[section] and target_name == name else next(
            (item for item in root.iter("Item")
             if item.get("type") == target_type and txt(item, "Name") == target_name), None)
        if target is None:
            continue
        node = target
        try:
            for index in edit["path"]:
                node = list(node)[int(index)]
        except (IndexError, TypeError, ValueError):
            continue
        if edit.get("kind") == "attr" and node.get("value") is not None:
            node.set("value", str(edit["value"])); changed += 1
        elif edit.get("kind") == "text" and len(node) == 0:
            node.text = str(edit["value"]); changed += 1
    if changed:
        save_file(source_file)
        if source_file == WEAPONS_FILE:
            ensure_file_replacement(WEAPONS_GAME_PATH, WEAPONS_FILE)
    return changed


def apply_weapon_shell_vfx(blanked):
    """Blank (or restore) each weapon's vanilla shell-ejection VFX.

    2026-07-20: weapons data is a STACK (see WEAPON_STACK). Loading a lone
    base weapons.ymt reverts Rockstar's own weapon patches - the repeater
    double-fire / lantern / off-hand-holster regressions were the game's
    pre-patch state, not file corruption. Serialization was never the
    problem. Until every stack file has been extracted from the archives,
    activating any weapons replacement is refused outright.
    """
    missing = missing_weapon_stack_files()
    if missing:
        raise ValueError(
            "Weapons edits ship the complete %d-file stack; missing extracted "
            "files: %s. The bundled extractor cannot convert Rockstar's PSIN "
            "weapon YMT resources to editable XML."
            % (len(WEAPON_STACK), ", ".join(missing)))
    root = load_file(WEAPONS_FILE)["root"]
    vanilla_root = load_file(WEAPONS_FILE, "vanilla")["root"]
    changed = _set_weapon_shell_vfx(root, vanilla_root, blanked)
    if changed:
        save_file(WEAPONS_FILE)
    # the whole stack must be mapped so patch layers stay applied
    for game_path, local in WEAPON_STACK:
        ensure_file_replacement(game_path, local)
    return changed


def _ai_scalar_rows(root):
    rows = []
    def walk(node, path, tags, context):
        next_context = context
        name = node.find("Name") if isinstance(node.tag, str) else None
        if name is not None and name.text and name.text.strip():
            next_context = name.text.strip()
        elif isinstance(node.tag, str) and node.get("key"):
            next_context = node.get("key")
        for index, child in enumerate(list(node)):
            if not isinstance(child.tag, str):
                continue
            child_path = path + [index]
            child_tags = tags + [child.tag]
            value = child.get("value")
            kind = "attr"
            if value is None and len(child) == 0 and child.text and child.text.strip():
                value = child.text.strip(); kind = "text"
            if value is not None:
                rows.append({"path": child_path, "field": "/".join(child_tags),
                             "context": next_context, "value": value, "kind": kind})
            elif len(child):
                walk(child, child_path, child_tags, next_context)
    walk(root, [], [], "GLOBAL")
    return rows


def get_ai_file(name, ds="mine"):
    allowed = {f for files in AI_FILES.values() for f in files}
    if name not in allowed:
        raise ValueError("unknown AI file")
    path = ds_dir(ds) / name
    if name == PED_PERCEPTION_FILE and not path.exists():
        if not VANILLA_PED_PERCEPTION_FILE.exists():
            return {"file": name, "fields": [], "available": False}
        root = ET.parse(VANILLA_PED_PERCEPTION_FILE).getroot()
        return {"file": name, "fields": _ai_scalar_rows(root),
                "available": True, "source": "vanilla extract"}
    return {"file": name, "fields": _ai_scalar_rows(load_file(name, ds)["root"]),
            "available": True}


def get_ai_reference(name):
    if name == PED_PERCEPTION_FILE and VANILLA_PED_PERCEPTION_FILE.exists():
        root = ET.parse(VANILLA_PED_PERCEPTION_FILE).getroot()
        return {"file": name, "fields": _ai_scalar_rows(root), "available": True,
                "reference": "Vanilla"}
    path = UCO_REF_DIR / Path(name).name
    if not path.exists():
        return {"file": name, "fields": [], "available": False}
    root = ET.parse(path).getroot()
    return {"file": name, "fields": _ai_scalar_rows(root), "available": True,
            "reference": "Ultimate Combat Overhaul 1.0.7"}


def apply_ai_edits(name, edits):
    allowed = {f for files in AI_FILES.values() for f in files}
    if name not in allowed:
        raise ValueError("unknown AI file")
    path = ds_dir("mine") / name
    if name == PED_PERCEPTION_FILE and not path.exists():
        if not VANILLA_PED_PERCEPTION_FILE.exists():
            raise ValueError("vanilla pedperception.meta extract is missing")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(VANILLA_PED_PERCEPTION_FILE, path)
    root = load_file(name)["root"]
    changed = 0
    for edit in edits:
        node = root
        try:
            for index in edit["path"]:
                node = list(node)[int(index)]
        except (IndexError, TypeError, ValueError):
            continue
        if edit.get("kind") == "attr" and node.get("value") is not None:
            node.set("value", str(edit["value"])); changed += 1
        elif edit.get("kind") == "text" and len(node) == 0:
            node.text = str(edit["value"]); changed += 1
    if changed:
        save_file(name)
        if name == PED_PERCEPTION_FILE:
            ensure_file_replacement(PED_PERCEPTION_GAME_PATH, name)
    return changed


# ---------------- mobs (#190) ----------------

def parse_with_comments(path):
    """Parse keeping comments, so child indices match load_file's tree.

    load_file inserts comment nodes. A plain ET.parse drops them, which shifts
    every positional index path by one per preceding comment and would make a
    later save write to the wrong node.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(path.read_text(encoding="utf-8-sig"), parser=parser)


def _mob_group(name):
    upper = (name or "").upper()
    if any(hint in upper for hint in MOB_ANIMAL_HINTS):
        return "animals"
    if any(hint in upper for hint in MOB_HUMAN_HINTS):
        return "humans"
    return "other"


def _record_fields(item, base_path):
    """Flatten one record's scalars, keeping an index path for writing back."""
    fields = []

    def walk(node, path, tags):
        for index, child in enumerate(list(node)):
            if not isinstance(child.tag, str):
                continue
            child_path = path + [index]
            name = "/".join(tags + [child.tag])
            if child.get("value") is not None:
                fields.append({"path": child_path, "kind": "attr",
                               "field": name, "value": child.get("value")})
            elif child.get("ref") is not None:
                fields.append({"path": child_path, "kind": "ref",
                               "field": name, "value": child.get("ref")})
            elif len(child):
                walk(child, child_path, tags + [child.tag])
            else:
                fields.append({"path": child_path, "kind": "text",
                               "field": name, "value": (child.text or "").strip()})

    walk(item, base_path, [])
    return fields


def _combat_records(root):
    """CCombatInfo profiles from combatbehaviour.meta."""
    records = []
    for section_index, section in enumerate(list(root)):
        if not isinstance(section.tag, str) or section.tag != "CombatInfos":
            continue
        for item_index, item in enumerate(list(section)):
            if not isinstance(item.tag, str) or item.tag != "Item":
                continue
            name = txt(item, "Name")
            records.append({"name": name, "group": _mob_group(name),
                            "fields": _record_fields(item, [section_index, item_index])})
    return records


def _pedhealth_records(root):
    """Health/stamina/energy archetypes from pedhealth.meta."""
    records = []
    for section_index, section in enumerate(list(root)):
        if not isinstance(section.tag, str) or section.tag not in PEDHEALTH_SECTIONS:
            continue
        for item_index, item in enumerate(list(section)):
            if not isinstance(item.tag, str) or item.tag != "Item":
                continue
            key = item.get("key", "")
            records.append({"section": section.tag, "name": key,
                            "group": _mob_group(key),
                            "fields": _record_fields(item, [section_index, item_index])})
    return records


def _mob_source(ds, name, vanilla_path, extract):
    """Read the mod's copy when it exists, else fall back to the vanilla extract."""
    if (ds_dir(ds) / name).exists():
        return {"available": True, "source": name,
                "records": extract(load_file(name, ds)["root"])}
    if not vanilla_path.exists():
        return {"available": False, "source": "", "records": []}
    return {"available": True, "source": f"vanilla extract ({vanilla_path.name})",
            "records": extract(parse_with_comments(vanilla_path))}


def get_mobs(ds="mine"):
    return {
        "combat": _mob_source(ds, COMBAT_FILE, VANILLA_COMBAT_FILE, _combat_records),
        "health": _mob_source(ds, PEDHEALTH_FILE, VANILLA_PEDHEALTH_FILE, _pedhealth_records),
    }


MOB_FILES = {
    "combat": (COMBAT_FILE, COMBAT_GAME_PATH, VANILLA_COMBAT_FILE),
    "health": (PEDHEALTH_FILE, PEDHEALTH_GAME_PATH, VANILLA_PEDHEALTH_FILE),
}

# ---- per-model view (#190) ----
# The model -> archetype binding exists in no extracted file and in no script,
# so it cannot be read statically. MobProbe spawns each model and reports the
# max health the running game gave it; that observation is the only evidence we
# have, and the editor presents it as an observation rather than a fact about
# the data. Assignments are written as a runtime override list, the same shape
# as merchant_buy_overrides.csv.
MOB_ROSTER_FILE = PROJECT_ROOT / "MobProbe" / "ped_models.csv"
MOB_PROBE_FILE = PROJECT_ROOT / "MobProbe" / "mob_stats.csv"
MOB_DISCOVERED_FILE = PROJECT_ROOT / "MobProbe" / "mob_stats_discovered.csv"


def _read_csv_rows(path):
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    return rows


def _health_by_hp(ds):
    """Max-health value -> the archetypes that declare it.

    Several archetypes share a value (four enemy tiers all sit at 70), so this
    maps to a LIST. The editor shows every candidate instead of picking one.
    """
    out = {}
    root_records = [r for r in get_mobs(ds)["health"]["records"] if r["section"] == "HealthConfig"]
    for record in root_records:
        energy = next((f["value"] for f in record["fields"] if f["field"] == "DefaultEnergy"), None)
        if energy is None:
            continue
        try:
            key = int(round(float(energy)))
        except ValueError:
            continue
        out.setdefault(key, []).append(record["name"])
    return out


def get_mob_models(ds="mine"):
    roster = _read_csv_rows(MOB_ROSTER_FILE)
    probed = {row.get("model", "").upper(): row for row in _read_csv_rows(MOB_PROBE_FILE)}
    by_hp = _health_by_hp(ds)
    models = []
    for row in roster:
        name = (row.get("model") or "").upper()
        if not name:
            continue
        probe = probed.get(name)
        observed = None
        status = "not probed"
        if probe:
            status = probe.get("status", "")
            try:
                observed = int(float(probe.get("max_health") or 0)) or None
            except ValueError:
                observed = None
        candidates = by_hp.get(observed, []) if observed else []
        models.append({
            "model": name,
            "hash": row.get("hash", ""),
            "group": row.get("group", "other"),
            "observedHealth": observed,
            "probeStatus": status,
            "candidates": candidates,
            "effective": candidates[0] if len(candidates) == 1 else "",
        })
    discovered = _read_csv_rows(MOB_DISCOVERED_FILE)
    return {
        "models": models,
        "probeAvailable": MOB_PROBE_FILE.exists(),
        "probedCount": len(probed),
        "discoveredCount": len(discovered),
        "rosterFile": str(MOB_ROSTER_FILE),
        "archetypes": sorted(
            r["name"] for r in get_mobs(ds)["health"]["records"] if r["section"] == "HealthConfig"
        ),
    }


def _validate_mob_value(previous, value, choices):
    """Keep source scalar types and source enum choices."""
    import math
    original = str(previous).strip()
    candidate = str(value).strip()
    if original.lower() in ("true", "false"):
        if candidate.lower() not in ("true", "false"):
            raise ValueError("Expected true or false")
    elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", original):
        try:
            valid = bool(candidate) and math.isfinite(float(candidate))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Expected a finite number")
    elif candidate != original and candidate not in choices:
        raise ValueError("Choose a value present in the source data")
    return candidate


def apply_mob_edits(edits):
    changed = 0
    touched = set()
    for edit in edits:
        target = MOB_FILES.get(edit.get("file"))
        if target is None:
            raise ValueError(f"unknown mobs file: {edit.get('file')}")
        name, game_path, vanilla_path = target
        path = ds_dir("mine") / name
        if not path.exists():
            if not vanilla_path.exists():
                raise ValueError(f"vanilla {name} extract is missing")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vanilla_path, path)
        root = load_file(name)["root"]
        node = root
        try:
            for index in edit["path"]:
                node = list(node)[int(index)]
        except (IndexError, TypeError, ValueError, KeyError):
            continue
        kind = edit.get("kind")
        attr = "value" if kind == "attr" else "ref" if kind == "ref" else None
        previous = node.get(attr) if attr else node.text
        choices = {str(sibling.get(attr) if attr else sibling.text).strip()
                   for sibling in root.iter(node.tag)}
        value = _validate_mob_value(previous, edit["value"], choices)
        if kind == "attr" and node.get("value") is not None:
            node.set("value", value)
        elif kind == "ref" and node.get("ref") is not None:
            node.set("ref", value)
        elif kind == "text" and len(node) == 0:
            node.text = value
        else:
            continue
        changed += 1
        touched.add((name, game_path))
    for name, game_path in touched:
        save_file(name)
        ensure_file_replacement(game_path, name)
    return changed


# ---------------- HTTP ----------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Lexeditor-Plugin", PLUGIN_ID)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _gzip_json_file(self, path):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Encoding", "gzip")
        self.send_header("X-Lexeditor-Plugin", PLUGIN_ID)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            url = urlparse(self.path)
            path = url.path
            ds = parse_qs(url.query).get("ds", ["mine"])[0]
            with _lock:
                if path in ("/", "/index.html"):
                    data = (ROOT / "editor.html").read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("X-Lexeditor-Plugin", PLUGIN_ID)
                    # The editor is a single HTML file (CSS + JS inline). Without
                    # this the browser caches it and keeps showing an OLD build
                    # after edits, which made fixes look like they did nothing.
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif path.startswith("/assets/"):
                    relative = Path(path.removeprefix("/assets/").replace("/", os.sep))
                    asset = (ROOT / "assets" / relative).resolve()
                    assets_root = (ROOT / "assets").resolve()
                    if assets_root not in asset.parents or not asset.is_file():
                        self._json({"error": "asset not found"}, 404)
                    else:
                        data = asset.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", mimetypes.guess_type(asset.name)[0] or "application/octet-stream")
                        self.send_header("Cache-Control", "public, max-age=3600")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                elif path.startswith("/shared/"):
                    relative = Path(path.removeprefix("/shared/").replace("/", os.sep))
                    shared_root = (LEXEDITOR_ROOT / "ui").resolve()
                    shared = (shared_root / relative).resolve()
                    if shared_root not in shared.parents or not shared.is_file():
                        self._json({"error": "shared UI asset not found"}, 404)
                    else:
                        data = shared.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", mimetypes.guess_type(shared.name)[0] or "application/octet-stream")
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                elif path == "/api/plugin":
                    self._json({
                        "apiVersion": PLUGIN_API_VERSION,
                        "pluginId": PLUGIN_ID,
                        "name": "Red Dead Redemption 2",
                        "hosted": PLUGIN_HOSTED,
                        "windowHost": os.environ.get("LEXEDITOR_WINDOW_HOST", ""),
                        "projectRoot": str(PROJECT_ROOT),
                        "editorRoot": str(ROOT),
                        "capabilities": [
                            "catalog", "challenges", "crime", "crafting",
                            "data-map", "items", "loot", "model-preview", "settings", "shops",
                            "weapons",
                        ],
                    })
                elif path == "/api/loot-usage":
                    # Where each loot table is invoked from; regenerate with
                    # tools/build_loot_usage.py after updating the decompiled scripts.
                    usage = ROOT / "loot_usage.json"
                    self._json(json.loads(usage.read_text(encoding="utf-8"))
                               if usage.exists() else {"tables": {}})
                elif path == "/api/config":
                    out = {}
                    for key, info in DATASETS.items():
                        d = info["dir"]
                        out[key] = {
                            "label": info["label"],
                            "readonly": info["readonly"],
                            "scopes": info["scopes"],
                            "dir": str(d),
                            "catalog": (d / CATALOG_FILE).exists(),
                            "quickSelect": data_file_path(QUICK_SELECT_FILE, key).exists(),
                            "lootFiles": [f for f in LOOT_FILES if (d / f).exists()],
                            "matrix": (d / MATRIX_FILE).exists(),
                            "crime": (d / CRIME_FILE).exists(),
                            "dispatch": (d / DISPATCH_FILE).exists(),
                            "challenges": (d / GOALS_FILE).exists(),
                        }
                    self._json({
                        "datasets": out,
                        "extensions": {
                            "gameplaySettings": {"available": GAMEPLAY_INI_FILE.exists(), "file": str(GAMEPLAY_INI_FILE)},
                            "customCrafting": {"available": VANILLA_CRAFTING_FILE.exists(),
                                               "customFile": str(CUSTOM_CRAFTING_FILE),
                                               "vanillaFile": str(VANILLA_CRAFTING_FILE)},
                        },
                    })
                elif path == "/api/settings":
                    self._json(get_gameplay_settings())
                elif path == "/api/model-preview/availability":
                    item_key = parse_qs(url.query).get("item", [""])[0].strip()
                    model = catalog_item_model(item_key, ds)
                    self._json(_model_preview_availability(model))
                elif path == "/api/model-preview/settings":
                    self._json(_get_preview_settings())
                elif path == "/api/model-preview/geometry":
                    key = parse_qs(url.query).get("key", [""])[0]
                    try:
                        self._gzip_json_file(_cached_preview_geometry(key))
                    except (FileNotFoundError, ValueError) as error:
                        self._json({"error": str(error)}, 404)
                elif path == "/api/model-preview/texture":
                    query = parse_qs(url.query)
                    key = query.get("key", [""])[0]
                    name = query.get("name", [""])[0]
                    try:
                        texture = _cached_preview_texture(key, name)
                        data = texture.read_bytes()
                        self.send_response(200)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("X-Lexeditor-Plugin", PLUGIN_ID)
                        self.send_header("Cache-Control", "public, max-age=3600")
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                    except (FileNotFoundError, ValueError) as error:
                        self._json({"error": str(error)}, 404)
                elif path == "/api/alcohol-strengths":
                    self._json(get_alcohol_strengths())
                elif path == "/api/custom-crafting":
                    self._json(get_custom_crafting())
                elif path == "/api/catalog":
                    self._json(get_catalog(ds))
                elif path == "/api/quick-select":
                    self._json(get_quick_select(ds))
                elif path == "/api/item-script-provenance":
                    key = parse_qs(url.query).get("item", [""])[0]
                    self._json(get_item_script_provenance(key))
                elif path == "/api/shops":
                    self._json(get_shops(ds))
                elif path == "/api/shops/catalogue-placement":
                    query = parse_qs(url.query)
                    try:
                        self._json(get_catalogue_placement(
                            query.get("item", [""])[0],
                            query.get("shop", [""])[0],
                            query.get("category", [""])[0] or None,
                        ))
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/shop-buyers":
                    self._json(get_shop_buyers() if ds == "mine" else {"available": False, "buyers": {}, "shops": BUYER_SHOPS})
                elif path == "/api/shops/acceptance":
                    self._json(get_shop_acceptance_report() if ds == "mine" else {"available": False, "shops": BUYER_SHOPS, "summary": {}, "rows": [], "unresolvedListed": {}})
                elif path.startswith("/api/loot/"):
                    name = path.split("/api/loot/", 1)[1]
                    if name not in LOOT_FILES:
                        self._json({"error": "unknown file"}, 404)
                    else:
                        self._json(get_loot(name, ds))
                elif path == "/api/matrix":
                    self._json(get_matrix(ds))
                elif path == "/api/crime":
                    self._json(get_crime(ds))
                elif path == "/api/dispatch":
                    self._json(get_dispatch(ds))
                elif path == "/api/bounty-hunters":
                    self._json(get_bounty_hunters(ds))
                elif path == "/api/honor-actions":
                    self._json(get_honor_actions() if ds == "mine" else {"available": False, "events": [], "tiers": []})
                elif path == "/api/challenges":
                    self._json(get_challenges(ds))
                elif path == "/api/datamap":
                    self._json(get_data_map())
                elif path == "/api/labels":
                    self._json(get_labels())
                elif path == "/api/localization":
                    self._json(get_localization(ds))
                elif path == "/api/weapons":
                    self._json(get_weapons(ds))
                elif path == "/api/weapons-reference":
                    self._json(get_weapon_reference())
                elif path == "/api/weapons/projectile-speeds":
                    self._json(get_projectile_speeds(ds))
                elif path == "/api/mobs":
                    self._json(get_mobs(ds))
                elif path == "/api/mob-models":
                    self._json(get_mob_models(ds))
                elif path.startswith("/api/ai-reference/"):
                    self._json(get_ai_reference(path.split("/api/ai-reference/", 1)[1]))
                elif path.startswith("/api/ai/"):
                    self._json(get_ai_file(path.split("/api/ai/", 1)[1], ds))
                else:
                    self._json({"error": "not found"}, 404)
        except FileNotFoundError as ex:
            self._json({"error": f"file not present in this dataset: {ex.filename}"}, 404)
        except Exception as ex:  # surface errors to the UI
            self._json({"error": str(ex)}, 500)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            url = urlparse(self.path)
            path = url.path
            ds = parse_qs(url.query).get("ds", ["mine"])[0]
            with _lock:
                if path == "/api/catalog/save":
                    n = apply_catalog_edits(body)
                    self._json({"saved": n})
                elif path == "/api/catalog/create":
                    self._json(create_catalog_item(body))
                elif path == "/api/catalog/effects/create":
                    self._json(create_catalog_effect(body))
                elif path == "/api/settings/save":
                    self._json({"saved": save_gameplay_settings(body.get("edits", []))})
                elif path == "/api/model-preview":
                    item_key = str(body.get("item", "")).strip()
                    model = catalog_item_model(item_key, ds)
                    requested_model = str(body.get("model", "")).strip()
                    if requested_model and requested_model.casefold() != model.casefold():
                        self._json({"error": "The requested model does not match the catalog item"}, 400)
                    else:
                        try:
                            components = catalog_preview_components(item_key, model, ds)
                            self._json(_prepare_model_preview(item_key, model, components))
                        except _PreviewUnavailable as error:
                            self._json({
                                "error": str(error), "available": False,
                                "item": item_key, "model": model,
                            }, 422)
                elif path == "/api/model-preview/settings":
                    try:
                        self._json(_save_preview_settings(body))
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/model-preview/cache/clear":
                    self._json(_clear_preview_cache())
                elif path == "/api/alcohol-strengths/save":
                    self._json({"saved": save_alcohol_strengths(body.get("entries", {}))})
                elif path == "/api/custom-crafting/save":
                    try:
                        self._json({"saved": save_custom_crafting(body.get("recipes", []))})
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/shops/save":
                    try:
                        self._json({"saved": apply_shop_edits(body.get("edits", []))})
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/shop-buyers/save":
                    self._json({"saved": apply_shop_buyer_edits(body.get("edits", []))})
                elif path == "/api/labels/save":
                    self._json({"saved": save_label(body.get("scope", ""), body.get("key", ""), body.get("value", ""))})
                elif path == "/api/localization/save":
                    self._json({"saved": save_localization(body.get("edits", []))})
                elif path.startswith("/api/loot/") and path.endswith("/save"):
                    name = path[len("/api/loot/"):-len("/save")]
                    if name not in LOOT_FILES:
                        self._json({"error": "unknown file"}, 404)
                    else:
                        try:
                            self._json({"saved": apply_loot_edits(name, body.get("edits", []))})
                        except ValueError as e:
                            self._json({"error": str(e)}, 400)
                elif path.startswith("/api/loot/") and path.endswith("/create"):
                    name = path[len("/api/loot/"):-len("/create")]
                    if name not in LOOT_FILES:
                        self._json({"error": "unknown file"}, 404)
                    else:
                        try:
                            self._json({"table": create_loot_table(name, body)})
                        except ValueError as e:
                            self._json({"error": str(e)}, 400)
                elif path.startswith("/api/loot/") and path.endswith("/delete"):
                    name = path[len("/api/loot/"):-len("/delete")]
                    if name not in LOOT_FILES:
                        self._json({"error": "unknown file"}, 404)
                    else:
                        try:
                            self._json({"deleted": delete_loot_table(name, body.get("key", ""))})
                        except ValueError as e:
                            self._json({"error": str(e)}, 400)
                elif path == "/api/matrix/save":
                    self._json({"saved": apply_matrix_edits(body.get("edits", []))})
                elif path == "/api/crime/save":
                    self._json({"saved": apply_crime_edits(body.get("edits", []))})
                elif path == "/api/dispatch/save":
                    self._json({"saved": apply_dispatch_edits(body.get("edits", []))})
                elif path == "/api/bounty-hunters/save":
                    self._json({"saved": apply_bounty_hunter_edits(body.get("edits", []))})
                elif path == "/api/honor-actions/save":
                    try:
                        self._json({"saved": save_honor_actions(body.get("edits", []))})
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/challenges/save":
                    self._json({"saved": apply_challenge_edits(body.get("edits", []), body.get("rewards", []), body.get("uiEdits", []), body.get("conditions", []), body.get("modes", []))})
                elif path == "/api/weapons/save":
                    self._json({"saved": apply_weapon_edits(
                        body.get("section", ""), body.get("name", ""),
                        body.get("edits", []), body.get("sourceFile", WEAPONS_FILE))})
                elif path == "/api/weapons/shell-vfx/save":
                    self._json({"saved": apply_weapon_shell_vfx(body.get("blanked", False))})
                elif path == "/api/weapons/projectile-speeds/save":
                    try:
                        self._json({"saved": save_projectile_speeds(body.get("entries", []))})
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                elif path == "/api/mobs/save":
                    self._json({"saved": apply_mob_edits(body.get("edits", []))})
                elif path.startswith("/api/ai/") and path.endswith("/save"):
                    name = path[len("/api/ai/"):-len("/save")]
                    self._json({"saved": apply_ai_edits(name, body.get("edits", []))})
                else:
                    self._json({"error": "not found"}, 404)
        except Exception as ex:
            self._json({"error": str(ex)}, 500)

    def do_PUT(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            path = urlparse(self.path).path
            with _lock:
                if path == "/api/custom-crafting":
                    try:
                        self._json({"saved": save_custom_crafting(body.get("recipes", []))})
                    except ValueError as error:
                        self._json({"error": str(error)}, 400)
                else:
                    self._json({"error": "not found"}, 404)
        except Exception as ex:
            self._json({"error": str(ex)}, 500)


def create_server(port=PORT):
    """Create one loopback-only server for the Lexeditor host or a check."""
    return ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)


def main():
    server = create_server()
    actual_port = int(server.server_address[1])
    url = f"http://127.0.0.1:{actual_port}/"
    print("LEXEDITOR RDR2 plugin service")
    for key, info in DATASETS.items():
        print(f"  {key:8} {info['dir']}")
    print(f"  Open:    {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
