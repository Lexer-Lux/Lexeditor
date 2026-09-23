"""Safe project asset inventory/import for Terraria/tModLoader source mods."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile


MAX_ASSET_FILE = 16 * 1024 * 1024
IGNORED_PARTS = frozenset({".git", ".pytest_cache", "__pycache__", "out", "obj", "bin", ".vs"})
ASSET_TYPES = {
    ".png": ("image", "image/png"),
    ".xnb": ("compiled", "application/octet-stream"),
    ".rawimg": ("image-compiled", "application/octet-stream"),
    ".fxc": ("effect", "application/octet-stream"),
    ".wav": ("audio", "audio/wav"),
    ".mp3": ("audio", "audio/mpeg"),
    ".ogg": ("audio", "audio/ogg"),
}


def asset_target(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Asset path is required")
    project = Path(root).resolve()
    target = (project / relative).resolve()
    if target == project or project not in target.parents or target.suffix.casefold() not in ASSET_TYPES:
        raise ValueError("Invalid tModLoader asset path")
    parts = target.relative_to(project).parts
    if IGNORED_PARTS.intersection(parts) or any(part.startswith(".") for part in parts):
        raise ValueError("Asset path is inside an ignored/generated folder")
    return target


def _asset_metadata(project: Path, target: Path, data: bytes) -> dict:
    relative = target.relative_to(project).as_posix()
    suffix = target.suffix.casefold()
    kind, mime = ASSET_TYPES[suffix]
    preview = "image" if suffix == ".png" else "audio" if suffix in {".wav", ".mp3", ".ogg"} else "none"
    payload = {
        "path": relative,
        "sha256": sha256(data).hexdigest(),
        "bytes": len(data),
        "extension": suffix,
        "kind": kind,
        "mime": mime,
        "preview": preview,
    }
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        payload["width"] = int.from_bytes(data[16:20], "big")
        payload["height"] = int.from_bytes(data[20:24], "big")
    else:
        payload["width"] = None
        payload["height"] = None
    return payload


def read_asset(root: Path, relative: str) -> tuple[Path, bytes, dict]:
    project = Path(root).resolve()
    target = asset_target(project, relative)
    if not target.is_file():
        raise ValueError("Asset file does not exist")
    data = target.read_bytes()
    if len(data) > MAX_ASSET_FILE:
        raise ValueError("Asset file is too large for Lexeditor asset management")
    return target, data, _asset_metadata(project, target, data)


def asset_state(root: Path, relative: str) -> dict:
    _target, _data, metadata = read_asset(root, relative)
    return metadata


def asset_index(root: Path) -> dict:
    project = Path(root).resolve()
    files: list[dict] = []
    if not project.is_dir():
        return {"root": str(project), "files": files}
    candidates = sorted(
        (
            path for path in project.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in ASSET_TYPES
            and not IGNORED_PARTS.intersection(path.relative_to(project).parts)
            and not any(part.startswith(".") for part in path.relative_to(project).parts)
        ),
        key=lambda path: path.relative_to(project).as_posix().casefold(),
    )
    for target in candidates:
        relative = target.relative_to(project).as_posix()
        try:
            size = target.stat().st_size
            if size > MAX_ASSET_FILE:
                kind, mime = ASSET_TYPES[target.suffix.casefold()]
                files.append({
                    "path": relative,
                    "bytes": size,
                    "extension": target.suffix.casefold(),
                    "kind": kind,
                    "mime": mime,
                    "preview": "none",
                    "editable": False,
                    "error": "Asset file is too large for Lexeditor asset management",
                })
                continue
            state = asset_state(project, relative)
            state["editable"] = True
            state["error"] = ""
            files.append(state)
        except (OSError, ValueError) as error:
            files.append({
                "path": relative,
                "bytes": 0,
                "extension": target.suffix.casefold(),
                "kind": "unknown",
                "mime": "application/octet-stream",
                "preview": "none",
                "editable": False,
                "error": str(error),
            })
    return {"root": str(project), "files": files}


def _validate_asset_data(relative: str, data: object) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("Asset content must be bytes")
    encoded = bytes(data)
    if len(encoded) > MAX_ASSET_FILE:
        raise ValueError("Asset file is too large for Lexeditor asset management")
    suffix = Path(relative).suffix.casefold()
    if suffix == ".png" and not encoded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG asset does not contain a PNG signature")
    if suffix == ".wav" and not (len(encoded) >= 12 and encoded[:4] == b"RIFF" and encoded[8:12] == b"WAVE"):
        raise ValueError("WAV asset does not contain a RIFF/WAVE header")
    if suffix == ".ogg" and not encoded.startswith(b"OggS"):
        raise ValueError("OGG asset does not contain an Ogg stream header")
    return encoded


def _atomic_replace(target: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".lexeditor-asset-", delete=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def create_asset(root: Path, relative: str, data: object) -> dict:
    project = Path(root).resolve()
    if not project.is_dir():
        raise ValueError("Terraria source project does not exist")
    target = asset_target(project, relative)
    encoded = _validate_asset_data(relative, data)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ValueError(f"Asset file already exists: {target.relative_to(project).as_posix()}") from error
    return asset_state(project, target.relative_to(project).as_posix())


def replace_asset(root: Path, relative: str, data: object, expected_sha256: str) -> dict:
    project = Path(root).resolve()
    target, current, state = read_asset(project, relative)
    if expected_sha256 != state["sha256"]:
        raise ValueError(f"{state['path']} changed outside Lexeditor; reload before replacing")
    encoded = _validate_asset_data(relative, data)
    if encoded == current:
        return state
    _atomic_replace(target, encoded)
    return asset_state(project, state["path"])


def rename_asset(root: Path, relative: str, new_relative: str, expected_sha256: str) -> dict:
    """Move an asset without overwrite while preserving the asset's format."""
    project = Path(root).resolve()
    source, data, state = read_asset(project, relative)
    if expected_sha256 != state["sha256"]:
        raise ValueError(f"{state['path']} changed outside Lexeditor; reload before renaming")
    destination = asset_target(project, new_relative)
    destination_relative = destination.relative_to(project).as_posix()
    if destination.suffix.casefold() != source.suffix.casefold():
        raise ValueError("Asset rename must preserve the file extension")
    if destination == source:
        return state
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise ValueError(f"Asset file already exists: {destination_relative}") from error
    try:
        source.unlink()
    except OSError:
        destination.unlink(missing_ok=True)
        raise
    return asset_state(project, destination_relative)


def delete_asset(root: Path, relative: str, expected_sha256: str) -> dict:
    """Delete one asset only when its current bytes match the observed SHA."""
    target, _data, state = read_asset(root, relative)
    if expected_sha256 != state["sha256"]:
        raise ValueError(f"{state['path']} changed outside Lexeditor; reload before deleting")
    target.unlink()
    return {"path": state["path"], "deleted": True}
