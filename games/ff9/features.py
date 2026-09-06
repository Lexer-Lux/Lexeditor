"""Lexeditor-owned FF9 feature toggles and transactional Memoria mod deployment.

This is intentionally separate from Memoria's settings UI. Lexeditor only owns
its own mod folder and the single FolderNames entry required for Memoria to load
that folder; every unrelated Memoria.ini byte is preserved.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Iterable

from . import memoria_manager, paths

MOD_NAME = "Lexeditor"
CONFIG_NAME = "lexeditor-ff9.ini"
RUNTIME_NAME = "Memoria.Scripts.Lexeditor.dll"
MARKER_NAME = ".lexeditor-ff9-owned"
PROJECT_CONFIG = paths.PROJECT_ROOT / CONFIG_NAME
RUNTIME_SOURCE = paths.PLUGIN_ROOT / "runtime" / RUNTIME_NAME
DEPLOY_ROOT = paths.GAME_ROOT / MOD_NAME
FEATURE_KEYS = ("ImprovedInterface", "BetterEat")


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(path: Path) -> str:
    return _digest_bytes(path.read_bytes()) if path.is_file() else ""


def _encode(values: dict[str, bool]) -> bytes:
    text = "[Features]\r\n" + "".join(
        f"{key} = {'1' if values.get(key, False) else '0'}\r\n" for key in FEATURE_KEYS
    )
    return text.encode("utf-8")


def load(project_root: Path | None = None) -> dict:
    root = Path(project_root or paths.PROJECT_ROOT)
    target = root / CONFIG_NAME
    values = {key: False for key in FEATURE_KEYS}
    if target.is_file():
        text = target.read_text(encoding="utf-8-sig", errors="strict")
        for line in text.splitlines():
            if "=" not in line or line.lstrip().startswith((";", "#")):
                continue
            key, raw = (part.strip() for part in line.split("=", 1))
            if key in values:
                values[key] = raw.casefold() in {"1", "true", "yes", "on"}
    return {"features": values, "sha256": _digest(target), "path": str(target)}


def save(values: dict, expected_sha256: str, project_root: Path | None = None) -> dict:
    if not isinstance(values, dict) or any(key not in FEATURE_KEYS for key in values):
        raise ValueError("Unknown FF9 feature setting")
    root = Path(project_root or paths.PROJECT_ROOT)
    target = root / CONFIG_NAME
    current = _digest(target)
    if current != str(expected_sha256 or ""):
        raise RuntimeError("The FF9 feature settings changed outside Lexeditor. Reload before saving.")
    clean: dict[str, bool] = {}
    previous = load(root)["features"]
    for key in FEATURE_KEYS:
        value = values.get(key, previous[key])
        if type(value) is not bool:
            raise ValueError(f"{key} must be true or false")
        clean[key] = value
    data = _encode(clean)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
    return load(root)


def _decode_ini(raw: bytes) -> tuple[str, str, bytes]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), "utf-8", b"\xef\xbb\xbf"
    try:
        return raw.decode("utf-8"), "utf-8", b""
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252", b""


def _split_folder_names(raw_value: str) -> list[str]:
    return re.findall(r'"([^"]*)"', raw_value)


def _folder_line(names: Iterable[str], prefix: str = "FolderNames = ") -> str:
    return prefix + ", ".join(f'"{name}"' for name in names)


def _edit_folder_names(raw: bytes, *, add: bool) -> bytes:
    text, encoding, bom = _decode_ini(raw)
    newline = "\r\n" if "\r\n" in text else "\n"
    had_final = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    in_mod = False
    found = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_mod = stripped.casefold() == "[mod]"
            continue
        if not in_mod:
            continue
        match = re.match(r"^(\s*FolderNames\s*=\s*)(.*)$", line, flags=re.I)
        if not match:
            continue
        found = True
        names = _split_folder_names(match.group(2))
        names = [name for name in names if name.casefold() != MOD_NAME.casefold()]
        if add:
            names.insert(0, MOD_NAME)
        lines[index] = _folder_line(names, match.group(1))
        break
    if not found:
        raise RuntimeError("Memoria.ini has no [Mod] FolderNames setting")
    updated = newline.join(lines) + (newline if had_final else "")
    return bom + updated.encode(encoding)


def _iter_project_files(project_root: Path) -> list[tuple[Path, Path]]:
    source = project_root / "StreamingAssets"
    if not source.is_dir():
        return []
    result: list[tuple[Path, Path]] = []
    for path in source.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"FF9 project deployment refuses linked files: {path}")
        if path.is_file():
            relative = path.relative_to(project_root)
            if ".." in relative.parts:
                raise RuntimeError("Unsafe FF9 project path")
            result.append((path, relative))
    return result


def status(game_root: Path | None = None, project_root: Path | None = None,
           runtime_source: Path | None = None) -> dict:
    game = Path(game_root or paths.GAME_ROOT)
    project = Path(project_root or paths.PROJECT_ROOT)
    runtime = Path(runtime_source or RUNTIME_SOURCE)
    deployed = game / MOD_NAME
    marker = deployed / MARKER_NAME
    target_runtime = deployed / "StreamingAssets" / "Scripts" / RUNTIME_NAME
    ini = game / "Memoria.ini"
    active = False
    if ini.is_file():
        try:
            text, _, _ = _decode_ini(ini.read_bytes())
            match = re.search(r"(?im)^\s*FolderNames\s*=\s*(.*)$", text)
            active = bool(match and any(name.casefold() == MOD_NAME.casefold()
                                        for name in _split_folder_names(match.group(1))))
        except Exception:
            active = False
    source_hash = _digest(runtime)
    target_hash = _digest(target_runtime)
    return {
        "deployed": marker.is_file() and target_runtime.is_file() and active,
        "active": active,
        "runtimeReady": runtime.is_file(),
        "runtimeSha256": source_hash,
        "deployedRuntimeSha256": target_hash,
        "runtimeCurrent": bool(source_hash) and source_hash == target_hash,
        "gameModPath": str(deployed),
        "projectPath": str(project),
        "features": load(project)["features"],
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def deploy(game_root: Path | None = None, project_root: Path | None = None,
           runtime_source: Path | None = None) -> dict:
    game = Path(game_root or paths.GAME_ROOT).resolve()
    project = Path(project_root or paths.PROJECT_ROOT).resolve()
    runtime = Path(runtime_source or RUNTIME_SOURCE).resolve()
    if not runtime.is_file():
        raise FileNotFoundError(f"The Lexeditor FF9 runtime is missing: {runtime}")
    if not memoria_manager.status(game)["installed"]:
        raise RuntimeError("Install Memoria before deploying the FF9 project")
    files = _iter_project_files(project)
    target = game / MOD_NAME
    marker = target / MARKER_NAME
    if target.exists() and not marker.is_file():
        raise RuntimeError(f"{target} already exists and is not owned by Lexeditor")
    config = load(project)
    ini = game / "Memoria.ini"
    original_ini = ini.read_bytes()
    with memoria_manager.configuration_write(game):
        staging = Path(tempfile.mkdtemp(prefix="Lexeditor.ff9-stage-", dir=game))
        backup = None
        try:
            for source, relative in files:
                destination = staging / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            scripts = staging / "StreamingAssets" / "Scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            shutil.copy2(runtime, scripts / RUNTIME_NAME)
            _atomic_write(staging / CONFIG_NAME, _encode(config["features"]))
            _atomic_write(staging / MARKER_NAME,
                          ("Lexeditor FF9 managed mod\n" + _digest(runtime) + "\n").encode("ascii"))
            if target.exists():
                backup = Path(tempfile.mkdtemp(prefix="Lexeditor.ff9-old-", dir=game))
                backup.rmdir()
                os.replace(target, backup)
            os.replace(staging, target)
            _atomic_write(ini, _edit_folder_names(original_ini, add=True))
            if backup and backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if target.exists() and marker.is_file():
                shutil.rmtree(target, ignore_errors=True)
            if backup and backup.exists():
                os.replace(backup, target)
            if ini.exists():
                _atomic_write(ini, original_ini)
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise
    return status(game, project, runtime)


def revert(game_root: Path | None = None, project_root: Path | None = None,
           runtime_source: Path | None = None) -> dict:
    game = Path(game_root or paths.GAME_ROOT).resolve()
    project = Path(project_root or paths.PROJECT_ROOT).resolve()
    runtime = Path(runtime_source or RUNTIME_SOURCE).resolve()
    target = game / MOD_NAME
    marker = target / MARKER_NAME
    if target.exists() and not marker.is_file():
        raise RuntimeError(f"{target} is not owned by Lexeditor")
    ini = game / "Memoria.ini"
    with memoria_manager.configuration_write(game):
        original_ini = ini.read_bytes() if ini.is_file() else b""
        try:
            if target.exists():
                shutil.rmtree(target)
            if original_ini:
                _atomic_write(ini, _edit_folder_names(original_ini, add=False))
        except Exception:
            if original_ini and ini.exists():
                _atomic_write(ini, original_ini)
            raise
    return status(game, project, runtime)
