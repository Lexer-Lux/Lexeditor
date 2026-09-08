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
import re
import shutil


RUNTIME_SCHEMA_VERSION = 1
RUNTIME_DLL_NAME = "LexeditorFF7RRuntime.dll"
RUNTIME_CONFIG_NAME = "LexeditorFF7RRuntime.json"
RUNTIME_PROBE_DLL_NAME = "LexeditorFF7RRuntimeProbe.dll"
RUNTIME_PROBE_REPORT_NAME = "LexeditorFF7RRuntimeProbe.json"
RUNTIME_PROBE_SCHEMA_VERSION = 1
MAX_PROBE_REPORT_BYTES = 1024 * 1024
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


def probe_report_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_PROBE_REPORT_NAME


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


def _validate_probe_address(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9A-Fa-f]+", value):
        raise ValueError("probe match address is malformed")
    return value


def validate_probe_report(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime probe report must be an object")
    if value.get("schemaVersion") != RUNTIME_PROBE_SCHEMA_VERSION:
        raise ValueError(f"unsupported FF7R runtime probe schema: {value.get('schemaVersion')}")
    if value.get("probeOnly") is not True:
        raise ValueError("runtime probe report is missing probeOnly=true")
    process = value.get("process")
    process_size = value.get("processSize")
    text_base = value.get("textBase")
    text_size = value.get("textSize")
    probes = value.get("probes")
    if not isinstance(process, str) or not process:
        raise ValueError("runtime probe process path is missing")
    if isinstance(process_size, bool) or not isinstance(process_size, int) or process_size < 0:
        raise ValueError("runtime probe process size is invalid")
    _validate_probe_address(text_base)
    if isinstance(text_size, bool) or not isinstance(text_size, int) or text_size <= 0:
        raise ValueError("runtime probe text size is invalid")
    if not isinstance(probes, list) or len(probes) > 1000:
        raise ValueError("runtime probe list is invalid")

    normalized = []
    seen = set()
    for probe in probes:
        if not isinstance(probe, dict) or set(probe) != {"name", "matches"}:
            raise ValueError("runtime probe entry is malformed")
        name = probe.get("name")
        matches = probe.get("matches")
        if not isinstance(name, str) or not name or len(name) > 128 or name in seen:
            raise ValueError("runtime probe name is invalid or duplicated")
        if not isinstance(matches, list) or len(matches) > 10000:
            raise ValueError("runtime probe match list is invalid")
        seen.add(name)
        normalized.append({"name": name, "matches": [_validate_probe_address(item) for item in matches]})

    return {
        "schemaVersion": RUNTIME_PROBE_SCHEMA_VERSION,
        "probeOnly": True,
        "process": process,
        "processSize": process_size,
        "textBase": text_base,
        "textSize": text_size,
        "probes": normalized,
    }


def runtime_probe_status(game_root: Path) -> dict:
    target = probe_report_path(game_root)
    if not target.is_file():
        return {
            "reportPresent": False,
            "reportPath": str(target),
            "valid": False,
            "baselineCompatible": False,
            "reason": "No FF7R native runtime probe report has been collected.",
        }
    try:
        if target.stat().st_size > MAX_PROBE_REPORT_BYTES:
            raise ValueError("runtime probe report exceeds the 1 MiB safety limit")
        payload = validate_probe_report(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return {
            "reportPresent": True,
            "reportPath": str(target),
            "valid": False,
            "baselineCompatible": False,
            "reason": str(error),
        }

    by_name = {probe["name"]: probe["matches"] for probe in payload["probes"]}
    map_matches = by_name.get("knownMapControl", [])
    input_matches = by_name.get("knownRawInputRegistration", [])
    baseline = len(map_matches) == 1 and len(input_matches) == 1
    return {
        "reportPresent": True,
        "reportPath": str(target),
        "valid": True,
        "baselineCompatible": baseline,
        "process": payload["process"],
        "processSize": payload["processSize"],
        "textBase": payload["textBase"],
        "textSize": payload["textSize"],
        "knownMapControlMatches": map_matches,
        "knownRawInputRegistrationMatches": input_matches,
        "candidateRuntimeStrings": {
            name.removeprefix("ascii:"): matches
            for name, matches in by_name.items()
            if name.startswith("ascii:")
        },
        "reason": (
            "Known current-build native signatures each matched exactly once."
            if baseline else
            "Known current-build native signatures did not each match exactly once; do not apply runtime patches."
        ),
    }


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
        "probe": runtime_probe_status(game_root),
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
