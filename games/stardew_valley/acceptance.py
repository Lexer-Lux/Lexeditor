"""Evidence-driven installed-game acceptance for the Stardew Valley plugin."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .content_pack import (
    ContentPackStore,
    _atomic_json,
    _json,
    deployment_status,
    loader_status,
)

TARGET_GAME_VERSION = "1.6.15"
ACCEPTANCE_MARKER = ".lexeditor-stardew-acceptance.json"
MAX_LOG_BYTES = 16 * 1024 * 1024
_RUNTIME_RE = re.compile(
    r"\bSMAPI\s+(?P<smapi>\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?)\s+with\s+"
    r"Stardew Valley\s+(?P<game>\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?)"
    r"(?:\s+build\s+(?P<build>\d+))?\s+on\s+(?P<platform>.+)$",
    re.IGNORECASE,
)
_CP_RE = re.compile(r"\bContent Patcher\s+(?P<version>\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.-]+)?)\b", re.IGNORECASE)
_ERROR_WORDS = ("error", "failed", "could not", "couldn't", "invalid", "skipped", "not loaded")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _version_tuple(value: str | None) -> tuple[int, ...] | None:
    if not value:
        return None
    match = re.match(r"^(\d+(?:\.\d+){1,3})", str(value).strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _version_at_least(actual: str | None, minimum: str | None) -> bool | None:
    if not minimum:
        return True
    actual_parts = _version_tuple(actual)
    minimum_parts = _version_tuple(minimum)
    if actual_parts is None or minimum_parts is None:
        return None
    width = max(len(actual_parts), len(minimum_parts))
    return actual_parts + (0,) * (width - len(actual_parts)) >= minimum_parts + (0,) * (width - len(minimum_parts))


def _loader_evidence(game_root: Path) -> dict:
    """Add manifest-declared Content Patcher versions without changing deployment semantics."""
    loader = dict(loader_status(game_root))
    root = loader.get("contentPatcherRoot")
    if root:
        try:
            manifest = _json(Path(root) / "manifest.json")
            loader["contentPatcherVersion"] = str(manifest.get("Version")) if manifest.get("Version") is not None else None
            loader["contentPatcherMinimumApiVersion"] = (
                str(manifest.get("MinimumApiVersion")) if manifest.get("MinimumApiVersion") is not None else None
            )
        except (OSError, ValueError, json.JSONDecodeError):
            loader["contentPatcherVersion"] = None
            loader["contentPatcherMinimumApiVersion"] = None
    return loader


def smapi_log_path() -> Path:
    """Return the canonical SMAPI latest-log path, with an environment override for tests/support."""
    override = os.environ.get("LEXEDITOR_STARDEW_SMAPI_LOG")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return (appdata / "StardewValley" / "ErrorLogs" / "SMAPI-latest.txt").resolve()
    # SMAPI uses this location on Linux and macOS too.
    return (Path.home() / ".config" / "StardewValley" / "ErrorLogs" / "SMAPI-latest.txt").resolve()


def _read_log(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, None
    size = path.stat().st_size
    if size > MAX_LOG_BYTES:
        return None, f"SMAPI log is too large to inspect safely ({size} bytes)"
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace"), None
    except OSError as error:
        return None, f"Could not read SMAPI log: {error}"


def _runtime_evidence(text: str, project_name: str, project_unique_id: str) -> dict:
    runtime = {"smapiVersion": None, "gameVersion": None, "gameBuild": None, "platform": None}
    content_patcher_version = None
    project_lines: list[str] = []
    project_error_lines: list[str] = []
    project_loaded_lines: list[str] = []
    name_key = project_name.casefold()
    id_key = project_unique_id.casefold()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _RUNTIME_RE.search(line)
        if match:
            runtime = {
                "smapiVersion": match.group("smapi"),
                "gameVersion": match.group("game"),
                "gameBuild": match.group("build"),
                "platform": match.group("platform").strip(),
            }
        cp_match = _CP_RE.search(line)
        if cp_match:
            content_patcher_version = cp_match.group("version")
        folded = line.casefold()
        project_named = (id_key and id_key in folded) or (name_key and name_key in folded)
        if project_named:
            project_lines.append(line[:1000])
            if "| for content patcher" in folded:
                project_loaded_lines.append(line[:1000])
            if any(word in folded for word in _ERROR_WORDS):
                project_error_lines.append(line[:1000])
    return {
        **runtime,
        "contentPatcherVersion": content_patcher_version,
        "contentPatcherSeen": content_patcher_version is not None or "content patcher" in text.casefold(),
        "projectMentioned": bool(project_lines),
        "projectLoaded": bool(project_loaded_lines),
        "projectLines": project_lines[:10],
        "projectLoadedLines": project_loaded_lines[:10],
        "projectErrors": project_error_lines[:10],
    }


def _marker_path(project_root: Path) -> Path:
    return Path(project_root).expanduser().resolve() / ACCEPTANCE_MARKER


def begin_acceptance(game_root: Path, project_root: Path, *, log_path: Path | None = None) -> dict:
    """Snapshot immutable game data and the current SMAPI log before a real runtime test."""
    game = Path(game_root).expanduser().resolve()
    project = Path(project_root).expanduser().resolve()
    store = ContentPackStore(project)
    store.validate()
    if not any(row.get("fields") for row in store.objects()["rows"]):
        raise RuntimeError("Add and save at least one supported Data/Objects field override before acceptance")
    deployment = deployment_status(game, project)
    if not deployment["deployed"] or not deployment["managed"]:
        raise RuntimeError("Deploy this project with Lexeditor before beginning installed-game acceptance")
    if deployment["externallyChanged"]:
        raise RuntimeError("The deployed content pack changed outside Lexeditor; reconcile it before acceptance")
    deployed_root = Path(deployment["target"])
    for relative in ("manifest.json", "content.json"):
        source_file = project / relative
        deployed_file = deployed_root / relative
        if not deployed_file.is_file() or _sha256(source_file) != _sha256(deployed_file):
            raise RuntimeError("The deployed pack is older than the current project; redeploy before acceptance")
    loader = _loader_evidence(game)
    if not loader["ready"]:
        raise RuntimeError("SMAPI and Content Patcher must both be installed before acceptance")
    xnb_path = game / "Content" / "Data" / "Objects.xnb"
    if not xnb_path.is_file():
        raise RuntimeError(f"Installed Data/Objects XNB was not found: {xnb_path}")
    manifest = _json(project / "manifest.json")
    project_name = str(manifest.get("Name") or project.name)
    project_unique_id = str(manifest.get("UniqueID") or "")
    if not project_unique_id:
        raise RuntimeError("The project manifest needs a UniqueID before acceptance")
    current_log = Path(log_path or smapi_log_path()).expanduser().resolve()
    marker = {
        "schema": 1,
        "targetGameVersion": TARGET_GAME_VERSION,
        "gameRoot": str(game),
        "projectRoot": str(project),
        "projectName": project_name,
        "projectUniqueID": project_unique_id,
        "objectsXnbPath": str(xnb_path),
        "objectsXnbSha256": _sha256(xnb_path),
        "smapiLogPath": str(current_log),
        "baselineLogSha256": _sha256(current_log) if current_log.is_file() else None,
    }
    _atomic_json(_marker_path(project), marker)
    return acceptance_status(game, project)


def acceptance_status(game_root: Path, project_root: Path) -> dict:
    """Return current acceptance evidence without mutating the installation or project."""
    game = Path(game_root).expanduser().resolve()
    project = Path(project_root).expanduser().resolve()
    marker_path = _marker_path(project)
    loader = _loader_evidence(game)
    deployment = deployment_status(game, project)
    if not marker_path.is_file():
        return {
            "started": False,
            "state": "not-started",
            "accepted": False,
            "targetGameVersion": TARGET_GAME_VERSION,
            "loader": loader,
            "deployment": deployment,
            "smapiLogPath": str(smapi_log_path()),
            "blockers": ["Begin acceptance after deploying a representative Data/Objects edit."],
        }

    try:
        marker = _json(marker_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "started": False,
            "state": "invalid-marker",
            "accepted": False,
            "targetGameVersion": TARGET_GAME_VERSION,
            "loader": loader,
            "deployment": deployment,
            "blockers": [f"Acceptance marker is invalid: {error}"],
        }

    blockers: list[str] = []
    if Path(str(marker.get("gameRoot", ""))).resolve() != game or Path(str(marker.get("projectRoot", ""))).resolve() != project:
        blockers.append("Acceptance baseline belongs to a different game or project path; begin it again.")

    xnb_path = Path(str(marker.get("objectsXnbPath", game / "Content" / "Data" / "Objects.xnb")))
    current_xnb_sha = _sha256(xnb_path) if xnb_path.is_file() else None
    xnb_unchanged = current_xnb_sha is not None and current_xnb_sha == marker.get("objectsXnbSha256")
    if current_xnb_sha is None:
        blockers.append("Installed Content/Data/Objects.xnb is missing after the runtime test.")
    elif not xnb_unchanged:
        blockers.append("Installed Content/Data/Objects.xnb changed after the acceptance baseline.")

    log_path = Path(str(marker.get("smapiLogPath") or smapi_log_path())).expanduser().resolve()
    log_text, log_error = _read_log(log_path)
    current_log_sha = _sha256(log_path) if log_text is not None else None
    fresh_runtime_log = current_log_sha is not None and current_log_sha != marker.get("baselineLogSha256")
    evidence = _runtime_evidence(
        log_text or "",
        str(marker.get("projectName") or ""),
        str(marker.get("projectUniqueID") or ""),
    )
    if log_error:
        blockers.append(log_error)
    elif log_text is None:
        blockers.append(f"SMAPI latest log was not found: {log_path}")
    elif not fresh_runtime_log:
        blockers.append("Launch Stardew Valley through SMAPI after beginning acceptance, then verify again.")

    game_version_matches = evidence["gameVersion"] == str(marker.get("targetGameVersion") or TARGET_GAME_VERSION)
    if fresh_runtime_log and evidence["gameVersion"] is None:
        blockers.append("The new log did not contain a recognizable SMAPI/Stardew runtime signature.")
    elif fresh_runtime_log and not game_version_matches:
        blockers.append(f"Runtime Stardew version is {evidence['gameVersion'] or 'unknown'}, expected {TARGET_GAME_VERSION}.")
    if fresh_runtime_log and not evidence["contentPatcherSeen"]:
        blockers.append("The new SMAPI log did not show Content Patcher loading.")
    if fresh_runtime_log and not evidence["projectLoaded"]:
        blockers.append("The new SMAPI log did not list this project as a loaded Content Patcher content pack.")
    if evidence["projectErrors"]:
        blockers.append("SMAPI/Content Patcher reported an error for this Lexeditor content pack.")

    minimum_api = loader.get("contentPatcherMinimumApiVersion")
    api_compatible = _version_at_least(evidence["smapiVersion"], minimum_api)
    if fresh_runtime_log and api_compatible is False:
        blockers.append(
            f"SMAPI {evidence['smapiVersion']} is below Content Patcher's minimum API version {minimum_api}."
        )
    elif fresh_runtime_log and minimum_api and api_compatible is None:
        blockers.append("Could not compare the detected SMAPI version with Content Patcher's minimum API version.")

    accepted = bool(
        fresh_runtime_log
        and xnb_unchanged
        and game_version_matches
        and evidence["contentPatcherSeen"]
        and evidence["projectLoaded"]
        and not evidence["projectErrors"]
        and api_compatible is not False
        and not blockers
    )
    return {
        "started": True,
        "state": "accepted" if accepted else ("failed" if fresh_runtime_log else "waiting-for-run"),
        "accepted": accepted,
        "targetGameVersion": str(marker.get("targetGameVersion") or TARGET_GAME_VERSION),
        "loader": loader,
        "deployment": deployment,
        "projectName": marker.get("projectName"),
        "projectUniqueID": marker.get("projectUniqueID"),
        "objectsXnbPath": str(xnb_path),
        "objectsXnbBaselineSha256": marker.get("objectsXnbSha256"),
        "objectsXnbCurrentSha256": current_xnb_sha,
        "objectsXnbUnchanged": xnb_unchanged,
        "smapiLogPath": str(log_path),
        "baselineLogSha256": marker.get("baselineLogSha256"),
        "currentLogSha256": current_log_sha,
        "freshRuntimeLog": fresh_runtime_log,
        "smapiVersion": evidence["smapiVersion"],
        "gameVersion": evidence["gameVersion"],
        "gameBuild": evidence["gameBuild"],
        "platform": evidence["platform"],
        "gameVersionMatches": game_version_matches,
        "contentPatcherVersionFromLog": evidence["contentPatcherVersion"],
        "contentPatcherSeen": evidence["contentPatcherSeen"],
        "contentPatcherVersionInstalled": loader.get("contentPatcherVersion"),
        "contentPatcherMinimumApiVersion": minimum_api,
        "smapiMeetsContentPatcherMinimum": api_compatible,
        "projectMentioned": evidence["projectMentioned"],
        "projectLoaded": evidence["projectLoaded"],
        "projectLogLines": evidence["projectLines"],
        "projectLoadedLogLines": evidence["projectLoadedLines"],
        "projectErrors": evidence["projectErrors"],
        "blockers": blockers,
    }
