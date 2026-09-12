"""Transactional build snapshots for Palworld official mod packages.

A Lexeditor project is an authoring source. ``build/official-package`` is the
clean package snapshot intended for Pocketpair's official uploader / Workshop
flow. Building never activates a mod, edits PalModSettings.ini, or writes to the
Steam Workshop content directory.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Any

from .package import InfoDocument, PackageValidationError


BUILD_DIRNAME = "build"
PACKAGE_DIRNAME = "official-package"
MANIFEST_NAME = ".lexeditor-palworld-build.json"
MANIFEST_SCHEMA = 1
MAX_BUILD_FILES = 100_000
BACKUP_SUFFIX = ".lexeditor.bak"


class BuildOwnershipError(RuntimeError):
    """Raised when a build target is absent from Lexeditor's ownership record."""


class BuildChangedError(RuntimeError):
    """Raised when an existing Lexeditor build was modified externally."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str, *, allow_root: bool = False) -> Path:
    text = value.strip().replace("\\", "/")
    if not text or text.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", text):
        raise ValueError(f"Unsafe package-relative path: {value!r}")
    parts = PurePosixPath(text).parts
    if ".." in parts:
        raise ValueError(f"Package path escapes the project: {value!r}")
    clean = [part for part in parts if part not in {"", "."}]
    if not clean:
        if allow_root:
            return Path()
        raise ValueError("A package build target may not be the project root")
    return Path(*clean)


def _source_path(project: Path, relative: Path) -> Path:
    project = project.resolve()
    source = (project / relative).resolve()
    if source != project and project not in source.parents:
        raise ValueError(f"Package source escapes the project: {relative.as_posix()}")
    return source


def _is_lexeditor_artifact(path: Path) -> bool:
    name = path.name
    return name.endswith(BACKUP_SUFFIX) or name.startswith(".lexeditor-") or name.endswith(".tmp")


def _iter_source_files(project: Path, relative: Path) -> list[tuple[Path, Path]]:
    source = _source_path(project, relative)
    if not source.exists():
        raise FileNotFoundError(f"Declared package target is missing: {relative.as_posix()}")
    if source.is_symlink():
        raise RuntimeError(f"Package build refuses linked target: {source}")
    if source.is_file():
        if _is_lexeditor_artifact(source):
            return []
        return [(source, relative)]
    if not source.is_dir():
        raise RuntimeError(f"Unsupported package target type: {source}")

    result: list[tuple[Path, Path]] = []
    for path in sorted(source.rglob("*"), key=lambda value: value.as_posix().casefold()):
        if path.is_symlink():
            raise RuntimeError(f"Package build refuses linked content: {path}")
        if not path.is_file() or _is_lexeditor_artifact(path):
            continue
        child_relative = relative / path.relative_to(source)
        result.append((path, child_relative))
        if len(result) > MAX_BUILD_FILES:
            raise RuntimeError(f"Package build exceeds the {MAX_BUILD_FILES}-file safety limit")
    return result


def _validated_info(project: Path) -> tuple[InfoDocument, Path]:
    info_path = project / "Info.json"
    document = InfoDocument.load(info_path)
    errors = [issue for issue in document.issues() if issue.severity == "error"]
    if errors:
        raise PackageValidationError(errors)
    return document, info_path


def _declared_sources(project: Path) -> tuple[InfoDocument, dict[str, Path]]:
    document, info_path = _validated_info(project)
    sources: dict[str, Path] = {"Info.json": info_path}

    thumbnail = document.data.get("Thumbnail")
    if isinstance(thumbnail, str) and thumbnail.strip():
        relative = _safe_relative(thumbnail)
        source = _source_path(project, relative)
        if not source.is_file():
            raise FileNotFoundError(f"Info.json Thumbnail is missing: {relative.as_posix()}")
        if source.is_symlink():
            raise RuntimeError(f"Package build refuses linked thumbnail: {source}")
        sources[relative.as_posix()] = source

    rules = document.data.get("InstallRule", [])
    for rule_index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        targets = rule.get("Targets", [])
        if not isinstance(targets, list):
            continue
        for target_index, target in enumerate(targets):
            if not isinstance(target, str):
                continue
            relative = _safe_relative(target)
            for source, destination in _iter_source_files(project, relative):
                key = destination.as_posix()
                existing = sources.get(key)
                if existing is not None and existing.resolve() != source.resolve():
                    raise RuntimeError(
                        f"Package target collision for {key} from InstallRule[{rule_index}].Targets[{target_index}]"
                    )
                sources[key] = source
                if len(sources) > MAX_BUILD_FILES:
                    raise RuntimeError(f"Package build exceeds the {MAX_BUILD_FILES}-file safety limit")
    return document, sources


def _file_records_from_sources(sources: dict[str, Path]) -> list[dict[str, Any]]:
    records = []
    for relative in sorted(sources, key=str.casefold):
        raw = sources[relative].read_bytes()
        records.append({"path": relative, "size": len(raw), "sha256": sha256_bytes(raw)})
    return records


def _file_records_from_directory(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda value: value.as_posix().casefold()):
        if path.is_symlink():
            raise BuildChangedError(f"Built package now contains a linked file: {path}")
        if not path.is_file():
            continue
        raw = path.read_bytes()
        records.append({
            "path": path.relative_to(root).as_posix(),
            "size": len(raw),
            "sha256": sha256_bytes(raw),
        })
        if len(records) > MAX_BUILD_FILES:
            raise BuildChangedError(f"Built package exceeds the {MAX_BUILD_FILES}-file safety limit")
    return records


def _package_digest(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in records:
        digest.update(str(row["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row["size"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(row["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def _paths(project: Path) -> tuple[Path, Path, Path]:
    project = Path(project).resolve()
    build_root = project / BUILD_DIRNAME
    return build_root, build_root / PACKAGE_DIRNAME, build_root / MANIFEST_NAME


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BuildOwnershipError(f"Could not read Palworld build ownership manifest: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != MANIFEST_SCHEMA:
        raise BuildOwnershipError("Palworld build ownership manifest is invalid")
    if not isinstance(value.get("packageDigest"), str):
        raise BuildOwnershipError("Palworld build ownership manifest has no package digest")
    return value


def desired(project: Path) -> dict[str, Any]:
    project = Path(project).resolve()
    document, sources = _declared_sources(project)
    files = _file_records_from_sources(sources)
    return {
        "packageName": document.data.get("PackageName", ""),
        "sourceInfoSha256": document.source_sha256,
        "packageDigest": _package_digest(files),
        "fileCount": len(files),
        "files": files,
    }


def status(project: Path) -> dict[str, Any]:
    project = Path(project).resolve()
    build_root, target, manifest_path = _paths(project)
    manifest = _load_manifest(manifest_path)
    target_exists = target.exists()
    owned = bool(target_exists and manifest is not None)
    current_digest = ""
    current_matches_manifest = False
    if target_exists:
        if not target.is_dir():
            raise BuildOwnershipError(f"Palworld build target is not a directory: {target}")
        current_records = _file_records_from_directory(target)
        current_digest = _package_digest(current_records)
        current_matches_manifest = bool(manifest and current_digest == manifest.get("packageDigest"))

    wanted = desired(project)
    return {
        "buildRoot": str(build_root),
        "packagePath": str(target),
        "manifestPath": str(manifest_path),
        "built": owned,
        "owned": owned,
        "unownedTarget": bool(target_exists and manifest is None),
        "currentDigest": current_digest,
        "currentMatchesManifest": current_matches_manifest,
        "current": bool(owned and current_matches_manifest and current_digest == wanted["packageDigest"]),
        "desiredDigest": wanted["packageDigest"],
        "packageName": wanted["packageName"],
        "fileCount": wanted["fileCount"],
    }


def build(project: Path) -> dict[str, Any]:
    project = Path(project).resolve()
    build_root, target, manifest_path = _paths(project)
    wanted_document, sources = _declared_sources(project)
    wanted_files = _file_records_from_sources(sources)
    wanted_digest = _package_digest(wanted_files)
    existing_manifest = _load_manifest(manifest_path)

    if target.exists():
        if not target.is_dir():
            raise BuildOwnershipError(f"Palworld build target is not a directory: {target}")
        if existing_manifest is None:
            raise BuildOwnershipError(f"{target} already exists and is not owned by Lexeditor")
        current_digest = _package_digest(_file_records_from_directory(target))
        if current_digest != existing_manifest.get("packageDigest"):
            raise BuildChangedError("The previous Palworld package build changed outside Lexeditor; preserve it or remove it manually before rebuilding.")
        if current_digest == wanted_digest:
            return status(project)
    elif existing_manifest is not None:
        raise BuildOwnershipError("Palworld build manifest exists but its owned package directory is missing")

    build_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".palworld-package-stage-", dir=build_root))
    backup: Path | None = None
    original_manifest = manifest_path.read_bytes() if manifest_path.is_file() else None
    try:
        for relative, source in sources.items():
            destination = staging / Path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        staged_records = _file_records_from_directory(staging)
        staged_digest = _package_digest(staged_records)
        if staged_digest != wanted_digest:
            raise RuntimeError("Palworld package build did not reproduce the validated source snapshot")

        manifest = {
            "schema": MANIFEST_SCHEMA,
            "packageName": wanted_document.data.get("PackageName", ""),
            "sourceInfoSha256": wanted_document.source_sha256,
            "packageDigest": staged_digest,
            "fileCount": len(staged_records),
            "files": staged_records,
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=".palworld-package-old-", dir=build_root))
            backup.rmdir()
            os.replace(target, backup)
        os.replace(staging, target)
        _atomic_write(manifest_path, manifest_bytes)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if target.exists() and not staging.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup is not None and backup.exists():
            os.replace(backup, target)
        if original_manifest is None:
            manifest_path.unlink(missing_ok=True)
        else:
            _atomic_write(manifest_path, original_manifest)
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return status(project)


def revert(project: Path) -> dict[str, Any]:
    project = Path(project).resolve()
    build_root, target, manifest_path = _paths(project)
    manifest = _load_manifest(manifest_path)
    if not target.exists():
        if manifest is not None:
            raise BuildOwnershipError("Palworld build manifest exists but its owned package directory is missing")
        return status(project)
    if manifest is None:
        raise BuildOwnershipError(f"{target} is not owned by Lexeditor")
    current_digest = _package_digest(_file_records_from_directory(target))
    if current_digest != manifest.get("packageDigest"):
        raise BuildChangedError("The Palworld package build changed outside Lexeditor; refusing to delete external changes.")

    quarantine = Path(tempfile.mkdtemp(prefix=".palworld-package-revert-", dir=build_root))
    quarantine.rmdir()
    os.replace(target, quarantine)
    try:
        manifest_path.unlink()
    except BaseException:
        os.replace(quarantine, target)
        raise
    shutil.rmtree(quarantine)
    return status(project)
