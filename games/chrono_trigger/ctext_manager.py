"""Safe, opt-in deployment of Chrono Trigger projects through CTExt.

This module deliberately does not install or replace runtime DLLs. It only
operates when an existing CTExt configuration has the documented
``mods.enabled`` / ``mods.load_order`` shape, and it only removes deployed files
recorded in Lexeditor's own manifest.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import shutil


CONFIG_NAME = "ctext.json"
CTEXT_DLL = "ctext.dll"
PROXY_DLL = "sqlite3.dll"
MODS_DIR = "mods"
DEPLOY_MANIFEST = ".lexeditor-deployment.json"
CONFIG_BACKUP = "ctext.json.lexeditor.bak"


def _read_config(game_root: Path) -> tuple[dict | None, str]:
    path = Path(game_root) / CONFIG_NAME
    if not path.is_file():
        return None, f"CTExt config is missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f"CTExt config could not be read: {error}"
    if not isinstance(payload, dict):
        return None, "CTExt config root must be a JSON object"
    mods = payload.get("mods")
    if not isinstance(mods, dict):
        return None, "CTExt config has no mods object"
    if not isinstance(mods.get("enabled"), bool):
        return None, "CTExt config mods.enabled is not a boolean"
    order = mods.get("load_order")
    if not isinstance(order, list) or any(not isinstance(value, str) or not value for value in order):
        return None, "CTExt config mods.load_order is not a list of mod folder names"
    return payload, ""


def status(game_root: Path, project_root: Path | None = None) -> dict:
    game = Path(game_root)
    config, config_error = _read_config(game)
    order = config["mods"]["load_order"] if config is not None else []
    project = Path(project_root).resolve() if project_root else None
    mods = (game / MODS_DIR).resolve()
    deployed_name = None
    deployed_path = None
    deployed = False
    active = False
    direct_project = False
    if project is not None:
        deployed_name = project.name
        candidate = mods / deployed_name
        deployed_path = str(candidate)
        try:
            direct_project = project == candidate.resolve()
        except OSError:
            direct_project = False
        deployed = direct_project or (candidate / DEPLOY_MANIFEST).is_file()
        active = deployed_name in order if config is not None else False
    return {
        "installed": (game / CTEXT_DLL).is_file() and (game / PROXY_DLL).is_file(),
        "runtimeDll": str(game / CTEXT_DLL),
        "proxyDll": str(game / PROXY_DLL),
        "configPath": str(game / CONFIG_NAME),
        "configValid": config is not None,
        "configError": config_error,
        "modsEnabled": bool(config and config["mods"]["enabled"]),
        "loadOrder": list(order),
        "projectName": deployed_name,
        "deployedPath": deployed_path,
        "deployed": deployed,
        "active": active,
        "directProject": direct_project,
        "automaticInstall": False,
    }


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _backup_config(game: Path, config_path: Path) -> None:
    backup = game / CONFIG_BACKUP
    if not backup.exists():
        shutil.copy2(config_path, backup)


def _enable_mod(game_root: Path, mod_name: str) -> None:
    game = Path(game_root)
    config_path = game / CONFIG_NAME
    config, error = _read_config(game)
    if config is None:
        raise RuntimeError(error)
    _backup_config(game, config_path)
    mods = config["mods"]
    mods["enabled"] = True
    if mod_name not in mods["load_order"]:
        mods["load_order"].append(mod_name)
    _atomic_json(config_path, config)


def _disable_mod(game_root: Path, mod_name: str) -> None:
    game = Path(game_root)
    config_path = game / CONFIG_NAME
    config, error = _read_config(game)
    if config is None:
        raise RuntimeError(error)
    _backup_config(game, config_path)
    mods = config["mods"]
    mods["load_order"] = [value for value in mods["load_order"] if value != mod_name]
    # Do not set mods.enabled=false: other CTExt mods may still depend on the
    # global switch even if this project's name was the only listed entry.
    _atomic_json(config_path, config)


def _project_files(project_root: Path) -> dict[str, Path]:
    root = project_root.resolve()
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Chrono Trigger project contains a symlink; deployment refuses it: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == DEPLOY_MANIFEST or relative.startswith(".git/"):
            continue
        files[relative] = path
    return files


def _read_owned_manifest(destination: Path, project: Path) -> dict:
    manifest_path = destination / DEPLOY_MANIFEST
    if not manifest_path.is_file():
        raise RuntimeError(f"CTExt mod folder is not Lexeditor-owned: {destination}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Lexeditor deployment manifest is unreadable: {error}") from error
    if payload.get("format") != 1 or payload.get("source") != str(project):
        raise RuntimeError(f"CTExt mod folder belongs to a different Lexeditor project: {destination}")
    files = payload.get("files")
    if not isinstance(files, list) or any(not isinstance(value, str) for value in files):
        raise RuntimeError("Lexeditor deployment manifest has an invalid files list")
    for relative in files:
        parts = PurePosixPath(relative).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise RuntimeError(f"Lexeditor deployment manifest contains an unsafe path: {relative}")
    return payload


def deploy_project(game_root: Path, project_root: Path) -> dict:
    """Mirror one project into ``mods/<project name>`` and activate it in CTExt."""
    game = Path(game_root).resolve()
    project = Path(project_root).resolve()
    if not project.is_dir():
        raise ValueError(f"Chrono Trigger project directory does not exist: {project}")
    if project.name in {"", ".", ".."}:
        raise ValueError("Chrono Trigger project needs a usable folder name")

    config, error = _read_config(game)
    if config is None:
        raise RuntimeError(error)
    if not (game / CTEXT_DLL).is_file() or not (game / PROXY_DLL).is_file():
        raise RuntimeError("CTExt runtime is not installed; Lexeditor will not install or replace its DLLs automatically")

    mods_root = (game / MODS_DIR).resolve()
    mods_root.mkdir(parents=True, exist_ok=True)
    destination = (mods_root / project.name).resolve()
    if mods_root not in destination.parents:
        raise ValueError("CTExt deployment path escaped the mods directory")

    source_is_destination = project == destination
    previous: dict = {}
    if destination.exists() and not source_is_destination:
        previous = _read_owned_manifest(destination, project)

    files = _project_files(project)
    if not source_is_destination:
        destination.mkdir(parents=True, exist_ok=True)
        previous_files = previous.get("files", []) if isinstance(previous.get("files", []), list) else []
        for relative in previous_files:
            if relative in files:
                continue
            target = (destination / Path(*PurePosixPath(relative).parts)).resolve()
            if destination in target.parents and target.is_file() and not target.is_symlink():
                target.unlink()
        for relative, source in files.items():
            target = (destination / Path(*PurePosixPath(relative).parts)).resolve()
            if destination not in target.parents:
                raise ValueError(f"Project file escaped deployment root: {relative}")
            if target.is_symlink():
                raise RuntimeError(f"Deployment target is a symlink: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            shutil.copy2(source, temporary)
            temporary.replace(target)
        _atomic_json(destination / DEPLOY_MANIFEST, {
            "format": 1,
            "source": str(project),
            "files": sorted(files),
        })

    _enable_mod(game, project.name)
    result = status(game, project)
    result.update({
        "deployed": True,
        "active": True,
        "deployedPath": str(destination),
        "copiedFiles": 0 if source_is_destination else len(files),
    })
    return result


def deactivate_project(game_root: Path, project_root: Path) -> dict:
    """Remove this project's folder name from CTExt load order only."""
    game = Path(game_root).resolve()
    project = Path(project_root).resolve()
    _disable_mod(game, project.name)
    result = status(game, project)
    result.update({"deactivated": True, "removedFiles": 0})
    return result


def undeploy_project(game_root: Path, project_root: Path) -> dict:
    """Deactivate and remove only files named in this project's Lexeditor manifest.

    A project already stored directly in ``mods/<name>`` is only deactivated;
    Lexeditor never treats the user's source project as disposable deployment
    output.
    """
    game = Path(game_root).resolve()
    project = Path(project_root).resolve()
    mods_root = (game / MODS_DIR).resolve()
    destination = (mods_root / project.name).resolve()
    if mods_root not in destination.parents:
        raise ValueError("CTExt undeploy path escaped the mods directory")

    direct_project = project == destination
    manifest = None
    if destination.exists() and not direct_project:
        manifest = _read_owned_manifest(destination, project)

    # Deactivate only after all ownership/path checks have succeeded, but before
    # deleting files. A cleanup failure therefore leaves a harmless inactive mod.
    _disable_mod(game, project.name)

    removed = 0
    if manifest is not None:
        for relative in manifest["files"]:
            target = (destination / Path(*PurePosixPath(relative).parts)).resolve()
            if destination not in target.parents:
                raise RuntimeError(f"Manifest path escaped deployment root: {relative}")
            if target.is_symlink():
                raise RuntimeError(f"Refusing to remove symlinked deployed file: {target}")
            if target.is_file():
                target.unlink()
                removed += 1
        manifest_path = destination / DEPLOY_MANIFEST
        if manifest_path.is_file() and not manifest_path.is_symlink():
            manifest_path.unlink()
        for directory in sorted((path for path in destination.rglob("*") if path.is_dir()),
                                key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass

    result = status(game, project)
    result.update({
        "undeployed": not direct_project,
        "deactivated": True,
        "removedFiles": removed,
        "directProjectPreserved": direct_project,
    })
    return result
