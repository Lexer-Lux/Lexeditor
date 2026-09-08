"""Validated project configuration for FF7R native runtime behavior patches.

The DataObject/PAK pipeline cannot implement input or event-scene runtime behavior.
Runtime configuration, native binaries and hook-validation evidence therefore live
as separate project artifacts. A DLL merely existing is never enough to call the
runtime ready: deployment requires a manifest proving every requested hook was
validated for the installed executable timestamp.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import zlib


RUNTIME_SCHEMA_VERSION = 1
RUNTIME_MANIFEST_VERSION = 1
RUNTIME_DLL_NAME = "LexeditorFF7RRuntime.dll"
RUNTIME_CONFIG_NAME = "LexeditorFF7RRuntime.json"
RUNTIME_MANIFEST_NAME = "LexeditorFF7RRuntime.manifest.json"
NATIVE_MODS_DIR = "NativeMods"
BUNDLED_RUNTIME_NAME = "LexeditorFF7RRuntime.dll.zlib.b85"
BUNDLED_RUNTIME_PATH = Path(__file__).resolve().parent / "native_runtime" / BUNDLED_RUNTIME_NAME
# Green Windows artifact produced by ff7r-native-loader-scaffold for commit
# a62be77588e71dd5f4e62ad7be4c59aeecf6c6a9 (merged as #449).
BUNDLED_RUNTIME_SHA256 = "ed9c7f252e517473d181e29e3d4b2fcc4856f8beb4794b6a5779df696977a071"
REQUIRED_HOOKS = (
    "cutsceneSpeed",
    "minimapTapHold",
    "minimapState",
)
OPTIONAL_HOOKS = (
    "hpRebalance",
    "betterSprint",
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
    """Optional developer/test override for the bundled runtime binary."""
    return Path(project_root) / "runtime" / RUNTIME_DLL_NAME


def bundled_dll_path() -> Path:
    return BUNDLED_RUNTIME_PATH


def deployed_dll_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_DLL_NAME


def deployed_config_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_CONFIG_NAME


def deployed_manifest_path(game_root: Path) -> Path:
    return Path(game_root) / NATIVE_MODS_DIR / RUNTIME_MANIFEST_NAME


def _clone_default() -> dict:
    return json.loads(json.dumps(DEFAULT_RUNTIME_CONFIG))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str | None:
    try:
        return _sha256_bytes(Path(path).read_bytes()) if Path(path).is_file() else None
    except OSError:
        return None


def _decode_bundled_runtime() -> tuple[bytes | None, str]:
    target = bundled_dll_path()
    if not target.is_file():
        return None, f"bundled runtime payload is missing: {target}"
    try:
        encoded = "".join(target.read_text(encoding="ascii").split()).encode("ascii")
        compressed = base64.b85decode(encoded)
        data = zlib.decompress(compressed)
    except (OSError, ValueError, zlib.error) as error:
        return None, f"bundled runtime payload could not be decoded: {error}"
    digest = _sha256_bytes(data)
    if digest != BUNDLED_RUNTIME_SHA256:
        return None, (
            "bundled runtime payload failed SHA-256 verification: "
            f"expected {BUNDLED_RUNTIME_SHA256}, got {digest}"
        )
    if len(data) < 2 or data[:2] != b"MZ":
        return None, "bundled runtime payload is not a Windows PE image"
    return data, ""


def _selected_runtime_binary(project_root: Path) -> dict:
    override = project_dll_path(project_root)
    if override.is_file():
        try:
            data = override.read_bytes()
        except OSError as error:
            return {
                "present": False,
                "source": "project",
                "path": str(override),
                "sha256": None,
                "data": None,
                "error": f"project runtime override could not be read: {error}",
            }
        if len(data) < 2 or data[:2] != b"MZ":
            return {
                "present": False,
                "source": "project",
                "path": str(override),
                "sha256": _sha256_bytes(data),
                "data": None,
                "error": "project runtime override is not a Windows PE image",
            }
        return {
            "present": True,
            "source": "project",
            "path": str(override),
            "sha256": _sha256_bytes(data),
            "data": data,
            "error": "",
        }

    bundled, error = _decode_bundled_runtime()
    if bundled is None:
        return {
            "present": False,
            "source": "bundled",
            "path": str(bundled_dll_path()),
            "sha256": None,
            "data": None,
            "error": error,
        }
    return {
        "present": True,
        "source": "bundled",
        "path": str(bundled_dll_path()),
        "sha256": _sha256_bytes(bundled),
        "data": bundled,
        "error": "",
    }


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


def _runtime_sha256(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[0-9A-Fa-f]{64}", value) is None:
        raise ValueError("runtimeDllSha256 must be a 64-character hexadecimal SHA-256 digest")
    return value.lower()


def validate_runtime_manifest(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime manifest must be an object")
    allowed = {
        "manifestVersion",
        "hooks",
        "supportedExeTimestamps",
        "runtimeDllSha256",
        "notes",
    }
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
    dll_sha256 = _runtime_sha256(value.get("runtimeDllSha256"))
    notes = value.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("runtime manifest notes must be a string")
    result = {
        "manifestVersion": RUNTIME_MANIFEST_VERSION,
        "hooks": {name: hooks[name] for name in (*REQUIRED_HOOKS, *OPTIONAL_HOOKS) if name in hooks},
        "supportedExeTimestamps": timestamps,
        "notes": notes,
    }
    if dll_sha256 is not None:
        result["runtimeDllSha256"] = dll_sha256
    return result


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


def runtime_status(game_root: Path, project_root: Path) -> dict:
    project_dll = project_dll_path(project_root)
    deployed_dll = deployed_dll_path(game_root)
    binary = _selected_runtime_binary(project_root)
    bundled_bytes, bundled_error = _decode_bundled_runtime()
    bundled_present = bundled_dll_path().is_file()
    bundled_valid = bundled_bytes is not None
    loaders = [path for path in _loader_candidates(game_root) if path.is_file()]
    native_mods = Path(game_root) / NATIVE_MODS_DIR
    config = load_runtime_config(project_root)
    manifest, timestamp, hooks_validated, build_supported = _manifest_state(game_root, project_root)

    hp_requested = config["hpRebalance"]["enabled"]
    hp_hook_validated = bool(manifest) and manifest["hooks"].get("hpRebalance", False)
    sprint_requested = config["betterSprint"]["enabled"]
    sprint_hook_validated = bool(manifest) and manifest["hooks"].get("betterSprint", False)
    requested_hooks_validated = (
        hooks_validated
        and (not hp_requested or hp_hook_validated)
        and (not sprint_requested or sprint_hook_validated)
    )

    manifest_dll_sha = manifest.get("runtimeDllSha256") if manifest else None
    binary_hash_validated = (
        bool(binary["present"])
        and (manifest_dll_sha is None or binary["sha256"] == manifest_dll_sha)
    )
    deployed_sha = _sha256_file(deployed_dll)
    deployed_hash_validated = (
        deployed_sha is not None
        and (manifest_dll_sha is None or deployed_sha == manifest_dll_sha)
    )
    ready = (
        bool(binary["present"])
        and bool(loaders)
        and requested_hooks_validated
        and build_supported
        and binary_hash_validated
    )
    active = (
        deployed_dll.is_file()
        and bool(loaders)
        and requested_hooks_validated
        and build_supported
        and deployed_hash_validated
    )

    binary_error = binary["error"]
    notes = (
        "Runtime behavior patches require a native DLL, a compatible loader, validation for every enabled "
        "runtime hook, and an installed executable timestamp covered by that manifest. "
        "Lexeditor uses a project-local runtime DLL as a developer override when present; otherwise it uses "
        "the bundled CI-built runtime after verifying its pinned SHA-256."
    )
    if manifest_dll_sha is not None and binary["present"] and not binary_hash_validated:
        notes += (
            f" The selected runtime binary SHA-256 {binary['sha256']} does not match manifest pin "
            f"{manifest_dll_sha}."
        )
    if binary_error:
        notes += f" Runtime binary error: {binary_error}"
    if bundled_error and binary["source"] != "project":
        notes += f" Bundled runtime error: {bundled_error}"

    return {
        "schemaVersion": RUNTIME_SCHEMA_VERSION,
        "config": config,
        "configPath": str(config_path(project_root)),
        "manifestPath": str(manifest_path(project_root)),
        "projectDllPath": str(project_dll),
        "bundledDllPath": str(bundled_dll_path()),
        "deployedDllPath": str(deployed_dll),
        "deployedConfigPath": str(deployed_config_path(game_root)),
        "deployedManifestPath": str(deployed_manifest_path(game_root)),
        "projectDllPresent": project_dll.is_file(),
        "bundledDllPresent": bundled_present,
        "bundledDllValid": bundled_valid,
        "bundledDllSha256": BUNDLED_RUNTIME_SHA256 if bundled_valid else None,
        "runtimeBinaryPresent": bool(binary["present"]),
        "runtimeBinarySource": binary["source"] if binary["present"] else "none",
        "runtimeBinaryPath": binary["path"],
        "runtimeBinarySha256": binary["sha256"],
        "runtimeBinaryError": binary_error,
        "manifestRuntimeDllSha256": manifest_dll_sha,
        "runtimeBinaryHashValidated": binary_hash_validated,
        "deployedDllPresent": deployed_dll.is_file(),
        "deployedDllSha256": deployed_sha,
        "deployedDllHashValidated": deployed_hash_validated,
        "manifestPresent": manifest is not None,
        "manifest": manifest,
        "hooksValidated": hooks_validated,
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
        "notes": notes,
    }


def deploy_runtime(game_root: Path, project_root: Path) -> dict:
    status = runtime_status(game_root, project_root)
    if not status["runtimeBinaryPresent"]:
        raise RuntimeError(
            "No valid FF7R native runtime binary is available; runtime settings were not deployed. "
            + status["notes"]
        )
    if not status["loaderCandidatePresent"]:
        raise RuntimeError(
            "No compatible FF7R native loader proxy was detected in End/Binaries/Win64; "
            "runtime settings were not deployed."
        )
    if not status["manifestPresent"]:
        raise RuntimeError("FF7R runtime hook-validation manifest is missing; runtime was not deployed")
    if not status["hooksValidated"]:
        raise RuntimeError("FF7R runtime hooks are not all validated; runtime was not deployed")
    if status["hpRebalanceRequested"] and not status["hpRebalanceHookValidated"]:
        raise RuntimeError("FF7R HP Rebalance hook is enabled but not validated; runtime was not deployed")
    if status["betterSprintRequested"] and not status["betterSprintHookValidated"]:
        raise RuntimeError("FF7R Better Sprint hook is enabled but not validated; runtime was not deployed")
    if status["installedExeTimestamp"] is None:
        raise RuntimeError("Installed ff7remake_.exe timestamp could not be read; runtime was not deployed")
    if not status["buildSupported"]:
        raise RuntimeError(
            f"FF7R runtime is not validated for installed executable timestamp "
            f"{status['installedExeTimestampHex']}; runtime was not deployed"
        )
    if not status["runtimeBinaryHashValidated"]:
        raise RuntimeError(
            "FF7R runtime binary does not match the hook-validation manifest SHA-256; runtime was not deployed"
        )

    selected = _selected_runtime_binary(project_root)
    if not selected["present"] or selected["data"] is None:
        raise RuntimeError("FF7R runtime binary became unavailable during deployment")
    config = save_runtime_config(project_root, load_runtime_config(project_root))
    manifest = load_runtime_manifest(project_root)
    destination = deployed_dll_path(game_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_config = deployed_config_path(game_root)
    destination_manifest = deployed_manifest_path(game_root)

    temporary_dll = destination.with_suffix(destination.suffix + ".tmp")
    temporary_dll.write_bytes(selected["data"])
    os.replace(temporary_dll, destination)
    for source, target in (
        (config_path(project_root), destination_config),
        (manifest_path(project_root), destination_manifest),
    ):
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copy2(source, temporary)
        os.replace(temporary, target)

    deployed_sha = _sha256_file(destination)
    if deployed_sha != selected["sha256"]:
        raise RuntimeError("FF7R runtime DLL failed deployment SHA-256 readback verification")
    return {
        "dll": str(destination),
        "dllSource": selected["source"],
        "dllSha256": deployed_sha,
        "config": str(destination_config),
        "manifest": str(destination_manifest),
        "settings": config,
        "validation": manifest,
        "exeTimestamp": status["installedExeTimestamp"],
    }
