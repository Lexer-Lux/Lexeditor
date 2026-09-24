"""Pinned FFNx acquisition and guarded first-time setup for classic FF7.

Lexeditor never vendors the FFNx binary in this repository. The helper downloads
one published upstream release, verifies the release asset digest, and installs
it only into the 2026 FF7 working directory. Existing/manual/7th-Heaven FFNx
installations are treated as externally owned and are never replaced.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

from core.runtime_bootstrap import user_data_dir


FFNX_VERSION = "1.24.3"
FFNX_TAG = FFNX_VERSION
FFNX_RELEASE = f"FFNx-v{FFNX_VERSION}.0"
FFNX_ARCHIVE = f"FFNx-Steam-v{FFNX_VERSION}.0.zip"
FFNX_URL = f"https://github.com/julianxhokaxhiu/FFNx/releases/download/{FFNX_TAG}/{FFNX_ARCHIVE}"
FFNX_SHA256 = "2be45f486974f0979b849d0525eb66427df62483ec99e9339e9773e9e52afc0d"
SETUP_MANIFEST = ".lexeditor-ffnx-setup.json"
STEAM_APP_ID = "3837340"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_path() -> Path:
    return user_data_dir() / "tools" / "ffnx" / FFNX_TAG / FFNX_ARCHIVE


def working_dir(game_root: Path) -> Path:
    return Path(game_root).resolve() / "ff7" / "workingdir"


def _manifest_path(game_root: Path) -> Path:
    return working_dir(game_root) / SETUP_MANIFEST


def helper_status(game_root: Path) -> dict:
    root = working_dir(game_root)
    archive = archive_path()
    config = root / "FFNx.toml"
    manifest = _manifest_path(game_root)
    owned = manifest.is_file()
    return {
        "runtime": "FFNx",
        "pinned": FFNX_RELEASE,
        "version": FFNX_VERSION,
        "archive": FFNX_ARCHIVE,
        "archiveSha256": FFNX_SHA256,
        "cached": archive.is_file() and _digest(archive.read_bytes()) == FFNX_SHA256,
        "cachePath": str(archive),
        "installed": config.is_file(),
        "owned": owned,
        "workingDir": str(root),
        "manifest": str(manifest),
        "message": (
            "FFNx is already present and is Lexeditor-owned."
            if config.is_file() and owned else
            "FFNx is already present and is externally managed; Lexeditor will not replace it."
            if config.is_file() else
            f"Install pinned {FFNX_RELEASE} into ff7/workingdir."
        ),
    }


def acquire_archive(opener=urllib.request.urlopen) -> Path:
    """Download the pinned upstream archive into Lexeditor's user-data cache."""
    target = archive_path()
    if target.is_file():
        digest = _digest(target.read_bytes())
        if digest == FFNX_SHA256:
            return target
        raise RuntimeError(
            f"Cached FFNx archive SHA-256 mismatch: expected {FFNX_SHA256}, got {digest}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with opener(FFNX_URL, timeout=60) as response:
                shutil.copyfileobj(response, stream)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    digest = _digest(temporary.read_bytes())
    if digest != FFNX_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"FFNx download SHA-256 mismatch: expected {FFNX_SHA256}, got {digest}")
    os.replace(temporary, target)
    return target


def _archive_files(archive: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            pure = PurePosixPath(name)
            if (not name or pure.is_absolute() or ".." in pure.parts
                    or len(pure.parts) == 0 or ":" in pure.parts[0]):
                raise ValueError(f"Unsafe FFNx archive path: {name}")
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError(f"FFNx archive contains a symbolic link: {name}")
            if name.casefold() == SETUP_MANIFEST.casefold():
                raise ValueError(f"FFNx archive attempts to own Lexeditor manifest path: {name}")
            folded = name.casefold()
            if folded in seen:
                raise ValueError(f"FFNx archive contains a duplicate path: {name}")
            seen.add(folded)
            result[name] = package.read(info)
    if not any(name.casefold() == "ffnx.toml" for name in result):
        raise ValueError("Pinned FFNx archive does not contain FFNx.toml")
    return result


def _load_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise ValueError(f"Invalid Lexeditor FFNx setup manifest: {path}") from error
    if data.get("schema") != 1 or data.get("runtime") != "FFNx" or not isinstance(data.get("files"), list):
        raise ValueError(f"Unsupported Lexeditor FFNx setup manifest: {path}")
    return data


def _required_local_files(game_root: Path) -> dict[str, bytes]:
    game = Path(game_root).resolve()
    root = working_dir(game)
    executable = game / "ff7" / "resources" / "ff7_1.02" / "ff7_en"
    window = root / "data" / "lang-ja" / "kernel" / "window.bin"
    missing = [str(path) for path in (executable, window) if not path.is_file()]
    if missing:
        raise FileNotFoundError("FFNx 2026 setup requires installed source file(s): " + ", ".join(missing))
    return {
        "ff7_en.exe": executable.read_bytes(),
        "data/kernel/windows.bin": window.read_bytes(),
        "steam_appid.txt": (STEAM_APP_ID + "\n").encode("ascii"),
    }


def install_pinned(game_root: Path, archive: Path | None = None) -> dict:
    """Install/update only Lexeditor-owned FFNx files for the 2026 Steam layout.

    A pre-existing FFNx.toml without Lexeditor's manifest is external ownership
    (manual install or a launcher such as 7th Heaven) and is never overwritten.
    Updates likewise refuse any owned file whose bytes changed outside Lexeditor.
    """
    game = Path(game_root).resolve()
    root = working_dir(game)
    if not root.is_dir():
        raise FileNotFoundError(f"FF7 working directory is unavailable: {root}")
    manifest_path = _manifest_path(game)
    previous = _load_manifest(manifest_path)
    if (root / "FFNx.toml").is_file() and not previous:
        raise ValueError("FFNx is already installed but is not Lexeditor-owned; refusing to replace it")

    source_archive = Path(archive).resolve() if archive is not None else acquire_archive()
    digest = _digest(source_archive.read_bytes())
    if digest != FFNX_SHA256:
        raise RuntimeError(f"FFNx archive SHA-256 mismatch: expected {FFNX_SHA256}, got {digest}")
    payload = _archive_files(source_archive)
    payload.update(_required_local_files(game))

    previous_files = {
        row["path"]: row for row in previous.get("files", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    root_resolved = root.resolve()
    for relative, raw in payload.items():
        target = (root / relative).resolve()
        if not target.is_relative_to(root_resolved):
            raise ValueError(f"Unsafe FFNx setup path: {relative}")
        if target.is_file():
            prior = previous_files.get(relative)
            if prior is None:
                raise ValueError(f"FFNx setup path is already externally owned: {target}")
            if _digest(target.read_bytes()) != prior.get("sha256"):
                raise ValueError(f"Lexeditor-owned FFNx file changed outside Lexeditor: {target}")

    for relative, row in previous_files.items():
        if relative in payload:
            continue
        target = (root / relative).resolve()
        if not target.is_relative_to(root_resolved):
            raise ValueError(f"Unsafe prior FFNx setup path: {relative}")
        if target.is_file() and _digest(target.read_bytes()) != row.get("sha256"):
            raise ValueError(f"Lexeditor-owned FFNx file changed outside Lexeditor: {target}")

    backup: dict[Path, bytes | None] = {}
    try:
        for relative in set(previous_files) | set(payload):
            target = (root / relative).resolve()
            backup[target] = target.read_bytes() if target.is_file() else None
        for relative in set(previous_files) - set(payload):
            (root / relative).unlink(missing_ok=True)
        for relative, raw in payload.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
            os.replace(temporary, target)
        manifest = {
            "schema": 1,
            "runtime": "FFNx",
            "version": FFNX_VERSION,
            "release": FFNX_RELEASE,
            "archive": FFNX_ARCHIVE,
            "archiveSha256": FFNX_SHA256,
            "files": [
                {"path": relative, "bytes": len(raw), "sha256": _digest(raw)}
                for relative, raw in sorted(payload.items())
            ],
        }
        temporary_manifest = manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary_manifest, manifest_path)
    except Exception:
        for target, raw in backup.items():
            if raw is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        raise

    return {**helper_status(game), "setup": True, "fileCount": len(payload)}
