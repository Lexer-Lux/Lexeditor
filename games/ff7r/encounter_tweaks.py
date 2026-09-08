"""Reversible authored encounter tweaks for FF7R.

The Chapter 5 request targets one Corkscrew Tunnel (`tnnl4`) BattleScene whose
vanilla composition is two Flametroopers and two turret/sentry enemies. The
composition is authored in `BattleScene.BattleCharaSpecID_Array`, with several
parallel per-enemy arrays. Lexeditor discovers the exact row from installed data
and removes the second turret index from every aligned per-enemy array only at
build time.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Any

from .archive import extract_pair
from .dataobject import DataObjectPackage
from .text_storage import resident_text_map


ENCOUNTER_SCHEMA_VERSION = 1
ENCOUNTER_CONFIG_NAME = "LexeditorFF7REncounterTweaks.json"
ENCOUNTER_TWEAKS_ASSET = "Lexeditor/EncounterTweaks"
BATTLE_SCENE_TABLE = "battlescene"
BATTLE_CHARA_TABLE = "battlecharaspec"
ENEMY_BOOK_TABLE = "enemybook"
CHAPTER5_AREA_TOKEN = "tnnl4"

FLAMETROOPER_TERMS = ("flametrooper", "flame trooper")
TURRET_TERMS = (
    "turret",
    "sentry launcher",
    "sentry gun",
    "sentry ray",
    "sentry",
)

# These BattleScene arrays are authored per BattleCharaSpec slot in the generated
# FF7R schema. Empty arrays are allowed. A non-empty length other than the enemy
# count is treated as evidence that the installed build uses a different shape.
PER_ENEMY_ARRAYS = (
    "BattleCharaSpecID_Array",
    "Level_Array",
    "OverrideItemPossession_Array",
    "OverrideResponseAreaID_Array",
    "RoleType_Array",
    "EntryType_Array",
    "EntrySpecialStatusChangeID_Array",
    "Flag0_Array",
    "BattleCharaRoleID_Array",
    "TalkGroupID_Array",
    "BattleConditionTriggerGroupId_Array",
)

DEFAULT_ENCOUNTER_CONFIG = {
    "schemaVersion": ENCOUNTER_SCHEMA_VERSION,
    "chapter5SubwayReducedTurret": False,
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / ENCOUNTER_CONFIG_NAME


def validate_encounter_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("encounter tweak config must be an object")
    allowed = {"schemaVersion", "chapter5SubwayReducedTurret"}
    if set(value) - allowed:
        raise ValueError("encounter tweak config contains unsupported fields")
    if value.get("schemaVersion", ENCOUNTER_SCHEMA_VERSION) != ENCOUNTER_SCHEMA_VERSION:
        raise ValueError("unsupported FF7R encounter tweak config schema")
    enabled = value.get("chapter5SubwayReducedTurret", False)
    if not isinstance(enabled, bool):
        raise ValueError("chapter5SubwayReducedTurret must be boolean")
    return {
        "schemaVersion": ENCOUNTER_SCHEMA_VERSION,
        "chapter5SubwayReducedTurret": enabled,
    }


def load_encounter_config(project_root: Path) -> dict:
    target = config_path(project_root)
    if not target.is_file():
        return dict(DEFAULT_ENCOUNTER_CONFIG)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R encounter tweak config: {error}") from error
    return validate_encounter_config(payload)


def save_encounter_config(project_root: Path, value: dict) -> dict:
    validated = validate_encounter_config(value)
    target = config_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    reread = load_encounter_config(project_root)
    if reread != validated:
        raise RuntimeError("FF7R encounter tweak config failed atomic readback")
    return reread


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _find(index: dict, basename: str) -> dict | None:
    for row in index.get("assets", []):
        if row.get("synthetic"):
            continue
        if _basename(str(row.get("asset", ""))) == basename:
            return row
    return None


def _load_source(game_root: Path, data_root: Path, index: dict, basename: str):
    row = _find(index, basename)
    if row is None:
        return None
    uasset, uexp = extract_pair(game_root, data_root, index, row["asset"])
    return DataObjectPackage(uasset, uexp, asset=row["asset"])


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)


def _normalized(value: str) -> str:
    return " ".join(str(value).casefold().replace("_", " ").replace("-", " ").split())


def _matches(values: list[str], terms: tuple[str, ...]) -> bool:
    normalized = [_normalized(value) for value in values if value]
    for value in normalized:
        compact = "".join(ch for ch in value if ch.isalnum())
        for term in terms:
            folded = _normalized(term)
            if folded in value:
                return True
            if "".join(ch for ch in folded if ch.isalnum()) in compact:
                return True
    return False


def _enemy_labels(enemy_book, text: dict[str, str]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    if enemy_book is None:
        return labels
    for entry in enemy_book.entries:
        evidence = [entry.tag]
        for value in _walk_strings(entry.values):
            evidence.append(value)
            if value in text:
                evidence.append(text[value])
        labels[entry.tag] = evidence
    return labels


def _classify_battle_chara(battle_chara, enemy_book, text: dict[str, str]) -> dict[str, str]:
    labels = _enemy_labels(enemy_book, text)
    result: dict[str, str] = {}
    if battle_chara is None:
        return result
    for entry in battle_chara.entries:
        enemy_book_id = str(entry.values.get("EnemyBookID", ""))
        evidence = [entry.tag, enemy_book_id, *labels.get(enemy_book_id, [])]
        if _matches(evidence, FLAMETROOPER_TERMS):
            result[entry.tag] = "flametrooper"
        elif _matches(evidence, TURRET_TERMS):
            result[entry.tag] = "turret"
        else:
            result[entry.tag] = "other"
    return result


def discover_chapter5_subway_encounter(game_root: Path, data_root: Path, project_root: Path,
                                      index: dict, *, language: str = "US") -> dict:
    battle_scene = _load_source(game_root, data_root, index, BATTLE_SCENE_TABLE)
    battle_chara = _load_source(game_root, data_root, index, BATTLE_CHARA_TABLE)
    enemy_book = _load_source(game_root, data_root, index, ENEMY_BOOK_TABLE)
    errors: list[str] = []
    try:
        text = resident_text_map(game_root, data_root, project_root, index, language=language)
    except Exception as error:
        text = {}
        errors.append(f"text lookup: {error}")

    classes = _classify_battle_chara(battle_chara, enemy_book, text)
    candidates = []
    if battle_scene is not None:
        prop_names = {prop.name for prop in battle_scene.properties}
        if "BattleCharaSpecID_Array" not in prop_names:
            errors.append("BattleScene has no BattleCharaSpecID_Array on this installed build")
        else:
            for entry in battle_scene.entries:
                if CHAPTER5_AREA_TOKEN not in entry.tag.casefold():
                    continue
                ids = entry.values.get("BattleCharaSpecID_Array", [])
                if not isinstance(ids, list) or len(ids) != 4:
                    continue
                kinds = [classes.get(str(enemy_id), "other") for enemy_id in ids]
                if kinds.count("flametrooper") != 2 or kinds.count("turret") != 2:
                    continue
                turret_indices = [i for i, kind in enumerate(kinds) if kind == "turret"]
                flame_indices = [i for i, kind in enumerate(kinds) if kind == "flametrooper"]
                shapes = {}
                unexpected = []
                for field in PER_ENEMY_ARRAYS:
                    value = entry.values.get(field)
                    if not isinstance(value, list):
                        continue
                    shapes[field] = len(value)
                    if len(value) not in {0, len(ids)}:
                        unexpected.append(field)
                candidates.append({
                    "entry": entry.index,
                    "sceneTag": entry.tag,
                    "battleCharaSpecIds": list(ids),
                    "kinds": kinds,
                    "flametrooperIndices": flame_indices,
                    "turretIndices": turret_indices,
                    "removeIndex": turret_indices[-1],
                    "parallelArrayLengths": shapes,
                    "unexpectedParallelArrayLengths": unexpected,
                })

    return {
        "language": language.upper(),
        "battleSceneAsset": battle_scene.asset if battle_scene else "",
        "battleCharaAsset": battle_chara.asset if battle_chara else "",
        "enemyBookAsset": enemy_book.asset if enemy_book else "",
        "candidateCount": len(candidates),
        "candidates": candidates,
        "classificationCounts": {
            "flametrooper": sum(kind == "flametrooper" for kind in classes.values()),
            "turret": sum(kind == "turret" for kind in classes.values()),
        },
        "errors": errors,
        "notes": [
            "The target is accepted only when one tnnl4 BattleScene contains exactly two classified Flametroopers and two classified turret/sentry enemies.",
            "The second/last authored turret slot is removed deterministically, preserving the first turret and both Flametroopers.",
            "Parallel per-enemy arrays must be empty or exactly four elements before structural deletion; any other shape fails closed.",
        ],
    }


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def resource_spec(game_root: Path, data_root: Path, project_root: Path, index: dict,
                  *, vanilla: bool = False) -> dict:
    discovery = discover_chapter5_subway_encounter(
        game_root, data_root, project_root, index)
    config = dict(DEFAULT_ENCOUNTER_CONFIG) if vanilla else load_encounter_config(project_root)
    source_sha = _canonical_hash({"schema": ENCOUNTER_SCHEMA_VERSION, "discovery": discovery})
    active_sha = _canonical_hash({"source": source_sha, "config": config})
    target = discovery["candidates"][0] if discovery["candidateCount"] == 1 else None
    return {
        "sourceSha256": source_sha,
        "activeSha256": active_sha,
        "properties": [
            {"name": "Chapter5SubwayReducedTurret", "label": "Chapter 5 Subway: Remove One Turret", "type": "BOOL", "editable": True, "min": 0, "max": 1},
            {"name": "CandidateCount", "label": "Matching Installed Encounters", "type": "INT32", "editable": False, "min": None, "max": None},
            {"name": "TargetScene", "label": "Target BattleScene", "type": "STRING", "editable": False, "min": None, "max": None},
            {"name": "VanillaComposition", "label": "Vanilla Composition", "type": "STRING", "editable": False, "min": None, "max": None},
            {"name": "RemovalSlot", "label": "Removed Turret Slot", "type": "INT32", "editable": False, "min": None, "max": None},
            {"name": "ResearchNotes", "label": "Validation Notes", "type": "STRING", "editable": False, "min": None, "max": None},
        ],
        "entries": [{
            "tag": "Chapter 5 Subway Encounter",
            "values": {
                "Chapter5SubwayReducedTurret": config["chapter5SubwayReducedTurret"],
                "CandidateCount": discovery["candidateCount"],
                "TargetScene": target["sceneTag"] if target else "Unresolved",
                "VanillaComposition": "2 Flametroopers + 2 turrets" if target else "Unresolved",
                "RemovalSlot": target["removeIndex"] if target else -1,
                "ResearchNotes": " ".join(discovery["notes"] + discovery["errors"]),
            },
        }],
        "discovery": discovery,
        "usingProject": (not vanilla and config_path(project_root).is_file()),
    }


def save_virtual_edits(game_root: Path, data_root: Path, project_root: Path, index: dict,
                       *, source_sha256: str, active_sha256: str,
                       edits: list[dict[str, Any]]) -> dict:
    spec = resource_spec(game_root, data_root, project_root, index)
    if spec["sourceSha256"] != source_sha256:
        raise RuntimeError("Installed FF7R encounter data changed; reload Encounter Tweaks before saving")
    if spec["activeSha256"] != active_sha256:
        raise RuntimeError("FF7R encounter tweak config changed on disk; reload before saving")
    if not isinstance(edits, list):
        raise TypeError("encounter edits must be a list")
    config = load_encounter_config(project_root)
    seen = False
    for edit in edits:
        if not isinstance(edit, dict):
            raise TypeError("each encounter edit must be an object")
        if int(edit.get("entry", -1)) != 0 or "index" in edit:
            raise ValueError("Encounter Tweaks accepts scalar edits on its single record only")
        if str(edit.get("property", "")) != "Chapter5SubwayReducedTurret":
            raise ValueError("encounter property is read-only or unknown")
        if seen:
            raise ValueError("duplicate encounter tweak edit")
        seen = True
        value = edit.get("value")
        if not isinstance(value, bool):
            raise ValueError("Chapter 5 subway encounter toggle must be boolean")
        config["chapter5SubwayReducedTurret"] = value
    saved = save_encounter_config(project_root, config)
    refreshed = resource_spec(game_root, data_root, project_root, index)
    return {
        "asset": ENCOUNTER_TWEAKS_ASSET,
        "path": str(config_path(project_root)),
        "saved": len(edits),
        "activeSha256": refreshed["activeSha256"],
        "usingProject": True,
        "enabled": saved["chapter5SubwayReducedTurret"],
    }


def has_enabled_encounter_tweaks(project_root: Path) -> bool:
    return load_encounter_config(project_root)["chapter5SubwayReducedTurret"]


def _staging_pair(staging_root: Path, source_uasset: Path, source_uexp: Path,
                  asset: str) -> tuple[Path, Path]:
    root = Path(staging_root).resolve()
    uasset = (root / f"{asset}.uasset").resolve()
    uexp = (root / f"{asset}.uexp").resolve()
    if root not in uasset.parents or root not in uexp.parents:
        raise ValueError(f"Unsafe FF7R encounter staging path: {asset}")
    if uasset.is_file() != uexp.is_file():
        raise RuntimeError(f"Encounter staging has an incomplete package pair for {asset}")
    if not uasset.is_file():
        uasset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_uasset, uasset)
        shutil.copy2(source_uexp, uexp)
    return uasset, uexp


def materialize_encounter_tweaks(game_root: Path, data_root: Path, project_root: Path,
                                 index: dict, staging_root: Path) -> list[dict]:
    if not has_enabled_encounter_tweaks(project_root):
        return []
    discovery = discover_chapter5_subway_encounter(
        game_root, data_root, project_root, index)
    if discovery["candidateCount"] != 1:
        raise RuntimeError(
            "Chapter 5 subway encounter tweak requires exactly one installed 2-Flametrooper/2-turret tnnl4 BattleScene; "
            f"found {discovery['candidateCount']}"
        )
    candidate = discovery["candidates"][0]
    if candidate["unexpectedParallelArrayLengths"]:
        raise RuntimeError(
            "Chapter 5 subway encounter uses unexpected per-enemy array lengths: "
            + ", ".join(candidate["unexpectedParallelArrayLengths"])
        )

    asset = discovery["battleSceneAsset"]
    source_uasset, source_uexp = extract_pair(game_root, data_root, index, asset)
    target_uasset, target_uexp = _staging_pair(
        staging_root, source_uasset, source_uexp, asset)
    package = DataObjectPackage(target_uasset, target_uexp, asset=asset)
    try:
        entry = next(row for row in package.entries if row.tag == candidate["sceneTag"])
    except StopIteration as error:
        raise RuntimeError("Target Chapter 5 BattleScene disappeared from staged project data") from error
    current_ids = entry.values.get("BattleCharaSpecID_Array", [])
    if list(current_ids) != candidate["battleCharaSpecIds"]:
        raise RuntimeError(
            "Target Chapter 5 encounter composition was already changed in project data; automatic turret removal refused"
        )

    enemy_count = len(candidate["battleCharaSpecIds"])
    remove_index = candidate["removeIndex"]
    deleted_fields = []
    for field in PER_ENEMY_ARRAYS:
        entry = package.entries[entry.index]
        value = entry.values.get(field)
        if not isinstance(value, list) or len(value) == 0:
            continue
        if len(value) != enemy_count:
            raise RuntimeError(
                f"Target Chapter 5 encounter field {field} has {len(value)} entries, expected 0 or {enemy_count}"
            )
        package.delete_array_element(entry.index, field, remove_index)
        deleted_fields.append(field)

    if "BattleCharaSpecID_Array" not in deleted_fields:
        raise RuntimeError("Target Chapter 5 encounter did not delete its enemy composition slot")
    package.write_pair(target_uasset, target_uexp)
    verified = DataObjectPackage(target_uasset, target_uexp, asset=asset)
    verified_entry = next(row for row in verified.entries if row.tag == candidate["sceneTag"])
    result_ids = verified_entry.values["BattleCharaSpecID_Array"]
    if len(result_ids) != 3:
        raise RuntimeError("Chapter 5 encounter structural write did not produce three enemies")
    if result_ids.count(candidate["battleCharaSpecIds"][remove_index]) != 1:
        raise RuntimeError("Chapter 5 encounter did not reduce the duplicated turret to one instance")

    return [{
        "asset": asset,
        "sceneTag": candidate["sceneTag"],
        "removedIndex": remove_index,
        "removedBattleCharaSpecId": candidate["battleCharaSpecIds"][remove_index],
        "deletedFields": deleted_fields,
        "resultBattleCharaSpecIds": list(result_ids),
    }]
