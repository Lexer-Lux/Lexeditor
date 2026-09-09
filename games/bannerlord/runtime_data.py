"""Installed Bannerlord module and dependency diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import paths
from .module_data import read_submodule


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
    for dependency in module.get("dependencies", []):
        dep_id = str(dependency.get("id") or "")
        found = installed.get(dep_id.casefold())
        optional = bool(dependency.get("optional"))
        if not found and not optional:
            missing_required.append(dep_id)
        dependency_rows.append(
            {
                "id": dep_id,
                "requiredVersion": dependency.get("dependentVersion") or "",
                "optional": optional,
                "installed": bool(found),
                "installedVersion": found.get("version", "") if found else "",
                "path": found.get("path", "") if found else "",
            }
        )
    if missing_required:
        issues.append("Missing required dependencies: " + ", ".join(missing_required))

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

    project_gui = sorted(path for path in (project / "GUI").rglob("*.xml") if path.is_file()) if (project / "GUI").is_dir() else []
    missing_gui = []
    for source in project_gui:
        relative = source.relative_to(project / "GUI")
        if not (deployed_root / "GUI" / relative).is_file():
            missing_gui.append(relative.as_posix())
    assets = {
        "sourceGuiXml": len(project_gui),
        "missingGuiXml": missing_gui,
        "deployedGuiXml": len(list((deployed_root / "GUI").rglob("*.xml"))) if (deployed_root / "GUI").is_dir() else 0,
    }
    if missing_gui:
        issues.append(f"{len(missing_gui)} GUI XML file(s) are not deployed")

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

    module_data = deployed_root / "ModuleData"
    overrides = {
        "effects": _json_override(module_data / "custom_skill_effects.json", nested=True),
        "xpSources": _json_override(module_data / "custom_skill_xp_sources.json", nested=False),
    }
    for label, row in overrides.items():
        if row["exists"] and not row["valid"]:
            issues.append(f"Invalid deployed {label} override JSON: {row['error']}")

    runnable = bool(game_exe.is_file() and installed_module and not missing_required and not missing_binaries)
    in_sync = bool(installed_module and descriptor_match and not missing_gui)
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
    }
