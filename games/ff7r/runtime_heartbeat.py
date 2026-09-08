"""Process-aware status contract written by the loaded FF7R native runtime DLL.

A deployed DLL file is not proof that FF7R loaded it, and a validation manifest is
not proof that a hook is active in the current process.  The runtime therefore
writes a small heartbeat/status file from its exported Init() entrypoint.  Python
accepts that file only when the PID is still alive, the executable timestamp
matches the installed game, and requested features are explicitly reported
active by the DLL.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable, Iterable


RUNTIME_STATUS_VERSION = 1
RUNTIME_STATUS_NAME = "LexeditorFF7RRuntime.status.json"
KNOWN_FEATURES = frozenset({
    "cutsceneSpeed",
    "minimapTapHold",
    "minimapState",
    "hpRebalance",
    "betterSprint",
    "atbTweaks",
    "dogWhistle",
    "unscannedNames",
})


def status_path(game_root: Path) -> Path:
    return Path(game_root) / "NativeMods" / RUNTIME_STATUS_NAME


def validate_runtime_status(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("runtime status must be an object")
    allowed = {"statusVersion", "processId", "exeTimestamp", "loaded", "features", "notes"}
    if set(value) - allowed:
        raise ValueError("runtime status contains unsupported fields")
    if value.get("statusVersion") != RUNTIME_STATUS_VERSION:
        raise ValueError("unsupported FF7R runtime status version")
    process_id = value.get("processId")
    if isinstance(process_id, bool) or not isinstance(process_id, int) or process_id <= 0:
        raise ValueError("runtime status processId must be a positive integer")
    timestamp = value.get("exeTimestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or not 0 <= timestamp <= 0xFFFFFFFF:
        raise ValueError("runtime status exeTimestamp must be a PE timestamp integer")
    loaded = value.get("loaded")
    if not isinstance(loaded, bool):
        raise ValueError("runtime status loaded must be boolean")
    raw_features = value.get("features")
    if not isinstance(raw_features, dict) or set(raw_features) - KNOWN_FEATURES:
        raise ValueError("runtime status features contain unsupported names")
    if any(not isinstance(flag, bool) for flag in raw_features.values()):
        raise ValueError("runtime status feature flags must be boolean")
    notes = value.get("notes", "")
    if not isinstance(notes, str):
        raise ValueError("runtime status notes must be a string")
    return {
        "statusVersion": RUNTIME_STATUS_VERSION,
        "processId": process_id,
        "exeTimestamp": timestamp,
        "loaded": loaded,
        "features": {name: bool(raw_features.get(name, False)) for name in sorted(KNOWN_FEATURES)},
        "notes": notes,
    }


def load_runtime_status(game_root: Path) -> dict | None:
    target = status_path(game_root)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R runtime status: {error}") from error
    return validate_runtime_status(payload)


def process_alive(process_id: int) -> bool:
    """Best-effort cross-platform PID liveness check; Windows uses a real handle."""
    if process_id <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(process_id, 0)
    except (OSError, ValueError):
        return False
    return True


def runtime_activation_state(
    status: dict | None,
    *,
    installed_timestamp: int | None,
    requested_features: Iterable[str],
    alive: Callable[[int], bool] = process_alive,
) -> dict:
    requested = tuple(dict.fromkeys(str(name) for name in requested_features))
    unknown = set(requested) - KNOWN_FEATURES
    if unknown:
        raise ValueError(f"Unknown requested FF7R runtime features: {sorted(unknown)}")
    if status is None:
        return {
            "heartbeatPresent": False,
            "runtimeProcessAlive": False,
            "runtimeLoaded": False,
            "heartbeatTimestampMatches": False,
            "activeFeatures": [],
            "requestedFeaturesActive": False,
        }
    validated = validate_runtime_status(status)
    is_alive = alive(validated["processId"])
    timestamp_matches = (
        installed_timestamp is not None
        and validated["exeTimestamp"] == installed_timestamp
    )
    active_features = sorted(name for name, active in validated["features"].items() if active)
    loaded = bool(validated["loaded"] and is_alive and timestamp_matches)
    requested_active = loaded and all(validated["features"].get(name, False) for name in requested)
    return {
        "heartbeatPresent": True,
        "runtimeProcessAlive": is_alive,
        "runtimeLoaded": loaded,
        "heartbeatTimestampMatches": timestamp_matches,
        "activeFeatures": active_features,
        "requestedFeaturesActive": requested_active,
    }
