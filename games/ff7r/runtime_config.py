"""Validated project configuration for FF7R native runtime behavior patches.

The DataObject/PAK pipeline cannot implement input or event-scene runtime behavior.
This module deliberately keeps those settings in a separate project artifact and
reports deployment readiness without pretending a missing native DLL is active.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil


RUNTIME_SCHEMA_VERSION = 1
RUNTIME_DLL_NAME = "LexeditorFF7RRuntime.dll"
RUNTIME_CONFIG_NAME = "LexeditorFF7RRuntime.json"
NATIVE_MODS_DIR = "NativeMods"

DEFAULT_RUNTIME_CONFIG = {
    "schemaVersion": RUNTIME_SCHEMA_VERSION,
    "cutsceneSpeed": {
        "enabled": False,
        "baseMultiplier": 1.25,
        # The runtime must multiply the game's selected native event-scene
        # fast-forward multiplier (1.5x/2x) by this base, not replace it.
        "r2Behavior": "multiply-native",
    },
    "minimap": {
        "enabled": False,
        "holdMilliseconds": 350,
        "persistChosenState": True,
        "tapBehavior": "open-map",
        "holdBehavior": "toggle-minimap",
    },
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / RUNTIME_CONFIG_NAME


def project_dll_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / RUNTIME_DLL_NAME


def deployed_dll_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_DLL_NAME


def deployed_config_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_CONFIG_NAME


def _clone_default() -> dict:
    return json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))


def validate_runtime_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime config must be an object")
    if set(value) - {"schemaVersion", "cutsceneSpeed", "minimap"}:
        raise ValueError("runtime config contains unsupported top-level fields")
    if value.get("schemaVersion", RUNTIME_SCHEMA_VERSION) != RUNTIME_SCHEMA_VERSION:
        raise ValueError(f"unsupported FF7R runtime config schema: {value.get('schemaVersion')}")

    cutscene = value.get("cutsceneSpeed", {})
    if not isinstance(cutscene, dict):
        raise ValueError("cutsceneSpeed must be an object")
    if set(cutscene) - {"enabled", "baseMultiplier", "r2Behavior"}:
        raise ValueError("cutsceneSpeed contains unsupported fields")
    enabled = cutscene.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("cutsceneSpeed.enabled must be boolean")
    multiplier = cutscene.get("baseMultiplier", DEFAULT_RUNTIME_CONFIG["cutsceneSpeed"]["baseMultiplier"])
    if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
        raise ValueError("cutsceneSpeed.baseMultiplier must be numeric")
    multiplier = float(multiplier)
    if not math.isfinite(multiplier) or multiplier <= 1.0:
        raise ValueError("cutsceneSpeed.baseMultiplier must be greater than 1.0")
    if cutscene.get("r2Behavior", "multiply-native") != "multiply-native":
        raise ValueError("cutsceneSpeed.r2Behavior must be multiply-native")

    minimap = value.get("minimap", {})
    if not isinstance(minimap, dict):
        raise ValueError("minimap must be an object")
    if set(minimap) - {
        "enabled", "holdMilliseconds", "persistChosenState", "tapBehavior", "holdBehavior"
    }:
        raise ValueError("minimap contains unsupported fields")
    map_enabled = minimap.get("enabled", False)
    persist = minimap.get("persistChosenState", True)
    if not isinstance(map_enabled, bool) or not isinstance(persist, bool):
        raise ValueError("minimap enabled/persistence fields must be boolean")
    hold_ms = minimap.get("holdMilliseconds", DEFAULT_RUNTIME_CONFIG["minimap"]["holdMilliseconds"])
    if isinstance(hold_ms, bool) or not isinstance(hold_ms, int):
        raise ValueError("minimap.holdMilliseconds must be an integer")
    if hold_ms < 150 or hold_ms > 1500:
        raise ValueError("minimap.holdMilliseconds must be between 150 and 1500 ms")
    if minimap.get("tapBehavior", "open-map") != "open-map":
        raise ValueError("minimap.tapBehavior must be open-map")
    if minimap.get("holdBehavior", "toggle-minimap") != "toggle-minimap":
        raise ValueError("minimap.holdBehavior must be toggle-minimap")

    return {
        "schemaVersion": RUNTIME_SCHEMA_VERSION,
        "cutsceneSpeed": {
            "enabled": enabled,
            "baseMultiplier": multiplier,
            "r2Behavior": "multiply-native",
        },
        "minimap": {
            "enabled": map_enabled,
            "holdMilliseconds": hold_ms,
            "persistChosenState": persist,
            "tapBehavior": "open-map",
            "holdBehavior": "toggle-minimap",
        },
    }


def load_runtime_config(project_root: Path) -> dict:
    target = config_path(project_root)
    if not target.is_file():
        return _clone_default()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R runtime config: {error}") from error
    return validate_runtime_config(payload)


def save_runtime_config(project_root: Path, value: dict) -> dict:
    validated = validate_runtime_config(value)
    target = config_path(project_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    reread = load_runtime_config(project_root)
    if reread != validated:
        raise RuntimeError("FF7R runtime config failed atomic readback")
    return reread


def _loader_candidates(game_root: Path) -> list[Path]:
    binaries = Path(game_root) / "End" / "Binaries" / "Win64"
    return [
        binaries / "xinput1_3.dll",
        binaries / "dxgi.dll",
        binaries / "X3DAudio1_7.dll",
        binaries / "XAPOFX1_5.dll",
    ]


def runtime_status(game_root: Path, project_root: Path) -> dict:
    project_dll = project_dll_path(project_root)
    deployed_dll = deployed_dll_path(game_root)
    loaders = [path for path in _loader_candidates(game_root) if path.is_file()]
    native_mods = Path(game_root) / NATIVE_MODS_DIR
    config = load_runtime_config(project_root)
    return {
        "schemaVersion": RUNTIME_SCHEMA_VERSION,
        "config": config,
        "configPath": str(config_path(project_root)),
        "projectDllPath": str(project_dll),
        "deployedDllPath": str(deployed_dll),
        "deployedConfigPath": str(deployed_config_path(game_root)),
        "projectDllPresent": project_dll.is_file(),
        "deployedDllPresent": deployed_dll.is_file(),
        "nativeModsDirectoryPresent": native_mods.is_dir(),
        # Proxy presence is evidence of a native loader/hook but not proof that
        # it is Native Mod Loader, so expose exactly what was observed.
        "proxyDlls": [str(path) for path in loaders],
        "loaderCandidatePresent": bool(loaders),
        "runtimeReady": project_dll.is_file() and bool(loaders),
        "active": deployed_dll.is_file() and bool(loaders),
        "notes": (
            "Runtime behavior patches require a native DLL and compatible DLL loader. "
            "PAK deployment alone cannot implement cutscene timing or tap/hold minimap input."
        ),
    }


def deploy_runtime(game_root: Path, project_root: Path) -> dict:
    source_dll = project_dll_path(project_root)
    if not source_dll.is_file():
        raise RuntimeError(
            f"FF7R native runtime DLL is not built: {source_dll}. "
            "Runtime settings were not deployed."
        )
    status = runtime_status(game_root, project_root)
    if not status["loaderCandidatePresent"]:
        raise RuntimeError(
            "No compatible FF7R native loader proxy was detected in End/Binaries/Win64; "
            "runtime settings were not deployed."
        )
    config = save_runtime_config(project_root, load_runtime_config(project_root))
    destination = deployed_dll_path(game_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_config = deployed_config_path(game_root)
    for source, target in ((source_dll, destination), (config_path(project_root), destination_config)):
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    return {
        "dll": str(destination),
        "config": str(destination_config),
        "settings": config,
    }
