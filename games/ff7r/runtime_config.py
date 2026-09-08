"""Validated project configuration for FF7R native runtime behavior patches.

The DataObject/PAK pipeline cannot implement input or event-scene runtime behavior.
Runtime configuration, native binaries and hook-validation evidence therefore live
as separate project artifacts. A DLL merely existing is never enough to call the
runtime ready: deployment requires a manifest proving every requested hook was
validated for the installed executable timestamp.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import struct


RUNTIME_SCHEMA_VERSION = 1
RUNTIME_MANIFEST_VERSION = 1
RUNTIME_DLL_NAME = "LexeditorFF7RRuntime.dll"
RUNTIME_CONFIG_NAME = "LexeditorFF7RRuntime.json"
RUNTIME_MANIFEST_NAME = "LexeditorFF7RRuntime.manifest.json"
NATIVE_MODS_DIR = "NativeMods"
REQUIRED_HOOKS = (
    "cutsceneSpeed",
    "minimapTapHold",
    "minimapState",
)
OPTIONAL_HOOKS = (
    "hpRebalance",
    "betterSprint",
    "atbTweaks",
)

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
    "hpRebalance": {
        "enabled": False,
        # Scale the final playable-party maximum HP. This must not be
        # implemented by merely scaling PlayerParameter.HPMax because equipment
        # and materia can add/scale max HP through separate data paths.
        "hpMultiplier": 0.5,
    },
    "betterSprint": {
        "enabled": False,
        # 1.0x is deliberately the default because the issue does not prescribe
        # a faster default. The validated runtime hook must scale actual player
        # dash/sprint translation while leaving walk/jog/scripted movement alone.
        "speedMultiplier": 1.0,
    },
}


def config_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / RUNTIME_CONFIG_NAME


def manifest_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / RUNTIME_MANIFEST_NAME


def project_dll_path(project_root: Path) -> Path:
    return Path(project_root) / "runtime" / RUNTIME_DLL_NAME


def deployed_dll_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_DLL_NAME


def deployed_config_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_CONFIG_NAME


def deployed_manifest_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_MANIFEST_NAME


def _clone_default() -> dict:
    return json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))


def validate_runtime_config(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime config must be an object")
    if set(value) - {"schemaVersion", "cutsceneSpeed", "minimap", "hpRebalance", "betterSprint"}:
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

    hp_rebalance = value.get("hpRebalance", {})
    if not isinstance(hp_rebalance, dict):
        raise ValueError("hpRebalance must be an object")
    if set(hp_rebalance) - {"enabled", "hpMultiplier"}:
        raise ValueError("hpRebalance contains unsupported fields")
    hp_enabled = hp_rebalance.get("enabled", False)
    if not isinstance(hp_enabled, bool):
        raise ValueError("hpRebalance.enabled must be boolean")
    hp_multiplier = hp_rebalance.get("hpMultiplier", DEFAULT_RUNTIME_CONFIG["hpRebalance"]["hpMultiplier"])
    if isinstance(hp_multiplier, bool) or not isinstance(hp_multiplier, (int, float)):
        raise ValueError("hpRebalance.hpMultiplier must be numeric")
    hp_multiplier = float(hp_multiplier)
    if not math.isfinite(hp_multiplier) or hp_multiplier <= 0.0:
        raise ValueError("hpRebalance.hpMultiplier must be greater than 0")

    better_sprint = value.get("betterSprint", {})
    if not isinstance(better_sprint, dict):
        raise ValueError("betterSprint must be an object")
    if set(better_sprint) - {"enabled", "speedMultiplier"}:
        raise ValueError("betterSprint contains unsupported fields")
    sprint_enabled = better_sprint.get("enabled", False)
    if not isinstance(sprint_enabled, bool):
        raise ValueError("betterSprint.enabled must be boolean")
    sprint_multiplier = better_sprint.get(
        "speedMultiplier", DEFAULT_RUNTIME_CONFIG["betterSprint"]["speedMultiplier"])
    if isinstance(sprint_multiplier, bool) or not isinstance(sprint_multiplier, (int, float)):
        raise ValueError("betterSprint.speedMultiplier must be numeric")
    sprint_multiplier = float(sprint_multiplier)
    if not math.isfinite(sprint_multiplier) or sprint_multiplier <= 0.0:
        raise ValueError("betterSprint.speedMultiplier must be greater than 0")

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
        "hpRebalance": {
            "enabled": hp_enabled,
            "hpMultiplier": hp_multiplier,
        },
        "betterSprint": {
            "enabled": sprint_enabled,
            "speedMultiplier": sprint_multiplier,
        },
    }


def _timestamp_value(value) -> int:
    if isinstance(value, bool):
        raise ValueError("runtime manifest timestamps must be integers or hexadecimal strings")
    if isinstance(value, int):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = int(value, 0)
        except ValueError as error:
            raise ValueError(f"invalid runtime manifest timestamp: {value!r}") from error
    else:
        raise ValueError("runtime manifest timestamps must be integers or hexadecimal strings")
    if timestamp < 0 or timestamp > 0xFFFFFFFF:
        raise ValueError("runtime manifest timestamp is outside the PE timestamp range")
    return timestamp


def validate_runtime_manifest(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime manifest must be an object")
    allowed = {"manifestVersion", "hooks", "supportedExeTimestamps", "notes"}
    if set(value) - allowed:
        raise ValueError("runtime manifest contains unsupported fields")
    if value.get("manifestVersion") != RUNTIME_MANIFEST_VERSION:
        raise ValueError("unsupported FF7R runtime manifest version")
    hooks = value.get("hooks")
    required = set(REQUIRED_HOOKS)
    optional = set(OPTIONAL_HOOKS)
    if (not isinstance(hooks, dict) or not required.issubset(hooks)
            or set(hooks) - required - optional):
        raise ValueError(
            "runtime manifest must declare exactly the required hook validation flags plus supported optional hooks"
        )
    if any(not isinstance(flag, bool) for flag in hooks.values()):
        raise ValueError("runtime manifest hook validation flags must be boolean")
    raw_timestamps = value.get("supportedExeTimestamps")
    if not isinstance(raw_timestamps, list) or not raw_timestamps:
        raise ValueError("runtime manifest must list at least one supported executable timestamp")
    timestamps = sorted({_timestamp_value(item) for item in raw_timestamps})
    notes = value.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("runtime manifest notes must be a string")
    return {
        "manifestVersion": RUNTIME_MANIFEST_VERSION,
        "hooks": {name: hooks[name] for name in (*REQUIRED_HOOKS, *OPTIONAL_HOOKS) if name in hooks},
        "supportedExeTimestamps": timestamps,
        "notes": notes,
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


def load_runtime_manifest(project_root: Path) -> dict | None:
    target = manifest_path(project_root)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R runtime manifest: {error}") from error
    return validate_runtime_manifest(payload)


def _loader_candidates(game_root: Path) -> list[Path]:
    binaries = Path(game_root) / "End" / "Binaries" / "Win64"
    return [
        binaries / "xinput1_3.dll",
        binaries / "dxgi.dll",
        binaries / "X3DAudio1_7.dll",
        binaries / "XAPOFX1_5.dll",
    ]


def _installed_exe_timestamp(game_root: Path) -> int | None:
    exe = Path(game_root) / "End" / "Binaries" / "Win64" / "ff7remake_.exe"
    if not exe.is_file():
        return None
    try:
        with exe.open("rb") as handle:
            if handle.read(2) != b"MZ":
                return None
            handle.seek(0x3C)
            raw = handle.read(4)
            if len(raw) != 4:
                return None
            pe_offset = struct.unpack("<I", raw)[0]
            handle.seek(pe_offset)
            if handle.read(4) != b"PE\0\0":
                return None
            coff = handle.read(20)
            if len(coff) != 20:
                return None
            return struct.unpack_from("<I", coff, 4)[0]
    except OSError:
        return None


def _manifest_state(game_root: Path, project_root: Path) -> tuple[dict | None, int | None, bool, bool]:
    manifest = load_runtime_manifest(project_root)
    timestamp = _installed_exe_timestamp(game_root)
    hooks_validated = bool(manifest) and all(manifest["hooks"][name] for name in REQUIRED_HOOKS)
    build_supported = bool(manifest) and timestamp is not None and timestamp in manifest["supportedExeTimestamps"]
    return manifest, timestamp, hooks_validated, build_supported


def _requested_hook_names(config: dict) -> tuple[str, ...]:
    requested: list[str] = []
    if config["cutsceneSpeed"]["enabled"]:
        requested.append("cutsceneSpeed")
    if config["minimap"]["enabled"]:
        requested.extend(("minimapTapHold", "minimapState"))
    if config["hpRebalance"]["enabled"]:
        requested.append("hpRebalance")
    if config["betterSprint"]["enabled"]:
        requested.append("betterSprint")
    return tuple(requested)


def runtime_status(game_root: Path, project_root: Path) -> dict:
    project_dll = project_dll_path(project_root)
    deployed_dll = deployed_dll_path(game_root)
    loaders = [path for path in _loader_candidates(game_root) if path.is_file()]
    native_mods = Path(game_root) / NATIVE_MODS_DIR
    config = load_runtime_config(project_root)
    manifest, timestamp, hooks_validated, build_supported = _manifest_state(game_root, project_root)

    hp_requested = config["hpRebalance"]["enabled"]
    hp_hook_validated = bool(manifest) and manifest["hooks"].get("hpRebalance", False)
    sprint_requested = config["betterSprint"]["enabled"]
    sprint_hook_validated = bool(manifest) and manifest["hooks"].get("betterSprint", False)
    requested_hooks = _requested_hook_names(config)
    missing_requested_hooks = [
        name
        for name in requested_hooks
        if not (manifest and manifest["hooks"].get(name, False))
    ]
    requested_hooks_validated = manifest is not None and not missing_requested_hooks
    ready = project_dll.is_file() and bool(loaders) and requested_hooks_validated and build_supported
    active = deployed_dll.is_file() and bool(loaders) and requested_hooks_validated and build_supported
    return {
        "schemaVersion": RUNTIME_SCHEMA_VERSION,
        "config": config,
        "configPath": str(config_path(project_root)),
        "manifestPath": str(manifest_path(project_root)),
        "projectDllPath": str(project_dll),
        "deployedDllPath": str(deployed_dll),
        "deployedConfigPath": str(deployed_config_path(game_root)),
        "deployedManifestPath": str(deployed_manifest_path(game_root)),
        "projectDllPresent": project_dll.is_file(),
        "deployedDllPresent": deployed_dll.is_file(),
        "manifestPresent": manifest is not None,
        "manifest": manifest,
        "hooksValidated": hooks_validated,
        "requestedHooks": list(requested_hooks),
        "missingRequestedHooks": missing_requested_hooks,
        "requestedHooksValidated": requested_hooks_validated,
        "hpRebalanceRequested": hp_requested,
        "hpRebalanceHookValidated": hp_hook_validated,
        "betterSprintRequested": sprint_requested,
        "betterSprintHookValidated": sprint_hook_validated,
        "installedExeTimestamp": timestamp,
        "installedExeTimestampHex": f"0x{timestamp:08X}" if timestamp is not None else None,
        "buildSupported": build_supported,
        "nativeModsDirectoryPresent": native_mods.is_dir(),
        # Proxy presence is evidence of a native loader/hook but not proof that
        # it is Native Mod Loader, so expose exactly what was observed.
        "proxyDlls": [str(path) for path in loaders],
        "loaderCandidatePresent": bool(loaders),
        "runtimeReady": ready,
        "active": active,
        "notes": (
            "Runtime behavior patches require a native DLL, a compatible loader, validation for every enabled "
            "runtime hook, and an installed executable timestamp covered by that manifest."
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
    if not status["manifestPresent"]:
        raise RuntimeError("FF7R runtime hook-validation manifest is missing; runtime was not deployed")
    if not status["requestedHooksValidated"]:
        missing = ", ".join(status["missingRequestedHooks"]) or "unknown"
        raise RuntimeError(
            f"FF7R requested runtime hooks are not validated: {missing}; runtime was not deployed"
        )
    if status["installedExeTimestamp"] is None:
        raise RuntimeError("Installed ff7remake_.exe timestamp could not be read; runtime was not deployed")
    if not status["buildSupported"]:
        raise RuntimeError(
            f"FF7R runtime is not validated for installed executable timestamp "
            f"{status['installedExeTimestampHex']}; runtime was not deployed"
        )

    config = save_runtime_config(project_root, load_runtime_config(project_root))
    manifest = load_runtime_manifest(project_root)
    destination = deployed_dll_path(game_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_config = deployed_config_path(game_root)
    destination_manifest = deployed_manifest_path(game_root)
    for source, target in (
        (source_dll, destination),
        (config_path(project_root), destination_config),
        (manifest_path(project_root), destination_manifest),
    ):
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
    return {
        "dll": str(destination),
        "config": str(destination_config),
        "manifest": str(destination_manifest),
        "settings": config,
        "validation": manifest,
        "exeTimestamp": status["installedExeTimestamp"],
    }
