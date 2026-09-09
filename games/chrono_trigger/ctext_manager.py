"""Safe, opt-in deployment of Chrono Trigger projects through CTExt.

This module deliberately does not install or replace runtime DLLs.  It only
operates when an existing CTExt configuration has the documented
``mods.enabled`` / ``mods.load_order`` shape, and it only removes deployed files
recorded in Lexeditor's own manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
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
    if project is not None:
        deployed_name = project.name
        candidate = mods / deployed_name
        deployed_path = str(candidate)
        try:
            same = project == candidate.resolve()
        except OSError:
            same = False
        deployed = same or (candidate / DEPLOY_MANIFEST).is_file()
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
        "automaticInstall": False,
    }


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _enable_mod(game_root: Path, mod_name: str) -> None:
    game = Path(game_root)
    config_path = game / CONFIG_NAME
    config, error = _read_config(game)
    if config is None:
        raise RuntimeError(error)
    backup = game / CONFIG_BACKUP
    if not backup.exists():
        shutil.copy2(config_path, backup)
    mods = config["mods"]
    mods["enabled"] = True
    if mod_name not in mods["load_order"]:
        mods["load_order"].append(mod_name)
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


def deploy_project(game_root: Path, project_root: Path) -> dict:
    """Mirror one project into ``mods/<project name>`` and activate it in CTExt."""
    game = Path(game_root).resolve()
    project = Path(project_root).resolve()
    if not project.is_dir():
        raise ValueError(f"Chrono Trigger project directory does not exist: {project}")
    if project.name in {"", ".", ".."}:
        raise ValueError("Chrono Trigger project needs a usable folder name")

    # Validate CTExt before copying anything.  Unknown config shapes fail closed.
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
    manifest_path = destination / DEPLOY_MANIFEST
    previous: dict = {}
    if destination.exists() and not source_is_destination:
        if not manifest_path.is_file():
            raise RuntimeError(
                f"CTExt mod folder already exists and is not Lexeditor-owned: {destination}"
            )
        try:
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Lexeditor deployment manifest is unreadable: {error}") from error
        if previous.get("source") != str(project):
            raise RuntimeError(
                f"CTExt mod folder belongs to a different Lexeditor project: {destination}"
            )

    files = _project_files(project)
    if not source_is_destination:
        destination.mkdir(parents=True, exist_ok=True)
        previous_files = previous.get("files", []) if isinstance(previous.get("files", []), list) else []
        for relative in previous_files:
            if not isinstance(relative, str) or relative in files:
                continue
            target = (destination / relative).resolve()
            if destination in target.parents and target.is_file():
                target.unlink()
        for relative, source in files.items():
            target = (destination / relative).resolve()
            if destination not in target.parents:
                raise ValueError(f"Project file escaped deployment root: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + ".tmp")
            shutil.copy2(source, temporary)
            temporary.replace(target)
        _atomic_json(manifest_path, {
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
