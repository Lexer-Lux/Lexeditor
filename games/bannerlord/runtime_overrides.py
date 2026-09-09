"""Structured editing for LexerSkillTweaks deployed runtime balance overrides."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil

from . import paths
from .game_launch import selected_module
from .perk_data import read_xp_source_definitions
from .skill_data import read_effect_definitions


def _load_object(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Runtime override file must contain a JSON object: {path}")
    return value


def _finite(value, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    if abs(number) > 1_000_000_000:
        raise ValueError(f"{label} magnitude is too large")
    return number


def _xp_amount(value, label: str) -> float:
    number = _finite(value, label)
    if number < 0:
        raise ValueError(f"{label} cannot be negative")
    return number


def _deployed_module(project: Path, game_root: Path | None = None) -> tuple[str, Path]:
    return selected_module((game_root or paths.game_root()).resolve(), project.resolve())


def _paths(project: Path, game_root: Path | None = None) -> tuple[Path, Path, Path]:
    _module_id, deployed = _deployed_module(project, game_root)
    module_data = deployed / "ModuleData"
    return (
        module_data,
        module_data / "custom_skill_effects.json",
        module_data / "custom_skill_xp_sources.json",
    )


def read_runtime_overrides(project: Path, game_root: Path | None = None) -> dict:
    """Merge source defaults with deployed JSON overrides without changing either."""
    module_id, deployed = _deployed_module(project, game_root)
    module_data, effects_path, xp_path = _paths(project, game_root)
    effects_json = _load_object(effects_path)
    xp_json = _load_object(xp_path)

    effect_definitions = read_effect_definitions(project)
    xp_definitions = read_xp_source_definitions(project)
    known_effects = {row["id"] for row in effect_definitions.get("effects", [])}
    known_xp = {row["id"] for row in xp_definitions.get("sources", [])}

    effects = []
    for row in effect_definitions.get("effects", []):
        raw = effects_json.get(row["id"])
        overridden = raw is not None
        if overridden:
            if not isinstance(raw, dict) or set(raw) != {"low", "high"}:
                raise ValueError(f"Runtime effect {row['id']} must contain exactly low/high")
            low = _finite(raw["low"], f"{row['id']} low")
            high = _finite(raw["high"], f"{row['id']} high")
        else:
            low, high = float(row["defaultLow"]), float(row["defaultHigh"])
        effects.append({
            "id": row["id"], "skillId": row["skillId"], "label": row["label"],
            "suffix": row.get("suffix", ""), "defaultLow": row["defaultLow"],
            "defaultHigh": row["defaultHigh"], "overridden": overridden,
            "low": low, "high": high,
        })

    xp_sources = []
    for row in xp_definitions.get("sources", []):
        overridden = row["id"] in xp_json
        amount = _xp_amount(xp_json[row["id"]], row["id"]) if overridden else float(row["defaultAmount"])
        xp_sources.append({
            "id": row["id"], "skillId": row["skillId"], "label": row["label"],
            "defaultAmount": row["defaultAmount"], "overridden": overridden,
            "amount": amount,
        })

    return {
        "available": bool(effect_definitions.get("available") or xp_definitions.get("available")),
        "moduleId": module_id,
        "deployedRoot": str(deployed),
        "moduleDataRoot": str(module_data),
        "effectsPath": str(effects_path),
        "xpSourcesPath": str(xp_path),
        "effects": effects,
        "xpSources": xp_sources,
        "unknownEffectKeys": sorted(set(effects_json) - known_effects),
        "unknownXpKeys": sorted(set(xp_json) - known_xp),
    }


def _write_json(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".lexeditor.bak")
    if path.is_file():
        shutil.copy2(path, backup)
    temporary = path.with_name(path.name + ".lexeditor.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return str(backup) if backup.is_file() else ""


def save_runtime_overrides(project: Path, payload: dict, game_root: Path | None = None) -> dict:
    """Replace only known override keys; preserve unknown keys written by other tools/versions."""
    _module_id, _deployed = _deployed_module(project, game_root)
    _module_data, effects_path, xp_path = _paths(project, game_root)
    current = read_runtime_overrides(project, game_root)
    known_effects = {row["id"]: row for row in current["effects"]}
    known_xp = {row["id"]: row for row in current["xpSources"]}
    effect_values = _load_object(effects_path)
    xp_values = _load_object(xp_path)
    changed_effects = 0
    changed_xp = 0

    for edit in list(payload.get("effects") or []):
        effect_id = str(edit.get("id") or "")
        if effect_id not in known_effects:
            raise ValueError(f"Unknown runtime effect ID: {effect_id}")
        if bool(edit.get("overridden")):
            value = {
                "low": _finite(edit.get("low"), f"{effect_id} low"),
                "high": _finite(edit.get("high"), f"{effect_id} high"),
            }
            if effect_values.get(effect_id) != value:
                effect_values[effect_id] = value
                changed_effects += 1
        elif effect_id in effect_values:
            del effect_values[effect_id]
            changed_effects += 1

    for edit in list(payload.get("xpSources") or []):
        source_id = str(edit.get("id") or "")
        if source_id not in known_xp:
            raise ValueError(f"Unknown runtime XP source ID: {source_id}")
        if bool(edit.get("overridden")):
            amount = _xp_amount(edit.get("amount"), source_id)
            if xp_values.get(source_id) != amount:
                xp_values[source_id] = amount
                changed_xp += 1
        elif source_id in xp_values:
            del xp_values[source_id]
            changed_xp += 1

    backups = {}
    if changed_effects:
        backups["effects"] = _write_json(effects_path, effect_values)
    if changed_xp:
        backups["xpSources"] = _write_json(xp_path, xp_values)
    result = read_runtime_overrides(project, game_root)
    result.update({"saved": changed_effects + changed_xp, "backups": backups})
    return result


def augment_data_map(value: dict, runtime: dict) -> dict:
    rows = list(value.get("rows") or [])
    available = bool(runtime.get("available"))
    for key, filename, controls, path_key in (
        ("effects", "ModuleData/custom_skill_effects.json", "Deployed quantitative effect overrides", "effectsPath"),
        ("xp", "ModuleData/custom_skill_xp_sources.json", "Deployed custom skill XP overrides", "xpSourcesPath"),
    ):
        path = Path(runtime.get(path_key) or "")
        rows.append({
            "id": f"bannerlord-runtime-{key}", "filename": filename, "area": "Runtime",
            "controls": controls, "coverage": "structured" if available else "unavailable",
            "status": "integrated" if available else "not-integrated",
            "target": "runtime" if available else "", "targets": ["runtime"] if available else [],
            "openable": available, "sourceAvailable": path.is_file(), "sourcePath": str(path),
            "notes": "Structured deployed runtime override editor; disabling an override falls back to the C# source default."
            if available else "The selected module must be deployed before runtime overrides can be edited.",
        })
    return {**value, "rows": rows}
