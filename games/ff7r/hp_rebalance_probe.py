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
from typing import Any, Iterable

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

STATUS_NEEDLES = (
    "BPGetPlayerStatus",
    "BPGetPlayerStatusWithEquipment",
    "BPGetPlayerStatusWithMateria",
)
PLAYER_MAX_READ_NEEDLES = (
    "BPGetPlayerHPMax",
    "GetCharaHPMax",
)
PLAYER_CURRENT_READ_NEEDLES = (
    "BPGetPlayerHP",
    "GetCharaHP",
)
PLAYER_MAX_WRITE_NEEDLES = (
    "BPSetPlayerHPMax",
)
PLAYER_CURRENT_WRITE_NEEDLES = (
    "BPSetPlayerHP",
)
GENERIC_HP_NEEDLES = (
    "GetHPMax",
    "GetHP",
)
NATIVE_NEEDLES = (
    *STATUS_NEEDLES,
    *PLAYER_MAX_READ_NEEDLES,
    *PLAYER_CURRENT_READ_NEEDLES,
    *PLAYER_MAX_WRITE_NEEDLES,
    *PLAYER_CURRENT_WRITE_NEEDLES,
    *GENERIC_HP_NEEDLES,
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


def _native_function_evidence(native: dict[str, Any]) -> dict[str, dict[str, list[int]]]:
    """Collect exact .pdata-owned string functions and bounded one-hop targets."""
    result: dict[str, dict[str, list[int]]] = {}
    for row in native.get("needles", ()):
        needle = str(row.get("needle", ""))
        if needle not in NATIVE_NEEDLES:
            continue
        direct: set[int] = set()
        next_hops: set[int] = set()
        for hit in row.get("hits", ()):
            for xref in hit.get("leaRipXrefs", ()):
                if xref.get("candidateFunctionSource") != "pdata":
                    continue
                function_rva = xref.get("candidateFunctionRva")
                if function_rva is not None:
                    direct.add(int(function_rva))
                refs = (xref.get("candidateFunctionCodeRefs") or {}).get("refs", ())
                for ref in refs:
                    target = ref.get("targetFunctionRva")
                    if target is not None:
                        next_hops.add(int(target))
        result[needle] = {
            "directPdataFunctions": sorted(direct),
            "nextHopPdataFunctions": sorted(next_hops),
            "expandedPdataFunctions": sorted(direct | next_hops),
        }
    return result


def _functions(evidence: dict[str, dict[str, list[int]]], needles: Iterable[str]) -> set[int]:
    result: set[int] = set()
    for needle in needles:
        result.update(evidence.get(needle, {}).get("expandedPdataFunctions", ()))
    return result


def _role_clusters(evidence: dict[str, dict[str, list[int]]]) -> list[dict[str, Any]]:
    roles = {
        "composed-status": STATUS_NEEDLES,
        "max-read": PLAYER_MAX_READ_NEEDLES,
        "current-read": PLAYER_CURRENT_READ_NEEDLES,
        "max-write": PLAYER_MAX_WRITE_NEEDLES,
        "current-write": PLAYER_CURRENT_WRITE_NEEDLES,
    }
    needle_role = {
        needle: role
        for role, needles in roles.items()
        for needle in needles
    }
    rows: dict[int, dict[str, Any]] = {}
    for needle, row in evidence.items():
        role = needle_role.get(needle)
        if role is None:
            continue
        for key, destination in (
            ("directPdataFunctions", "directNeedles"),
            ("nextHopPdataFunctions", "nextHopNeedles"),
        ):
            for raw_rva in row.get(key, ()):
                rva = int(raw_rva)
                cluster = rows.setdefault(rva, {
                    "functionRva": rva,
                    "roles": set(),
                    "directNeedles": set(),
                    "nextHopNeedles": set(),
                })
                cluster["roles"].add(role)
                cluster[destination].add(needle)

    result = []
    for rva in sorted(rows):
        row = rows[rva]
        roles_for_row = sorted(row["roles"])
        direct = sorted(row["directNeedles"])
        next_hops = sorted(row["nextHopNeedles"])
        result.append({
            "functionRva": rva,
            "roles": roles_for_row,
            "roleCount": len(roles_for_row),
            "directNeedles": direct,
            "nextHopNeedles": next_hops,
            "crossRole": len(roles_for_row) >= 2,
            "registrationCollisionRisk": len(direct) >= 2,
        })
    return result


def assess_hp_native_evidence(native: dict[str, Any]) -> dict[str, Any]:
    """Keep exact playable HP APIs separate from generic HP method-name anchors."""
    evidence = _native_function_evidence(native)
    exact_needles = (
        *STATUS_NEEDLES,
        *PLAYER_MAX_READ_NEEDLES,
        *PLAYER_CURRENT_READ_NEEDLES,
        *PLAYER_MAX_WRITE_NEEDLES,
        *PLAYER_CURRENT_WRITE_NEEDLES,
    )
    hit_counts = {
        needle: sum(
            len(hit.get("leaRipXrefs", ()))
            for hit in next((row for row in native.get("needles", ()) if row.get("needle") == needle), {}).get("hits", ())
        )
        for needle in NATIVE_NEEDLES
    }

    status = _functions(evidence, STATUS_NEEDLES)
    max_read = _functions(evidence, PLAYER_MAX_READ_NEEDLES)
    current_read = _functions(evidence, PLAYER_CURRENT_READ_NEEDLES)
    max_write = _functions(evidence, PLAYER_MAX_WRITE_NEEDLES)
    current_write = _functions(evidence, PLAYER_CURRENT_WRITE_NEEDLES)
    generic = _functions(evidence, GENERIC_HP_NEEDLES)

    correlations = {
        "maxWriteToMaxRead": sorted(max_write & max_read),
        "maxWriteToStatus": sorted(max_write & status),
        "currentWriteToCurrentRead": sorted(current_write & current_read),
        "maxWriteToCurrentWrite": sorted(max_write & current_write),
        "statusToMaxRead": sorted(status & max_read),
    }
    blockers = []
    if not max_write:
        blockers.append("player-max-hp-setter-function-unresolved")
    if not current_write:
        blockers.append("player-current-hp-clamp-setter-function-unresolved")
    if not max_read:
        blockers.append("player-max-hp-read-function-unresolved")
    if not current_read:
        blockers.append("player-current-hp-read-function-unresolved")
    if not status:
        blockers.append("composed-player-status-function-unresolved")
    if max_write and max_read and not correlations["maxWriteToMaxRead"]:
        blockers.append("max-hp-setter-reader-link-unvalidated")
    if current_write and current_read and not correlations["currentWriteToCurrentRead"]:
        blockers.append("current-hp-clamp-reader-writer-link-unvalidated")
    blockers.extend((
        "authoritative-max-hp-recalculation-interception-unvalidated",
        "playable-only-scope-unvalidated",
        "current-hp-clamp-semantics-unvalidated",
    ))

    clusters = _role_clusters(evidence)
    return {
        "implementationReady": False,
        "blockers": blockers,
        "needleXrefCounts": hit_counts,
        "exactPlayerNeedles": list(exact_needles),
        "genericCorrelationNeedles": list(GENERIC_HP_NEEDLES),
        "functionEvidence": evidence,
        "functionCorrelations": correlations,
        "functionClusters": clusters,
        "crossRoleFunctionCount": sum(1 for row in clusters if row["crossRole"]),
        "genericAnchorFunctions": sorted(generic),
        "notes": [
            "BPSetPlayerHPMax/BPSetPlayerHP and the BPGetPlayer*/GetCharaHP* families are exact playable/final-status research anchors; generic GetHP/GetHPMax can never satisfy a required player API role.",
            "Only exact .pdata function owners and their bounded one-hop code targets participate in correlations; padding-heuristic owners are ignored.",
            "Shared reflected-string owner functions can be Unreal registration glue. Multi-name direct owners are tagged registrationCollisionRisk rather than promoted to runtime hooks.",
            "Even a cross-role exact function remains research-only until the installed build proves it owns final playable max-HP recomputation and current-HP clamping with enemies excluded.",
        ],
    }


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
    native_assessment = assess_hp_native_evidence(native)
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
        "nativeAssessment": native_assessment,
        "knownContracts": {
            "finalStatusType": "FEndPlayerStatus.HPMax",
            "finalStatusGetter": "UEndMenuBPAPI::BPGetPlayerStatus(EPlayerType)",
            "hypotheticalEquipmentGetter": "UEndMenuBPAPI::BPGetPlayerStatusWithEquipment(...)",
            "hypotheticalMateriaGetter": "UEndMenuBPAPI::BPGetPlayerStatusWithMateria(...)",
            "directMaxGetter": "UEndMenuBPAPI::BPGetPlayerHPMax(EPlayerType)",
            "directCurrentGetter": "UEndMenuBPAPI::BPGetPlayerHP(EPlayerType)",
            "maxSetter": "UEndMenuBPAPI::BPSetPlayerHPMax(EPlayerType,int32)",
            "currentSetter": "UEndMenuBPAPI::BPSetPlayerHP(EPlayerType,int32)",
            "battleCharaMaxGetter": "UEndBattleAPI::GetCharaHPMax(...) research anchor",
            "battleCharaCurrentGetter": "UEndBattleAPI::GetCharaHP(...) research anchor",
            "battleControllerMaxGetter": "AEndBattleAIController::GetHPMax() generic correlation only",
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