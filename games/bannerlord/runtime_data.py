"""Installed Bannerlord module and dependency diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import paths
from .game_launch import module_load_order
from .module_data import is_singleplayer_module, read_submodule


_RUNTIME_STATE_FILES = {
    "custom_skill_effects.json",
    "custom_skill_xp_sources.json",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _installed_index(game_root: Path) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for folder in paths.installed_modules(game_root):
        descriptor = folder / "SubModule.xml"
        try:
            module = read_submodule(descriptor)
        except Exception as error:
            result[folder.name.casefold()] = {
                "id": folder.name,
                "name": folder.name,
                "version": "",
                "path": str(folder),
                "descriptorError": str(error),
            }
            continue
        module_id = str(module.get("id") or folder.name)
        result[module_id.casefold()] = {
            "id": module_id,
            "name": module.get("name") or module_id,
            "version": module.get("version") or "",
            "path": str(folder),
            "descriptorError": "",
        }
    return result


def _json_override(path: Path, nested: bool) -> dict:
    if not path.is_file():
        return {"path": str(path), "exists": False, "valid": True, "keys": 0, "error": ""}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("root must be a JSON object")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("all override keys must be strings")
            if nested:
                if not isinstance(item, dict) or set(item) != {"low", "high"}:
                    raise ValueError(f"{key} must contain exactly low/high")
                float(item["low"])
                float(item["high"])
            else:
                float(item)
        return {"path": str(path), "exists": True, "valid": True, "keys": len(value), "error": ""}
    except Exception as error:
        return {"path": str(path), "exists": True, "valid": False, "keys": 0, "error": str(error)}


def _asset_files(root: Path, *, runtime_state: bool = False) -> list[Path]:
    if not root.is_dir():
        return []
    result = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.name.endswith(".lexeditor.bak") or path.name.endswith(".lexeditor.tmp"):
            continue
        if runtime_state and relative.as_posix() in _RUNTIME_STATE_FILES:
            continue
        result.append(path)
    return sorted(result, key=lambda value: value.as_posix().casefold())


def _asset_status(project_root: Path, deployed_root: Path, *, runtime_state: bool = False) -> dict:
    sources = _asset_files(project_root, runtime_state=runtime_state)
    deployed = _asset_files(deployed_root, runtime_state=runtime_state)
    missing = []
    different = []
    for source in sources:
        relative = source.relative_to(project_root)
        target = deployed_root / relative
        if not target.is_file():
            missing.append(relative.as_posix())
        elif _sha256(source) != _sha256(target):
            different.append(relative.as_posix())
    return {
        "source": len(sources),
        "deployed": len(deployed),
        "missing": missing,
        "different": different,
        "inSync": not missing and not different,
    }


def deployment_status(project: Path, game_root: Path | None = None) -> dict:
    """Report whether the selected project is present and runnable in the game install."""
    game = (game_root or paths.game_root()).resolve()
    descriptor = project / "SubModule.xml"
    if not descriptor.is_file():
        return {
            "gameRoot": str(game),
            "projectRoot": str(project),
            "moduleId": "",
            "runnable": False,
            "inSync": False,
            "issues": [f"Missing project SubModule.xml: {descriptor}"],
            "dependencies": [],
            "binaries": [],
            "assets": {},
            "runtimeOverrides": {},
            "loadOrder": [],
            "playError": "Missing project SubModule.xml",
        }

    module = read_submodule(descriptor)
    module_id = str(module.get("id") or "").strip()
    installed = _installed_index(game)
    installed_module = installed.get(module_id.casefold()) if module_id else None
    deployed_root = Path(installed_module["path"]) if installed_module else paths.modules_root(game) / module_id
    deployed_descriptor = deployed_root / "SubModule.xml"

    issues: list[str] = []
    game_exe = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    if not game_exe.is_file():
        issues.append(f"Missing Bannerlord executable: {game_exe}")
    if not module_id:
        issues.append("Project SubModule.xml has no module ID")
    if not installed_module:
        issues.append(f"Module {module_id or '(no ID)'} is not installed under {paths.modules_root(game)}")

    dependency_rows = []
    missing_required = []
    version_mismatches = []
    for dependency in module.get("dependencies", []):
        dep_id = str(dependency.get("id") or "")
        found = installed.get(dep_id.casefold())
        optional = bool(dependency.get("optional"))
        required_version = str(dependency.get("dependentVersion") or "").strip()
        installed_version = str(found.get("version", "") or "").strip() if found else ""
        version_match = None
        if not found and not optional:
            missing_required.append(dep_id)
        if found and required_version:
            version_match = required_version.casefold() == installed_version.casefold()
            if not version_match:
                version_mismatches.append(
                    f"{dep_id} requires {required_version}, installed "
                    f"{installed_version or '(no version declared)'}"
                )
        dependency_rows.append(
            {
                "id": dep_id,
                "requiredVersion": required_version,
                "optional": optional,
                "installed": bool(found),
                "installedVersion": installed_version,
                "versionMatch": version_match,
                "path": found.get("path", "") if found else "",
            }
        )
    if missing_required:
        issues.append("Missing required dependencies: " + ", ".join(missing_required))
    if version_mismatches:
        issues.append(
            "Dependency version warning (Bannerlord launcher would warn before start): "
            + "; ".join(version_mismatches)
        )

    binaries = []
    missing_binaries = []
    for submodule in module.get("submodules", []):
        dll_name = str(submodule.get("dllName") or "").strip()
        if not dll_name:
            continue
        target = deployed_root / "bin" / "Win64_Shipping_Client" / dll_name
        exists = target.is_file()
        if not exists:
            missing_binaries.append(dll_name)
        stat = target.stat() if exists else None
        binaries.append(
            {
                "name": dll_name,
                "classType": submodule.get("classType") or "",
                "path": str(target),
                "exists": exists,
                "size": stat.st_size if stat else 0,
                "modifiedNs": stat.st_mtime_ns if stat else 0,
            }
        )
    if missing_binaries:
        issues.append("Missing deployed module binaries: " + ", ".join(missing_binaries))

    gui_status = _asset_status(project / "GUI", deployed_root / "GUI")
    module_data_status = _asset_status(
        project / "ModuleData",
        deployed_root / "ModuleData",
        runtime_state=True,
    )
    for label, status in (("GUI assets", gui_status), ("ModuleData assets", module_data_status)):
        if status["missing"]:
            issues.append(f"{len(status['missing'])} {label} file(s) are not deployed")
        if status["different"]:
            issues.append(f"{len(status['different'])} deployed {label} file(s) differ from the project")

    project_gui_xml = [path for path in _asset_files(project / "GUI") if path.suffix.casefold() == ".xml"]
    deployed_gui_xml = [path for path in _asset_files(deployed_root / "GUI") if path.suffix.casefold() == ".xml"]
    assets = {
        "gui": gui_status,
        "moduleData": module_data_status,
        # Backward-compatible summary fields used by the first deployment UI.
        "sourceGuiXml": len(project_gui_xml),
        "missingGuiXml": [value for value in gui_status["missing"] if value.casefold().endswith(".xml")],
        "differentGuiXml": [value for value in gui_status["different"] if value.casefold().endswith(".xml")],
        "deployedGuiXml": len(deployed_gui_xml),
    }

    descriptor_match = False
    deployed_module = None
    if deployed_descriptor.is_file():
        try:
            deployed_module = read_submodule(deployed_descriptor)
            descriptor_match = _sha256(descriptor) == _sha256(deployed_descriptor)
        except Exception as error:
            issues.append(f"Could not parse deployed SubModule.xml: {error}")
    if installed_module and not deployed_descriptor.is_file():
        issues.append(f"Deployed module is missing SubModule.xml: {deployed_descriptor}")
    elif deployed_descriptor.is_file() and not descriptor_match:
        issues.append("Deployed SubModule.xml differs from the project copy")

    direct_play_compatible = bool(deployed_module and is_singleplayer_module(deployed_module))
    if installed_module and deployed_module is not None and not direct_play_compatible:
        issues.append(
            "Deployed module is not declared as a single-player module; "
            "Lexeditor Play currently supports single-player modules only"
        )

    load_order: list[str] = []
    play_error = ""
    if game_exe.is_file() and installed_module and direct_play_compatible:
        try:
            load_order = module_load_order(game, project)
        except Exception as error:
            play_error = str(error)
            issues.append(f"Play load-order validation failed: {play_error}")

    module_data = deployed_root / "ModuleData"
    overrides = {
        "effects": _json_override(module_data / "custom_skill_effects.json", nested=True),
        "xpSources": _json_override(module_data / "custom_skill_xp_sources.json", nested=False),
    }
    for label, row in overrides.items():
        if row["exists"] and not row["valid"]:
            issues.append(f"Invalid deployed {label} override JSON: {row['error']}")

    runnable = bool(
        game_exe.is_file()
        and installed_module
        and direct_play_compatible
        and not missing_required
        and not missing_binaries
        and not play_error
    )
    in_sync = bool(
        installed_module
        and descriptor_match
        and gui_status["inSync"]
        and module_data_status["inSync"]
    )
    return {
        "gameRoot": str(game),
        "gameExecutable": str(game_exe),
        "projectRoot": str(project),
        "moduleId": module_id,
        "projectName": module.get("name") or module_id,
        "projectVersion": module.get("version") or "",
        "deployedRoot": str(deployed_root),
        "deployed": bool(installed_module),
        "deployedVersion": (deployed_module or {}).get("version", "") if deployed_module else "",
        "descriptorInSync": descriptor_match,
        "runnable": runnable,
        "inSync": in_sync,
        "issues": issues,
        "dependencies": dependency_rows,
        "binaries": binaries,
        "assets": assets,
        "runtimeOverrides": overrides,
        "loadOrder": load_order,
        "playError": play_error,
    }
