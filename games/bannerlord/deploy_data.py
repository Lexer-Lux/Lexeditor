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
    descriptor = project / "SubModule.xml"
    if not descriptor.is_file():
        raise FileNotFoundError(descriptor)
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
        return module_id, target.resolve(), True
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


def sync_project_assets(project: Path, game_root: Path | None = None) -> dict:
    """Copy owned non-binary module assets additively, backing up overwritten files."""
    project = project.resolve()
    module_id, target, existed = deploy_target(project, game_root)
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    unchanged = []
    backups = []

    for relative, source in _source_files(project):
        destination = (target / relative).resolve()
        if target != destination and target not in destination.parents:
            raise ValueError(f"Deployment destination escaped module folder: {relative}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and _hash(source) == _hash(destination):
            unchanged.append(relative)
            continue
        if destination.exists() and not destination.is_file():
            raise ValueError(f"Deployment destination is not a file: {destination}")
        if destination.is_file():
            backup = destination.with_name(destination.name + ".lexeditor.bak")
            shutil.copy2(destination, backup)
            backups.append(backup.relative_to(target).as_posix())
        temporary = destination.with_name(destination.name + ".lexeditor.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(destination)
        copied.append(relative)

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
