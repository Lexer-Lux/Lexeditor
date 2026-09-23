"""Structured editing for LexerSkillTweaks deployed runtime balance overrides."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil

from . import paths
from .deploy_data import deploy_target
from .perk_data import read_xp_source_definitions
from .skill_data import read_effect_definitions
from .source_revision import optional_source_revision, require_optional_source_revision


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
    game = (game_root or paths.game_root()).resolve()
    module_id, deployed, existed = deploy_target(project.resolve(), game)
    if not existed:
        raise RuntimeError(
            f"Bannerlord module {module_id} is not deployed under {paths.modules_root(game)}. "
            "Build/deploy it before editing runtime overrides."
        )
    return module_id, deployed.resolve()


def _paths(project: Path, game_root: Path | None = None) -> tuple[Path, Path, Path]:
    _module_id, deployed = _deployed_module(project, game_root)
    module_data = (deployed / "ModuleData").resolve()
    if deployed not in module_data.parents:
        raise ValueError("Resolved Bannerlord runtime ModuleData path escaped the deployed module")
    effects_path = (module_data / "custom_skill_effects.json").resolve()
    xp_path = (module_data / "custom_skill_xp_sources.json").resolve()
    for target in (effects_path, xp_path):
        if module_data not in target.parents:
            raise ValueError("Resolved Bannerlord runtime override path escaped ModuleData")
    return module_data, effects_path, xp_path


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
        "effectsHash": optional_source_revision(effects_path),
        "xpSourcesHash": optional_source_revision(xp_path),
        "effects": effects,
        "xpSources": xp_sources,
        "unknownEffectKeys": sorted(set(effects_json) - known_effects),
        "unknownXpKeys": sorted(set(xp_json) - known_xp),
    }


def _runtime_write_plan(entries: list[tuple[str, Path, dict, str]]) -> list[dict]:
    plan = []
    for key, destination, value, expected in entries:
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Runtime override destination is not a file: {destination}")
        backup = destination.with_name(destination.name + ".lexeditor.bak")
        temporary = destination.with_name(destination.name + ".lexeditor.tmp")
        for helper in (backup, temporary):
            if helper.is_dir():
                raise ValueError(f"Bannerlord write helper path is a directory: {helper}")
        plan.append({
            "key": key,
            "destination": destination,
            "backup": backup,
            "temporary": temporary,
            "hadDestination": destination.is_file(),
            "expected": expected,
            "content": (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        })
    return plan


def _cleanup_runtime_staged(rows: list[dict]) -> list[str]:
    errors = []
    for row in rows:
        try:
            row["temporary"].unlink(missing_ok=True)
        except OSError as error:
            errors.append(f"{row['temporary']}: {error}")
    return errors


def _rollback_runtime_committed(rows: list[dict]) -> list[str]:
    errors = []
    for row in reversed(rows):
        destination = row["destination"]
        try:
            if row["hadDestination"]:
                if not row["backup"].is_file():
                    raise RuntimeError(f"Runtime rollback backup is missing: {row['backup']}")
                paths.clear_write_helper(row["temporary"])
                shutil.copy2(row["backup"], row["temporary"])
                row["temporary"].replace(destination)
            else:
                destination.unlink(missing_ok=True)
        except Exception as error:
            errors.append(f"{row['key']}: {error}")
    return errors


def _write_json_transaction(entries: list[tuple[str, Path, dict, str]]) -> dict[str, str]:
    plan = _runtime_write_plan(entries)
    if not plan:
        return {}

    # Stage every candidate before touching a destination or backup.
    try:
        for row in plan:
            row["destination"].parent.mkdir(parents=True, exist_ok=True)
            paths.clear_write_helper(row["temporary"])
            row["temporary"].write_bytes(row["content"])
    except Exception as error:
        cleanup_errors = _cleanup_runtime_staged(plan)
        if cleanup_errors:
            raise RuntimeError(
                "Bannerlord runtime override staging failed and temporary files could not all be cleaned up: "
                + "; ".join(cleanup_errors)
            ) from error
        raise

    # A staged candidate may take non-trivial time on a slow disk. Revalidate
    # the loaded versions before making backups or replacing either target.
    try:
        for row in plan:
            require_optional_source_revision(row["destination"], row["expected"])
    except Exception:
        _cleanup_runtime_staged(plan)
        raise

    backups: dict[str, str] = {}
    try:
        for row in plan:
            paths.clear_write_helper(row["backup"])
            if row["hadDestination"]:
                shutil.copy2(row["destination"], row["backup"])
                backups[row["key"]] = str(row["backup"])
            else:
                backups[row["key"]] = ""
    except Exception as error:
        cleanup_errors = _cleanup_runtime_staged(plan)
        if cleanup_errors:
            raise RuntimeError(
                "Bannerlord runtime override backup staging failed and temporary files could not all be cleaned up: "
                + "; ".join(cleanup_errors)
            ) from error
        raise

    # Detect edits that raced the backup phase itself. Destinations are still
    # untouched, so a stale save can still abort cleanly here.
    try:
        for row in plan:
            require_optional_source_revision(row["destination"], row["expected"])
    except Exception:
        _cleanup_runtime_staged(plan)
        raise

    committed = []
    try:
        for row in plan:
            row["temporary"].replace(row["destination"])
            committed.append(row)
    except Exception as error:
        rollback_errors = _rollback_runtime_committed(committed)
        cleanup_errors = _cleanup_runtime_staged(plan)
        problems = rollback_errors + cleanup_errors
        if problems:
            raise RuntimeError(
                "Bannerlord runtime override commit failed and rollback was incomplete: "
                + "; ".join(problems)
            ) from error
        raise
    return backups


def save_runtime_overrides(project: Path, payload: dict, game_root: Path | None = None) -> dict:
    """Replace only known override keys; preserve unknown keys written by other tools/versions."""
    _module_id, _deployed = _deployed_module(project, game_root)
    _module_data, effects_path, xp_path = _paths(project, game_root)
    effect_edits = list(payload.get("effects") or [])
    xp_edits = list(payload.get("xpSources") or [])
    if effect_edits:
        require_optional_source_revision(effects_path, payload.get("effectsHash"))
    if xp_edits:
        require_optional_source_revision(xp_path, payload.get("xpSourcesHash"))
    current = read_runtime_overrides(project, game_root)
    known_effects = {row["id"]: row for row in current["effects"]}
    known_xp = {row["id"]: row for row in current["xpSources"]}
    effect_values = _load_object(effects_path)
    xp_values = _load_object(xp_path)
    changed_effects = 0
    changed_xp = 0

    for edit in effect_edits:
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

    for edit in xp_edits:
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

    # Narrow the external-write race: verify the loaded revision again
    # immediately before the first backup/temp/target mutation.
    if changed_effects:
        require_optional_source_revision(effects_path, payload.get("effectsHash"))
    if changed_xp:
        require_optional_source_revision(xp_path, payload.get("xpSourcesHash"))

    writes = []
    if changed_effects:
        writes.append(("effects", effects_path, effect_values, str(payload.get("effectsHash") or "")))
    if changed_xp:
        writes.append(("xpSources", xp_path, xp_values, str(payload.get("xpSourcesHash") or "")))
    backups = _write_json_transaction(writes)
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
