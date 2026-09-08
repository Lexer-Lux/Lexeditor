"""Truthful FF7R native runtime state exposed to the editor/service.

`runtime_config.runtime_status()` answers whether files/manifest/build are ready.
This module adds the missing runtime fact: whether the actual DLL is loaded in a
live FF7R process and explicitly reports every requested feature active.
"""

from __future__ import annotations

from pathlib import Path

from .runtime_config import (
    deploy_runtime as deploy_runtime_files,
    load_runtime_config,
    load_runtime_manifest,
    runtime_status as deployment_status,
)
from .runtime_heartbeat import (
    load_runtime_status,
    runtime_activation_state,
    status_path,
)


def requested_runtime_features(project_root: Path) -> list[str]:
    config = load_runtime_config(project_root)
    requested: list[str] = []
    if config["cutsceneSpeed"]["enabled"]:
        requested.append("cutsceneSpeed")
    if config["minimap"]["enabled"]:
        requested.extend(("minimapTapHold", "minimapState"))
    if config["hpRebalance"]["enabled"]:
        requested.append("hpRebalance")
    if config["betterSprint"]["enabled"]:
        requested.append("betterSprint")

    # Local import avoids archive -> runtime_dataobject -> runtime_state ->
    # atb_tweaks -> archive during module initialization.
    from .atb_tweaks import load_atb_config

    atb = load_atb_config(project_root)
    if atb["enabled"] and (
        atb["movementMultiplier"] != 1.0
        or atb["rollReduction"] != 0.0
    ):
        requested.append("atbTweaks")
    return requested


def _requested_manifest_hooks_valid(project_root: Path, requested: list[str]) -> bool:
    manifest = load_runtime_manifest(project_root)
    if manifest is None:
        return False
    hooks = manifest["hooks"]
    return all(bool(hooks.get(name, False)) for name in requested)


def runtime_status(game_root: Path, project_root: Path) -> dict:
    base = deployment_status(game_root, project_root)
    requested = requested_runtime_features(project_root)
    heartbeat_error = ""
    try:
        heartbeat = load_runtime_status(game_root)
    except ValueError as error:
        heartbeat = None
        heartbeat_error = str(error)
    activation = runtime_activation_state(
        heartbeat,
        installed_timestamp=base["installedExeTimestamp"],
        requested_features=requested,
    )
    manifest_requested = _requested_manifest_hooks_valid(project_root, requested)
    deployment_candidate_active = bool(base.get("active", False))
    runtime_ready = bool(base["projectDllPresent"] and base["loaderCandidatePresent"]
                         and base["buildSupported"] and manifest_requested)
    active = bool(
        base["deployedDllPresent"]
        and base["loaderCandidatePresent"]
        and base["buildSupported"]
        and manifest_requested
        and activation["requestedFeaturesActive"]
    )
    notes = base.get("notes", "")
    heartbeat_note = (
        " Runtime Active additionally requires a live DLL heartbeat from the current FF7R process "
        "with every requested feature explicitly reported active."
    )
    return {
        **base,
        **activation,
        "requestedRuntimeFeatures": requested,
        "requestedManifestHooksValidated": manifest_requested,
        "deploymentCandidateActive": deployment_candidate_active,
        "heartbeatPath": str(status_path(game_root)),
        "heartbeatError": heartbeat_error,
        "runtimeReady": runtime_ready,
        "active": active,
        "notes": notes + heartbeat_note,
    }


def deploy_runtime(game_root: Path, project_root: Path) -> dict:
    requested = requested_runtime_features(project_root)
    if not _requested_manifest_hooks_valid(project_root, requested):
        manifest = load_runtime_manifest(project_root)
        hooks = manifest["hooks"] if manifest else {}
        missing = [name for name in requested if not hooks.get(name, False)]
        raise RuntimeError(
            "FF7R runtime manifest does not validate every enabled runtime feature"
            + (f": {', '.join(missing)}" if missing else "")
        )
    result = deploy_runtime_files(game_root, project_root)
    # Deployment itself is not activation. Any old heartbeat belongs to an old
    # process/runtime image and must not be allowed to survive as apparent proof.
    target = status_path(game_root)
    try:
        target.unlink(missing_ok=True)
    except OSError:
        pass
    return {**result, "active": False, "heartbeat": str(target)}
