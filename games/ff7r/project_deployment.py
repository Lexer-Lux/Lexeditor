"""Ownership-guarded deployment for Lexeditor's FF7R project PAK.

The editor's direct Build & Deploy path writes one well-known archive beside
third-party PAKs. A filename alone is not ownership. This module records the
exact deployed digest in a sibling marker and refuses to replace or delete a
file unless that marker still proves Lexeditor created the current bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil


def _active_pak_conflicts(game_root: Path, built: Path) -> list[dict]:
    """Return exact asset-path collisions with other active ~mods PAKs.

    FF7R/Unreal can resolve colliding archives by load order, but Lexeditor does
    not guess a winner for user data. Listing PAK indexes is enough to detect
    the ambiguity and does not extract or modify third-party content.
    """
    from .tooling import list_pak

    root = Path(game_root) / "End" / "Content" / "Paks" / "~mods"
    target = deployed_pak_path(game_root)
    if not root.is_dir():
        return []
    others = [
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.casefold() == ".pak"
        and path.resolve() != target.resolve()
    ]
    if not others:
        return []

    mine = {entry.casefold(): entry for entry in list_pak(built)}
    conflicts = []
    for package in sorted(others, key=lambda path: path.as_posix().casefold()):
        for entry in list_pak(package):
            key = entry.casefold()
            if key in mine:
                conflicts.append({
                    "asset": mine[key],
                    "package": str(package.relative_to(root)),
                })
    return conflicts


DEPLOYMENT_SCHEMA_VERSION = 1
DEPLOYED_PAK_NAME = "Lexeditor-FF7R_P.pak"
MARKER_NAME = DEPLOYED_PAK_NAME + ".lexeditor.json"


def deployed_pak_path(game_root: Path) -> Path:
    return Path(game_root) / "End" / "Content" / "Paks" / "~mods" / DEPLOYED_PAK_NAME


def marker_path(game_root: Path) -> Path:
    return deployed_pak_path(game_root).with_name(MARKER_NAME)


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validated_marker(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read FF7R deployment ownership marker: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("FF7R deployment ownership marker must be an object")
    if value.get("schemaVersion") != DEPLOYMENT_SCHEMA_VERSION:
        raise ValueError("Unsupported FF7R deployment ownership marker version")
    if value.get("pluginId") != "ff7r" or value.get("filename") != DEPLOYED_PAK_NAME:
        raise ValueError("FF7R deployment marker does not identify this plugin archive")
    digest = value.get("sha256")
    size = value.get("size")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("FF7R deployment marker has an invalid SHA-256")
    try:
        int(digest, 16)
    except ValueError as error:
        raise ValueError("FF7R deployment marker has an invalid SHA-256") from error
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError("FF7R deployment marker has an invalid size")
    return value


def deployment_status(game_root: Path) -> dict:
    target = deployed_pak_path(game_root)
    marker = marker_path(game_root)
    target_exists = target.is_file()
    marker_exists = marker.is_file()
    result = {
        "path": str(target),
        "markerPath": str(marker),
        "exists": target_exists,
        "markerExists": marker_exists,
        "managed": False,
        "state": "absent",
        "sha256": "",
        "size": target.stat().st_size if target_exists else 0,
        "error": "",
    }
    if not marker_exists:
        if target_exists:
            result["state"] = "unmanaged"
            result["error"] = (
                "A PAK already exists at Lexeditor's deployment filename without an ownership marker. "
                "Lexeditor will preserve it."
            )
        return result

    try:
        owned = _validated_marker(marker)
    except ValueError as error:
        result["state"] = "marker-error"
        result["error"] = str(error)
        return result

    result["sha256"] = str(owned["sha256"])
    if not target_exists:
        result["state"] = "stale-marker"
        result["error"] = "Lexeditor's ownership marker remains, but the deployed PAK is missing."
        return result

    actual = _digest(target)
    if target.stat().st_size != owned["size"] or actual != owned["sha256"]:
        result["state"] = "changed"
        result["error"] = (
            "The deployed PAK changed after Lexeditor wrote it. Lexeditor will not replace or remove it."
        )
        result["actualSha256"] = actual
        return result

    result["state"] = "managed"
    result["managed"] = True
    result["sha256"] = actual
    return result


def _write_marker(target: Path, *, sha256: str, size: int) -> Path:
    marker = target.with_name(MARKER_NAME)
    value = {
        "schemaVersion": DEPLOYMENT_SCHEMA_VERSION,
        "pluginId": "ff7r",
        "filename": DEPLOYED_PAK_NAME,
        "sha256": sha256,
        "size": size,
    }
    temporary = marker.with_suffix(marker.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, marker)
    return marker


def deploy_built_pak(game_root: Path, built: Path) -> dict:
    built = Path(built).resolve()
    if not built.is_file() or built.stat().st_size <= 0:
        raise FileNotFoundError(f"Built FF7R mod PAK does not exist: {built}")

    target = deployed_pak_path(game_root)
    marker = marker_path(game_root)
    status = deployment_status(game_root)
    if target.is_file() and not status["managed"]:
        raise RuntimeError(status["error"] or (
            "The FF7R deployment target is not proven to be owned by Lexeditor; refusing to overwrite it."
        ))
    if not target.is_file() and marker.is_file() and status["state"] == "marker-error":
        raise RuntimeError(status["error"])

    conflicts = _active_pak_conflicts(game_root, built)
    if conflicts:
        preview = "; ".join(
            f"{row['asset']} ({row['package']})" for row in conflicts[:4]
        )
        extra = len(conflicts) - min(len(conflicts), 4)
        if extra:
            preview += f"; +{extra} more"
        raise RuntimeError(
            "Built FF7R PAK conflicts with another active mod. "
            "Lexeditor will not guess a PAK load-order winner: " + preview
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".lexeditor.tmp")
    try:
        shutil.copy2(built, temporary)
        expected = _digest(built)
        actual = _digest(temporary)
        if actual != expected or temporary.stat().st_size != built.stat().st_size:
            raise RuntimeError("FF7R deployed PAK staging copy failed digest/readback validation")
        os.replace(temporary, target)
        _write_marker(target, sha256=actual, size=target.stat().st_size)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    after = deployment_status(game_root)
    if not after["managed"] or after["sha256"] != expected:
        raise RuntimeError("FF7R deployed PAK failed ownership/readback validation")
    return after


def remove_deployed_pak(game_root: Path) -> dict:
    target = deployed_pak_path(game_root)
    marker = marker_path(game_root)
    status = deployment_status(game_root)

    if not target.exists() and not marker.exists():
        return {**status, "removed": False}

    if not target.exists():
        if status["state"] != "stale-marker":
            raise RuntimeError(status["error"] or "FF7R deployment ownership marker is not valid")
        marker.unlink()
        return {**deployment_status(game_root), "removed": False, "markerRemoved": True}

    if not status["managed"]:
        raise RuntimeError(status["error"] or (
            "The FF7R deployment target is not proven to be owned by Lexeditor; refusing to remove it."
        ))

    target.unlink()
    marker.unlink()
    after = deployment_status(game_root)
    return {**after, "removed": True}
