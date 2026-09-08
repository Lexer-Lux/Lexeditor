"""Read-only correlation probe for FF7R HP Rebalance.

The tweak must scale final playable-character max HP after progression,
equipment, materia, and weapon-upgrade effects. This probe inventories all
publicly identified installed HP data sources and pairs them with native
final-status getter/setter candidates so the eventual runtime hook can target the
composed value rather than approximate it by independently rounding authored
components.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from .archive import extract_pair
from .dataobject import DataObjectPackage
from .native_probe import probe_installed_exe
from .text_storage import resident_text_map


PLAYER_PARAMETER = "playerparameter"
EQUIPMENT = "equipment"
MATERIA = "materia"
EQUIPMENT_SKILL = "equipmentskill"
WEAPON_UPGRADE = "weaponupgrade"
HP_MAX_ADD_EFFECT_TYPE = 1

NATIVE_NEEDLES = (
    "BPGetPlayerStatus",
    "BPGetPlayerStatusWithEquipment",
    "BPGetPlayerStatusWithMateria",
    "BPGetPlayerHPMax",
    "BPGetPlayerHP",
    "BPSetPlayerHPMax",
    "GetHPMax",
    "GetHP",
)

NAME_HINTS = (
    "ItemNameLabel",
    "EquipmentNameLabel",
    "MateriaNameLabel",
    "NameLabel",
    "Name",
)
MAX_ROWS = 4096


def _basename(asset: str) -> str:
    return PurePosixPath(asset).name.casefold()


def _find(index: dict, basename: str) -> dict | None:
    for row in index.get("assets", []):
        if row.get("synthetic"):
            continue
        if _basename(str(row.get("asset", ""))) == basename:
            return row
    return None


def _load(game_root: Path, data_root: Path, index: dict, basename: str):
    row = _find(index, basename)
    if row is None:
        return None
    uasset, uexp = extract_pair(game_root, data_root, index, row["asset"])
    return DataObjectPackage(uasset, uexp, asset=row["asset"])


def _resolved_name(entry, text: dict[str, str]) -> str:
    for name in NAME_HINTS:
        value = entry.values.get(name)
        if isinstance(value, str) and value in text:
            return text[value]
    for value in entry.values.values():
        if isinstance(value, str) and value.startswith("$") and value in text:
            return text[value]
    return entry.tag


def _scalar_rows(package, fields: tuple[str, ...], *, text: dict[str, str] | None = None) -> list[dict]:
    if package is None:
        return []
    props = {prop.name for prop in package.properties}
    available = [field for field in fields if field in props]
    rows = []
    for entry in package.entries[:MAX_ROWS]:
        values = {field: entry.values[field] for field in available}
        rows.append({
            "entry": entry.index,
            "tag": entry.tag,
            "name": _resolved_name(entry, text or {}),
            "values": values,
        })
    return rows


def _property_names(package) -> list[str]:
    return [prop.name for prop in package.properties] if package else []


def probe_hp_rebalance_sources(game_root: Path, data_root: Path, project_root: Path,
                               index: dict, *, language: str = "US") -> dict:
    game_root = Path(game_root).resolve()
    data_root = Path(data_root).resolve()
    project_root = Path(project_root).resolve()

    try:
        text = resident_text_map(game_root, data_root, project_root, index, language=language)
    except Exception:
        text = {}

    player = _load(game_root, data_root, index, PLAYER_PARAMETER)
    equipment = _load(game_root, data_root, index, EQUIPMENT)
    materia = _load(game_root, data_root, index, MATERIA)
    equipment_skill = _load(game_root, data_root, index, EQUIPMENT_SKILL)
    weapon_upgrade = _load(game_root, data_root, index, WEAPON_UPGRADE)

    player_rows = _scalar_rows(player, ("HPMax",), text=text)
    equipment_rows = [
        row for row in _scalar_rows(equipment, ("HPMaxAdd", "HPMaxScale"), text=text)
        if any(row["values"].get(field, 0) != 0 for field in ("HPMaxAdd", "HPMaxScale"))
    ]
    materia_rows = [
        row for row in _scalar_rows(materia, ("HPMaxAdd", "HPMaxScale"), text=text)
        if any(row["values"].get(field, 0) != 0 for field in ("HPMaxAdd", "HPMaxScale"))
    ]

    hp_skill_rows: list[dict[str, Any]] = []
    hp_skill_ids: set[str] = set()
    if equipment_skill:
        props = {prop.name for prop in equipment_skill.properties}
        required = {"EffectType0", "EffectValue0"}
        if required.issubset(props):
            for entry in equipment_skill.entries[:MAX_ROWS]:
                try:
                    effect_type = int(entry.values["EffectType0"])
                except (TypeError, ValueError):
                    continue
                if effect_type != HP_MAX_ADD_EFFECT_TYPE:
                    continue
                hp_skill_ids.add(entry.tag)
                hp_skill_rows.append({
                    "entry": entry.index,
                    "tag": entry.tag,
                    "effectType": effect_type,
                    "effectValue": entry.values["EffectValue0"],
                    "effectName": entry.values.get("EffectName0"),
                })

    hp_upgrade_rows: list[dict[str, Any]] = []
    if weapon_upgrade:
        props = {prop.name for prop in weapon_upgrade.properties}
        required = {"WeaponID", "EquipmentSkillID", "OverrideParameter"}
        if required.issubset(props):
            for entry in weapon_upgrade.entries[:MAX_ROWS]:
                skill_id = str(entry.values.get("EquipmentSkillID", ""))
                if skill_id not in hp_skill_ids:
                    continue
                hp_upgrade_rows.append({
                    "entry": entry.index,
                    "tag": entry.tag,
                    "weaponId": entry.values.get("WeaponID"),
                    "equipmentSkillId": skill_id,
                    "overrideParameter": entry.values.get("OverrideParameter"),
                    "nodeName": entry.values.get("NodeName"),
                    "nodeDetail": entry.values.get("NodeDetail"),
                })

    native = probe_installed_exe(game_root, needles=NATIVE_NEEDLES)
    return {
        "language": language.upper(),
        "playerParameter": {
            "asset": player.asset if player else "",
            "properties": _property_names(player),
            "rows": player_rows,
        },
        "equipment": {
            "asset": equipment.asset if equipment else "",
            "properties": _property_names(equipment),
            "hpRows": equipment_rows,
        },
        "materia": {
            "asset": materia.asset if materia else "",
            "properties": _property_names(materia),
            "hpRows": materia_rows,
        },
        "equipmentSkill": {
            "asset": equipment_skill.asset if equipment_skill else "",
            "properties": _property_names(equipment_skill),
            "hpMaxAddEffectType": HP_MAX_ADD_EFFECT_TYPE,
            "hpRows": hp_skill_rows,
        },
        "weaponUpgrade": {
            "asset": weapon_upgrade.asset if weapon_upgrade else "",
            "properties": _property_names(weapon_upgrade),
            "hpUpgradeRows": hp_upgrade_rows,
        },
        "native": native,
        "knownContracts": {
            "finalStatusType": "FEndPlayerStatus.HPMax",
            "finalStatusGetter": "UEndMenuBPAPI::BPGetPlayerStatus(EPlayerType)",
            "hypotheticalEquipmentGetter": "UEndMenuBPAPI::BPGetPlayerStatusWithEquipment(...)",
            "hypotheticalMateriaGetter": "UEndMenuBPAPI::BPGetPlayerStatusWithMateria(...)",
            "directMaxGetter": "UEndMenuBPAPI::BPGetPlayerHPMax(EPlayerType)",
            "directCurrentGetter": "UEndMenuBPAPI::BPGetPlayerHP(EPlayerType)",
            "maxSetter": "UEndMenuBPAPI::BPSetPlayerHPMax(EPlayerType,int32)",
            "battleControllerMaxGetter": "AEndBattleAIController::GetHPMax()",
            "baseHpField": "PlayerParameter.HPMax",
            "equipmentFlatField": "Equipment.HPMaxAdd",
            "equipmentPercentField": "Equipment.HPMaxScale",
            "materiaFlatField": "Materia.HPMaxAdd",
            "materiaPercentField": "Materia.HPMaxScale",
            "equipmentSkillFlatEffect": "EquipmentSkill.EffectType0 == HPMaxAdd(1)",
            "weaponUpgradeFlatOverride": "WeaponUpgrade.OverrideParameter for HPMaxAdd EquipmentSkillID",
        },
        "notes": [
            "HPMaxScale percentage fields are inventoried but should not be multiplied by the Lexeditor HP multiplier; the requested tweak scales final HP, not the percentage modifier itself.",
            "PlayerParameter.HPMax and several flat HP additions are integer-valued, so independently scaling authored components can introduce rounding drift for arbitrary multipliers.",
            "WeaponUpgrade.OverrideParameter is correlated through EquipmentSkillID and EffectType0 rather than text matching.",
            "The preferred implementation remains one build-validated hook on the final composed player HP value, followed by a clamp of current HP to the resulting maximum.",
            "EnemyParameter.HPMax is deliberately excluded from the player-source inventory.",
        ],
    }
