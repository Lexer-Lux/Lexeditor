"""Reversible Windows dedicated-server package deployment and activation.

Pocketpair documents Windows dedicated servers as loading package sources from
``<PalServer>/Mods/Workshop/<any-folder>/Info.json`` and requires operators to
edit ``Mods/PalModSettings.ini`` directly. Lexeditor owns only its deterministic
Workshop source folder and, when asked to activate, records an exact-byte backup
of the settings file so rollback can be stale-guarded and byte-exact.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from . import build as package_build
from . import loader_state
from . import workshop as client_workshop


SERVER_APP_ID = "2394010"
DEPLOY_MANIFEST_NAME = ".lexeditor-palworld-dedicated-deploy.json"
ACTIVATION_MANIFEST_NAME = ".lexeditor-palworld-dedicated-activation.json"
ACTIVATION_BACKUP_NAME = ".lexeditor-palworld-dedicated-PalModSettings.ini.bak"
MANIFEST_SCHEMA = 1


class DedicatedServerUnavailableError(RuntimeError):
    pass


class DedicatedServerOwnershipError(RuntimeError):
    pass


class DedicatedServerChangedError(RuntimeError):
    pass


class DedicatedServerRefreshError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _project_paths(project: Path) -> tuple[Path, Path, Path, Path]:
    build_root = Path(project).resolve() / package_build.BUILD_DIRNAME
    return (
        build_root,
        build_root / DEPLOY_MANIFEST_NAME,
        build_root / ACTIVATION_MANIFEST_NAME,
        build_root / ACTIVATION_BACKUP_NAME,
    )


def resolve_server_root(client_root: Path | None = None, explicit: Path | None = None) -> Path | None:
    """Resolve a Windows PalServer root without scanning arbitrary disks."""
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    override = os.environ.get("LEXEDITOR_PALWORLD_SERVER_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if client_root is None:
        value = os.environ.get("LEXEDITOR_PALWORLD_ROOT")
        client_root = Path(value).expanduser().resolve() if value else None
    if client_root is not None:
        root = Path(client_root).expanduser().resolve()
        if root.parent.name.casefold() == "common":
            return root.parent / "PalServer"
    if os.name == "nt":
        return Path(r"C:\Program Files (x86)\Steam\steamapps\common\PalServer")
    return None


def _require_server_root(
    server_root: Path | None = None,
    *,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> Path:
    if os.name != "nt" and not allow_non_windows:
        raise DedicatedServerUnavailableError(
            "Pocketpair's official mod loader supports dedicated-server mods on Windows only."
        )
    root = resolve_server_root(client_root, explicit=server_root)
    if root is None:
        raise DedicatedServerUnavailableError("No Palworld dedicated-server root is selected")
    root = Path(root).resolve()
    if not (root / "PalServer.exe").is_file():
        raise DedicatedServerUnavailableError(f"PalServer.exe was not found under {root}")
    return root


def _load_json_manifest(path: Path, *, kind: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DedicatedServerOwnershipError(f"Could not read {kind} ownership manifest: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != MANIFEST_SCHEMA:
        raise DedicatedServerOwnershipError(f"Palworld dedicated-server {kind} ownership manifest is invalid")
    return value


def _build_identity(project: Path) -> tuple[dict[str, Any], Path, str, str, str, bool]:
    build_status = package_build.status(project)
    if not build_status.get("current") or not build_status.get("currentMatchesManifest"):
        raise RuntimeError("Build a current clean Palworld package snapshot before dedicated-server deployment")
    source = Path(str(build_status["packagePath"])).resolve()
    package_name, version, debug_mode = client_workshop._loader_identity(source)
    digest = str(build_status["currentDigest"])
    info = json.loads((source / "Info.json").read_text(encoding="utf-8-sig"))
    if not isinstance(info, dict):
        raise RuntimeError("Clean Palworld build Info.json root must be an object")
    has_server_rule = any(
        isinstance(rule, dict) and rule.get("IsServer") is True
        for rule in info.get("InstallRule", [])
    )
    if not has_server_rule:
        raise RuntimeError('Dedicated-server deployment requires at least one InstallRule with "IsServer": true')
    return build_status, source, digest, package_name, version, debug_mode


def _target_name(package_name: str) -> str:
    if not package_name or not package_name.isalnum():
        raise RuntimeError("Dedicated-server PackageName must be alphanumeric")
    return f"Lexeditor-{package_name}"


def _target_digest(target: Path) -> str:
    if target.is_symlink():
        raise DedicatedServerChangedError(
            "The owned dedicated-server package folder was replaced by a link; refusing to follow it."
        )
    if not target.is_dir():
        raise DedicatedServerOwnershipError(f"Owned dedicated-server package path is not a directory: {target}")
    return package_build._package_digest(package_build._file_records_from_directory(target))


def _deployment_target(root: Path, package_name: str) -> Path:
    workshop_root = root / "Mods" / "Workshop"
    target = workshop_root / _target_name(package_name)
    if target.parent.resolve() != workshop_root.resolve():
        raise DedicatedServerOwnershipError("Dedicated-server package target escapes Mods/Workshop")
    return target


def _deployment_status(project: Path, root: Path | None) -> dict[str, Any]:
    _build_root, manifest_path, _activation_manifest, _backup = _project_paths(project)
    manifest = _load_json_manifest(manifest_path, kind="deployment")
    payload: dict[str, Any] = {
        "deployed": False,
        "owned": manifest is not None,
        "current": False,
        "externallyChanged": False,
        "rootMismatch": False,
        "targetPath": "",
        "deployedVersion": "",
        "deployedDebugMode": False,
    }
    if manifest is None:
        return payload
    package_name = str(manifest.get("packageName", ""))
    payload["deployedVersion"] = str(manifest.get("version", ""))
    payload["deployedDebugMode"] = manifest.get("debugMode") is True
    recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
    if root is None or recorded_root != root.resolve():
        payload["rootMismatch"] = True
        return payload
    target = _deployment_target(root, package_name)
    payload["targetPath"] = str(target)
    if target.is_symlink():
        payload["externallyChanged"] = True
        return payload
    if not target.exists():
        return payload
    if not target.is_dir():
        payload["externallyChanged"] = True
        return payload
    current_digest = package_build._package_digest(package_build._file_records_from_directory(target))
    matches = current_digest == manifest.get("packageDigest")
    build_status = package_build.status(project)
    payload.update({
        "deployed": True,
        "current": bool(matches and build_status.get("current") and current_digest == build_status.get("currentDigest")),
        "externallyChanged": not matches,
        "currentDigest": current_digest,
    })
    return payload


def _activation_status(project: Path, root: Path | None, package_name: str) -> dict[str, Any]:
    _build_root, _deploy_manifest, activation_manifest_path, backup_path = _project_paths(project)
    manifest = _load_json_manifest(activation_manifest_path, kind="activation")
    loader = loader_state.status(root, package_name) if root is not None else loader_state.status(None, package_name)
    payload: dict[str, Any] = {
        **loader,
        "activationOwned": manifest is not None,
        "activationExternallyChanged": False,
        "activationRootMismatch": False,
        "activationBackupReady": backup_path.is_file(),
    }
    if manifest is None:
        return payload
    recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
    if root is None or recorded_root != root.resolve() or str(manifest.get("packageName", "")) != package_name:
        payload["activationRootMismatch"] = True
        return payload
    settings = root / "Mods" / "PalModSettings.ini"
    if not settings.is_file():
        payload["activationExternallyChanged"] = True
        return payload
    current_sha = _sha256(settings.read_bytes())
    payload["activationExternallyChanged"] = current_sha != str(manifest.get("postSha256", ""))
    return payload


def status(
    project: Path,
    *,
    server_root: Path | None = None,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> dict[str, Any]:
    project = Path(project).resolve()
    root_candidate = resolve_server_root(client_root, explicit=server_root)
    supported = os.name == "nt" or allow_non_windows
    root_ready = bool(root_candidate is not None and (Path(root_candidate) / "PalServer.exe").is_file())
    root = Path(root_candidate).resolve() if root_ready else None
    try:
        build_status = package_build.status(project)
        package_name = str(build_status.get("packageName", ""))
        build_current = bool(build_status.get("current"))
        server_rule = False
        if build_current:
            info = json.loads((Path(str(build_status["packagePath"])) / "Info.json").read_text(encoding="utf-8-sig"))
            server_rule = bool(isinstance(info, dict) and any(
                isinstance(rule, dict) and rule.get("IsServer") is True for rule in info.get("InstallRule", [])
            ))
    except Exception:
        package_name, build_current, server_rule = "", False, False
    deployment = _deployment_status(project, root)
    activation = _activation_status(project, root, package_name)
    return {
        "platformSupported": supported,
        "serverRoot": str(root_candidate) if root_candidate is not None else "",
        "serverRootReady": root_ready,
        "serverAppId": SERVER_APP_ID,
        "packageName": package_name,
        "buildCurrent": build_current,
        "serverRule": server_rule,
        "deployment": deployment,
        "loader": activation,
        "restartRequired": bool(deployment.get("deployed") or activation.get("active")),
        "note": "Restart PalServer.exe to make the official loader deploy configuration changes.",
    }


def deploy(
    project: Path,
    *,
    server_root: Path | None = None,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> dict[str, Any]:
    project = Path(project).resolve()
    root = _require_server_root(server_root, client_root=client_root, allow_non_windows=allow_non_windows)
    _build_status, source, package_digest, package_name, version, debug_mode = _build_identity(project)
    workshop_root = root / "Mods" / "Workshop"
    workshop_root.mkdir(parents=True, exist_ok=True)
    target = _deployment_target(root, package_name)
    _build_root, manifest_path, _activation_manifest, _backup = _project_paths(project)
    manifest = _load_json_manifest(manifest_path, kind="deployment")

    if manifest is None:
        collisions = client_workshop.package_name_collisions(workshop_root, package_name)
        if collisions:
            raise DedicatedServerOwnershipError(
                f"PackageName {package_name!r} already exists in dedicated-server Workshop folder(s): "
                + ", ".join(collisions)
            )
        if target.exists() or target.is_symlink():
            raise DedicatedServerOwnershipError(f"Dedicated-server package target already exists and is not owned: {target}")
    else:
        recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
        if recorded_root != root or str(manifest.get("packageName", "")) != package_name:
            raise DedicatedServerOwnershipError(
                "Dedicated-server deployment identity changed; remove the existing owned deployment first."
            )
        if target.is_symlink():
            raise DedicatedServerChangedError("Owned dedicated-server package folder was replaced by a link")
        if not target.exists():
            raise DedicatedServerOwnershipError("Dedicated-server deployment manifest exists but its owned folder is missing")
        current_digest = _target_digest(target)
        if current_digest != str(manifest.get("packageDigest", "")):
            raise DedicatedServerChangedError("Dedicated-server package changed outside Lexeditor; refusing to overwrite it")
        collisions = client_workshop.package_name_collisions(workshop_root, package_name, exclude=target)
        if collisions:
            raise DedicatedServerOwnershipError(
                f"PackageName {package_name!r} also exists in dedicated-server Workshop folder(s): "
                + ", ".join(collisions)
            )
        if current_digest == package_digest:
            return status(project, server_root=root, allow_non_windows=allow_non_windows)
        deployed_version = str(manifest.get("version", ""))
        if not debug_mode and deployed_version and version == deployed_version:
            raise DedicatedServerRefreshError(
                "The dedicated-server package changed but Version is unchanged and DebugMode is false; "
                "the official loader would keep the old installed copy after restart. Change Version or enable DebugMode."
            )

    staging = Path(tempfile.mkdtemp(prefix=".lexeditor-palserver-stage-", dir=workshop_root))
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
            raise RuntimeError("Dedicated-server package staging digest did not match the clean build")
        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=".lexeditor-palserver-old-", dir=workshop_root))
            backup.rmdir()
            os.replace(target, backup)
        os.replace(staging, target)
        record = {
            "schema": MANIFEST_SCHEMA,
            "serverRoot": str(root),
            "target": str(target),
            "packageName": package_name,
            "packageDigest": package_digest,
            "version": version,
            "debugMode": debug_mode,
        }
        _atomic_write(manifest_path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if target.exists() and not target.is_symlink() and not staging.exists():
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
    return status(project, server_root=root, allow_non_windows=allow_non_windows)


def _decode_settings(raw: bytes) -> tuple[str, bytes]:
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    try:
        text = raw[len(bom):].decode("utf-8")
    except UnicodeDecodeError as error:
        raise DedicatedServerOwnershipError(f"PalModSettings.ini is not valid UTF-8: {error}") from error
    return text, bom


def _enable_settings(raw: bytes, package_name: str) -> bytes:
    """Enable one package while preserving unrelated settings and formatting."""
    text, bom = _decode_settings(raw)
    newline = "\r\n" if "\r\n" in text else "\n"
    final_newline = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            name = stripped[1:-1].strip().casefold()
            if name == "palmodsettings":
                section_start = index
                continue
            if section_start is not None:
                section_end = index
                break
    if section_start is None:
        raise DedicatedServerOwnershipError(
            "PalModSettings.ini has no [PalModSettings] section; launch the dedicated server once to generate it."
        )

    global_index: int | None = None
    active_names: list[str] = []
    for index in range(section_start + 1, section_end):
        line = lines[index]
        if line.lstrip().startswith((";", "#")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        folded = key.strip().casefold()
        if folded == "bglobalenablemod":
            global_index = index
        elif folded == "activemodlist":
            active_names.append(value.strip())

    if global_index is None:
        lines.insert(section_start + 1, "bGlobalEnableMod=True")
        section_end += 1
    else:
        line = lines[global_index]
        match = re.match(r"^(\s*bGlobalEnableMod\s*=\s*)(.*?)(\s*)$", line, flags=re.I)
        lines[global_index] = (match.group(1) + "True" + match.group(3)) if match else "bGlobalEnableMod=True"

    if package_name not in active_names:
        lines.insert(section_end, f"ActiveModList={package_name}")

    updated = newline.join(lines) + (newline if final_newline else "")
    return bom + updated.encode("utf-8")


def enable(
    project: Path,
    *,
    server_root: Path | None = None,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> dict[str, Any]:
    project = Path(project).resolve()
    root = _require_server_root(server_root, client_root=client_root, allow_non_windows=allow_non_windows)
    current_status = status(project, server_root=root, allow_non_windows=allow_non_windows)
    deployment = current_status["deployment"]
    if not deployment.get("current"):
        raise RuntimeError("Deploy the current package to the dedicated server before enabling it")
    package_name = str(current_status.get("packageName", ""))
    settings = root / "Mods" / "PalModSettings.ini"
    if not settings.is_file():
        raise DedicatedServerUnavailableError(
            "PalModSettings.ini does not exist; launch the dedicated server once, stop it, then enable the package."
        )
    _build_root, _deploy_manifest, manifest_path, backup_path = _project_paths(project)
    manifest = _load_json_manifest(manifest_path, kind="activation")
    if manifest is not None:
        recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
        if recorded_root != root or str(manifest.get("packageName", "")) != package_name:
            raise DedicatedServerOwnershipError("Owned dedicated-server activation belongs to a different server/package")
        current = settings.read_bytes()
        if _sha256(current) != str(manifest.get("postSha256", "")):
            raise DedicatedServerChangedError("PalModSettings.ini changed outside Lexeditor after activation")
        return status(project, server_root=root, allow_non_windows=allow_non_windows)

    external_state = loader_state.status(root, package_name)
    if external_state.get("active") is True:
        return current_status

    original = settings.read_bytes()
    updated = _enable_settings(original, package_name)
    if updated == original:
        return current_status
    original_sha = _sha256(original)
    post_sha = _sha256(updated)
    try:
        _atomic_write(backup_path, original)
        _atomic_write(settings, updated)
        record = {
            "schema": MANIFEST_SCHEMA,
            "serverRoot": str(root),
            "packageName": package_name,
            "originalSha256": original_sha,
            "postSha256": post_sha,
        }
        _atomic_write(manifest_path, (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    except BaseException:
        if settings.is_file() and _sha256(settings.read_bytes()) == post_sha:
            _atomic_write(settings, original)
        manifest_path.unlink(missing_ok=True)
        backup_path.unlink(missing_ok=True)
        raise
    return status(project, server_root=root, allow_non_windows=allow_non_windows)


def revert_activation(
    project: Path,
    *,
    server_root: Path | None = None,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> dict[str, Any]:
    project = Path(project).resolve()
    root = _require_server_root(server_root, client_root=client_root, allow_non_windows=allow_non_windows)
    _build_root, _deploy_manifest, manifest_path, backup_path = _project_paths(project)
    manifest = _load_json_manifest(manifest_path, kind="activation")
    if manifest is None:
        return status(project, server_root=root, allow_non_windows=allow_non_windows)
    package_name = str(manifest.get("packageName", ""))
    recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
    if recorded_root != root:
        raise DedicatedServerOwnershipError("Owned dedicated-server activation belongs to a different server root")
    settings = root / "Mods" / "PalModSettings.ini"
    if not settings.is_file() or not backup_path.is_file():
        raise DedicatedServerOwnershipError("Owned dedicated-server activation recovery data is missing")
    current = settings.read_bytes()
    if _sha256(current) != str(manifest.get("postSha256", "")):
        raise DedicatedServerChangedError("PalModSettings.ini changed outside Lexeditor; refusing to overwrite external changes")
    original = backup_path.read_bytes()
    if _sha256(original) != str(manifest.get("originalSha256", "")):
        raise DedicatedServerOwnershipError("Dedicated-server activation backup digest does not match its manifest")
    _atomic_write(settings, original)
    manifest_path.unlink()
    backup_path.unlink()
    return status(project, server_root=root, allow_non_windows=allow_non_windows)


def remove(
    project: Path,
    *,
    server_root: Path | None = None,
    client_root: Path | None = None,
    allow_non_windows: bool = False,
) -> dict[str, Any]:
    project = Path(project).resolve()
    root = _require_server_root(server_root, client_root=client_root, allow_non_windows=allow_non_windows)
    current_status = status(project, server_root=root, allow_non_windows=allow_non_windows)
    loader = current_status["loader"]
    if loader.get("activationOwned"):
        raise DedicatedServerOwnershipError("Revert the Lexeditor-owned server activation before removing its package source")
    if loader.get("listed"):
        raise DedicatedServerOwnershipError(
            "The package is still listed in PalModSettings.ini; disable it there before removing the server package source."
        )
    _build_root, manifest_path, _activation_manifest, _backup = _project_paths(project)
    manifest = _load_json_manifest(manifest_path, kind="deployment")
    if manifest is None:
        return current_status
    recorded_root = Path(str(manifest.get("serverRoot", ""))).expanduser().resolve()
    package_name = str(manifest.get("packageName", ""))
    if recorded_root != root:
        raise DedicatedServerOwnershipError("Owned dedicated-server deployment belongs to a different server root")
    target = _deployment_target(root, package_name)
    if target.is_symlink():
        raise DedicatedServerChangedError("Owned dedicated-server package folder was replaced by a link")
    if not target.exists():
        raise DedicatedServerOwnershipError("Dedicated-server deployment manifest exists but its owned folder is missing")
    if _target_digest(target) != str(manifest.get("packageDigest", "")):
        raise DedicatedServerChangedError("Dedicated-server package changed outside Lexeditor; refusing to delete it")
    quarantine = Path(tempfile.mkdtemp(prefix=".lexeditor-palserver-remove-", dir=target.parent))
    quarantine.rmdir()
    os.replace(target, quarantine)
    try:
        manifest_path.unlink()
    except BaseException:
        os.replace(quarantine, target)
        raise
    shutil.rmtree(quarantine)
    return status(project, server_root=root, allow_non_windows=allow_non_windows)
