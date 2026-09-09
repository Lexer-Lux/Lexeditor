"""Conservative Bannerlord project-asset deployment.

C# build output remains the MSBuild project's responsibility. Lexeditor fills
Bannerlord's non-binary deployment gap by synchronizing owned descriptors,
ModuleData, and GUI assets without deleting anything from the installed module.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil

from . import paths
from .game_launch import installed_modules
from .module_data import read_submodule


_RUNTIME_STATE_FILES = {
    "ModuleData/custom_skill_effects.json",
    "ModuleData/custom_skill_xp_sources.json",
}
_MODULE_ID = re.compile(r"[A-Za-z0-9_.-]+")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _module_id(project: Path) -> str:
    descriptor = paths.contained_project_path(project, "SubModule.xml", require_file=True)
    module_id = str(read_submodule(descriptor).get("id") or "").strip()
    if not module_id:
        raise ValueError("Project SubModule.xml has no module Id")
    if not _MODULE_ID.fullmatch(module_id):
        raise ValueError(f"Module Id is unsafe as an install folder name: {module_id}")
    return module_id


def deploy_target(project: Path, game_root: Path | None = None) -> tuple[str, Path, bool]:
    """Resolve an existing installed module by Id, or a safe new Modules/Id folder."""
    game = (game_root or paths.game_root()).resolve()
    executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"Bannerlord executable not found: {executable}")
    module_id = _module_id(project)
    modules_root = paths.modules_root(game).resolve()
    if not modules_root.is_dir():
        raise FileNotFoundError(f"Bannerlord Modules directory not found: {modules_root}")
    existing = installed_modules(game)
    target = existing.get(module_id)
    if target is not None:
        target = target.resolve()
        if modules_root not in target.parents:
            raise ValueError("Resolved existing Bannerlord module deployment path escaped the Modules folder")
        return module_id, target, True
    target = (modules_root / module_id).resolve()
    if modules_root not in target.parents:
        raise ValueError("Resolved Bannerlord module deployment path escaped the Modules folder")
    return module_id, target, False


def _source_files(project: Path) -> list[tuple[str, Path]]:
    project = project.resolve()
    candidates = [project / "SubModule.xml"]
    for folder in (project / "GUI", project / "ModuleData"):
        if folder.is_dir():
            candidates.extend(path for path in folder.rglob("*") if path.is_file())

    result = []
    seen = set()
    for source in candidates:
        resolved = source.resolve()
        if resolved != project and project not in resolved.parents:
            raise ValueError(f"Deployment source escaped project root: {source}")
        relative = resolved.relative_to(project).as_posix()
        if relative in _RUNTIME_STATE_FILES:
            continue
        if relative.endswith(".lexeditor.bak") or relative.endswith(".lexeditor.tmp"):
            continue
        if relative in seen:
            continue
        seen.add(relative)
        result.append((relative, resolved))
    return sorted(result, key=lambda item: item[0].casefold())


def _deployment_plan(project: Path, target: Path) -> list[dict]:
    """Validate every semantic deployment destination before the first write."""
    if target.exists() and not target.is_dir():
        raise ValueError(f"Bannerlord module deployment target is not a directory: {target}")

    plan = []
    for relative, source in _source_files(project):
        destination = (target / relative).resolve()
        if target != destination and target not in destination.parents:
            raise ValueError(f"Deployment destination escaped module folder: {relative}")
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Deployment destination is not a file: {destination}")

        had_destination = destination.is_file()
        unchanged = had_destination and _hash(source) == _hash(destination)
        backup = destination.with_name(destination.name + ".lexeditor.bak")
        temporary = destination.with_name(destination.name + ".lexeditor.tmp")
        if not unchanged:
            # clear_write_helper intentionally rejects directory-like helper
            # entries. Detect all such semantic failures now, before an earlier
            # asset in the plan can be modified.
            for helper in (backup, temporary):
                if helper.is_dir():
                    raise ValueError(f"Bannerlord write helper path is a directory: {helper}")

        plan.append(
            {
                "relative": relative,
                "source": source,
                "destination": destination,
                "backup": backup,
                "temporary": temporary,
                "hadDestination": had_destination,
                "unchanged": unchanged,
            }
        )
    return plan


def _cleanup_staged(rows: list[dict]) -> list[str]:
    errors = []
    for row in rows:
        temporary = row["temporary"]
        try:
            temporary.unlink(missing_ok=True)
        except OSError as error:
            errors.append(f"{temporary}: {error}")
    return errors


def _rollback_committed(rows: list[dict]) -> list[str]:
    errors = []
    for row in reversed(rows):
        destination = row["destination"]
        try:
            if row["hadDestination"]:
                temporary = row["temporary"]
                paths.clear_write_helper(temporary)
                shutil.copy2(row["backup"], temporary)
                temporary.replace(destination)
            else:
                destination.unlink(missing_ok=True)
        except Exception as error:  # best-effort rollback must report every failure
            errors.append(f"{row['relative']}: {error}")
    return errors


def sync_project_assets(project: Path, game_root: Path | None = None) -> dict:
    """Copy owned non-binary module assets additively with staged commit/rollback."""
    project = project.resolve()
    module_id, target, existed = deploy_target(project, game_root)
    plan = _deployment_plan(project, target)
    changed = [row for row in plan if not row["unchanged"]]
    unchanged = [row["relative"] for row in plan if row["unchanged"]]

    # No deployment directory or destination is created until all sources,
    # destinations, and directory-like predictable helper entries have passed
    # semantic validation.
    target.mkdir(parents=True, exist_ok=True)

    # Stage every incoming asset before touching a deployed destination. A read
    # or copy failure therefore cannot leave an earlier asset committed.
    staged = []
    try:
        for row in changed:
            destination = row["destination"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            paths.clear_write_helper(row["temporary"])
            shutil.copy2(row["source"], row["temporary"])
            staged.append(row)
    except Exception as error:
        cleanup_errors = _cleanup_staged(staged + [row for row in changed if row not in staged])
        if cleanup_errors:
            raise RuntimeError(
                "Bannerlord asset staging failed and temporary files could not all be cleaned up: "
                + "; ".join(cleanup_errors)
            ) from error
        raise

    # Create all backups before the first destination replacement. If backup
    # creation fails, deployed content is still untouched and staged temps are
    # discarded.
    backups = []
    try:
        for row in changed:
            if not row["hadDestination"]:
                continue
            paths.clear_write_helper(row["backup"])
            shutil.copy2(row["destination"], row["backup"])
            backups.append(row["backup"].relative_to(target).as_posix())
    except Exception as error:
        cleanup_errors = _cleanup_staged(changed)
        if cleanup_errors:
            raise RuntimeError(
                "Bannerlord asset backup staging failed and temporary files could not all be cleaned up: "
                + "; ".join(cleanup_errors)
            ) from error
        raise

    copied = []
    committed = []
    try:
        for row in changed:
            row["temporary"].replace(row["destination"])
            committed.append(row)
            copied.append(row["relative"])
    except Exception as error:
        rollback_errors = _rollback_committed(committed)
        cleanup_errors = _cleanup_staged(changed)
        problems = rollback_errors + cleanup_errors
        if problems:
            raise RuntimeError(
                "Bannerlord asset commit failed and rollback was incomplete: "
                + "; ".join(problems)
            ) from error
        raise

    return {
        "moduleId": module_id,
        "target": str(target),
        "existingModule": existed,
        "copied": copied,
        "unchanged": unchanged,
        "backups": backups,
        "excludedRuntimeState": sorted(_RUNTIME_STATE_FILES),
        "deleted": [],
    }
