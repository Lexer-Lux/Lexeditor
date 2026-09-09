"""Owned local-test deployment into Palworld's official Workshop content root.

Pocketpair's Mod Uploader supports Shift+Create New Mod to bypass Steam
registration and create a local package folder using a random 10-digit number.
Lexeditor mirrors that local-test shape only. It does not publish Workshop items,
write subscribed item folders, or edit PalModSettings.ini.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Any

from . import build as package_build


STEAM_APP_ID = "1623730"
DEPLOY_MANIFEST_NAME = ".lexeditor-palworld-local-workshop.json"
DEPLOY_SCHEMA = 1
MAX_SCAN_PACKAGES = 10_000
MAX_INFO_BYTES = 1024 * 1024


class WorkshopUnavailableError(RuntimeError):
    pass


class WorkshopOwnershipError(RuntimeError):
    pass


class WorkshopChangedError(RuntimeError):
    pass


class PackageNameCollisionError(RuntimeError):
    pass


def _project_paths(project: Path) -> tuple[Path, Path]:
    project = Path(project).resolve()
    build_root = project / package_build.BUILD_DIRNAME
    return build_root, build_root / DEPLOY_MANIFEST_NAME


def workshop_root(game_root: Path | None = None) -> Path | None:
    override = os.environ.get("LEXEDITOR_PALWORLD_WORKSHOP_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if game_root is None:
        value = os.environ.get("LEXEDITOR_PALWORLD_ROOT")
        if not value:
            return None
        game_root = Path(value)
    root = Path(game_root).expanduser().resolve()
    common = root.parent
    steamapps = common.parent
    if common.name.casefold() != "common" or steamapps.name.casefold() != "steamapps":
        return None
    return steamapps / "workshop" / "content" / STEAM_APP_ID


def _ensure_workshop_root(root: Path) -> Path:
    root = Path(root).resolve()
    if root.exists():
        if not root.is_dir():
            raise WorkshopUnavailableError(f"Palworld Workshop root is not a directory: {root}")
        return root
    content = root.parent
    if root.name != STEAM_APP_ID or content.name.casefold() != "content" or not content.is_dir():
        raise WorkshopUnavailableError(
            "Palworld Workshop content root does not exist; select/override the Steam workshop/content/1623730 directory"
        )
    root.mkdir()
    return root


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkshopOwnershipError(f"Could not read Palworld local deployment manifest: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != DEPLOY_SCHEMA:
        raise WorkshopOwnershipError("Palworld local deployment manifest is invalid")
    folder = value.get("folder")
    digest = value.get("packageDigest")
    root = value.get("workshopRoot")
    if not isinstance(folder, str) or not (len(folder) == 10 and folder.isdigit()):
        raise WorkshopOwnershipError("Palworld local deployment manifest has an invalid folder id")
    if not isinstance(digest, str) or len(digest) != 64 or not isinstance(root, str) or not root:
        raise WorkshopOwnershipError("Palworld local deployment manifest is incomplete")
    return value


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _read_package_name(info_path: Path) -> str:
    try:
        raw = info_path.read_bytes()
    except OSError:
        return ""
    if len(raw) > MAX_INFO_BYTES:
        return ""
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(value, dict):
        return ""
    package_name = value.get("PackageName")
    return package_name if isinstance(package_name, str) else ""


def package_name_collisions(root: Path, package_name: str, *, exclude: Path | None = None) -> list[str]:
    if not root.is_dir() or not package_name:
        return []
    collisions: list[str] = []
    checked = 0
    for child in sorted(root.iterdir(), key=lambda value: value.name.casefold()):
        if checked >= MAX_SCAN_PACKAGES:
            raise RuntimeError(f"Workshop scan exceeds the {MAX_SCAN_PACKAGES}-package safety limit")
        checked += 1
        if child.is_symlink() or not child.is_dir():
            continue
        resolved = child.resolve()
        if exclude is not None and resolved == exclude.resolve():
            continue
        if _read_package_name(child / "Info.json") == package_name:
            collisions.append(child.name)
    return collisions


def _new_local_folder(root: Path) -> str:
    for _attempt in range(100):
        # Exactly ten decimal digits, matching Pocketpair's local-test uploader pattern.
        value = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
        if not (root / value).exists():
            return value
    raise RuntimeError("Could not allocate a unique Palworld local Workshop folder")


def _owned_target(manifest: dict[str, Any]) -> Path:
    return (Path(manifest["workshopRoot"]).expanduser().resolve() / manifest["folder"]).resolve()


def status(project: Path, *, game_root: Path | None = None) -> dict[str, Any]:
    project = Path(project).resolve()
    _build_root, manifest_path = _project_paths(project)
    manifest = _load_manifest(manifest_path)
    root = workshop_root(game_root)
    root_ready = bool(root is not None and root.is_dir())
    build_status = package_build.status(project)
    payload: dict[str, Any] = {
        "workshopRoot": str(root) if root is not None else "",
        "workshopRootReady": root_ready,
        "deployed": False,
        "owned": False,
        "current": False,
        "externallyChanged": False,
        "folder": "",
        "targetPath": "",
        "packageName": build_status.get("packageName", ""),
        "buildCurrent": bool(build_status.get("current")),
    }
    if manifest is None:
        return payload
    target = _owned_target(manifest)
    payload.update({
        "owned": True,
        "folder": manifest["folder"],
        "targetPath": str(target),
    })
    if not target.is_dir():
        return payload
    current_digest = package_build._package_digest(package_build._file_records_from_directory(target))
    matches = current_digest == manifest["packageDigest"]
    payload.update({
        "deployed": True,
        "current": bool(matches and current_digest == build_status.get("currentDigest") and build_status.get("current")),
        "externallyChanged": not matches,
        "currentDigest": current_digest,
    })
    return payload


def deploy(project: Path, *, game_root: Path | None = None) -> dict[str, Any]:
    project = Path(project).resolve()
    build_status = package_build.status(project)
    if not build_status.get("current") or not build_status.get("currentMatchesManifest"):
        raise RuntimeError("Build a current clean Palworld package snapshot before local deployment")
    source = Path(build_status["packagePath"]).resolve()
    package_digest = str(build_status["currentDigest"])
    package_name = str(build_status.get("packageName", ""))

    root_candidate = workshop_root(game_root)
    if root_candidate is None:
        raise WorkshopUnavailableError("Could not determine Palworld's Steam Workshop content root")
    root = _ensure_workshop_root(root_candidate)
    build_root, manifest_path = _project_paths(project)
    manifest = _load_manifest(manifest_path)

    if manifest is None:
        collisions = package_name_collisions(root, package_name)
        if collisions:
            raise PackageNameCollisionError(
                f"PackageName {package_name!r} already exists in Workshop folder(s): " + ", ".join(collisions)
            )
        folder = _new_local_folder(root)
        target = root / folder
    else:
        recorded_root = Path(manifest["workshopRoot"]).expanduser().resolve()
        if recorded_root != root:
            raise WorkshopOwnershipError(
                "This project already owns a local deployment in a different Workshop root; remove it before changing roots."
            )
        folder = manifest["folder"]
        target = root / folder
        if target.exists():
            if not target.is_dir():
                raise WorkshopOwnershipError(f"Owned local deployment path is not a directory: {target}")
            current_digest = package_build._package_digest(package_build._file_records_from_directory(target))
            if current_digest != manifest["packageDigest"]:
                raise WorkshopChangedError(
                    "The local Palworld deployment changed outside Lexeditor; refusing to overwrite external changes."
                )
            collisions = package_name_collisions(root, package_name, exclude=target)
            if collisions:
                raise PackageNameCollisionError(
                    f"PackageName {package_name!r} also exists in Workshop folder(s): " + ", ".join(collisions)
                )
            if current_digest == package_digest:
                return status(project, game_root=game_root)
        elif manifest.get("packageDigest"):
            raise WorkshopOwnershipError("Local deployment manifest exists but its owned Workshop folder is missing")

    staging = Path(tempfile.mkdtemp(prefix=".lexeditor-palworld-local-", dir=root))
    backup: Path | None = None
    old_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    try:
        for path in source.rglob("*"):
            if path.is_symlink():
                raise RuntimeError(f"Clean Palworld build unexpectedly contains a link: {path}")
            if not path.is_file():
                continue
            destination = staging / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        staged_digest = package_build._package_digest(package_build._file_records_from_directory(staging))
        if staged_digest != package_digest:
            raise RuntimeError("Local Palworld deployment copy did not match the clean build digest")

        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=".lexeditor-palworld-old-", dir=root))
            backup.rmdir()
            os.replace(target, backup)
        os.replace(staging, target)
        record = {
            "schema": DEPLOY_SCHEMA,
            "workshopRoot": str(root),
            "folder": folder,
            "packageName": package_name,
            "packageDigest": package_digest,
        }
        _atomic_write(
            manifest_path,
            (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if target.exists() and not staging.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup is not None and backup.exists():
            os.replace(backup, target)
        if old_manifest is None:
            manifest_path.unlink(missing_ok=True)
        else:
            _atomic_write(manifest_path, old_manifest)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return status(project, game_root=game_root)


def remove(project: Path, *, game_root: Path | None = None) -> dict[str, Any]:
    project = Path(project).resolve()
    _build_root, manifest_path = _project_paths(project)
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return status(project, game_root=game_root)
    target = _owned_target(manifest)
    if not target.exists():
        raise WorkshopOwnershipError("Local deployment manifest exists but its owned Workshop folder is missing")
    if not target.is_dir():
        raise WorkshopOwnershipError(f"Owned local deployment path is not a directory: {target}")
    current_digest = package_build._package_digest(package_build._file_records_from_directory(target))
    if current_digest != manifest["packageDigest"]:
        raise WorkshopChangedError(
            "The local Palworld deployment changed outside Lexeditor; refusing to delete external changes."
        )

    quarantine = Path(tempfile.mkdtemp(prefix=".lexeditor-palworld-remove-", dir=target.parent))
    quarantine.rmdir()
    os.replace(target, quarantine)
    try:
        manifest_path.unlink()
    except BaseException:
        os.replace(quarantine, target)
        raise
    shutil.rmtree(quarantine)
    return status(project, game_root=game_root)
