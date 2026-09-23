"""Whole-file optimistic-concurrency tokens for structured Bannerlord editors."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import shutil

from . import paths


_UTF8_BOM = b"\xef\xbb\xbf"


def revision_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def source_revision(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        return ""
    return revision_bytes(path.read_bytes())


def read_utf8_source(path: Path) -> tuple[str, str, str]:
    """Read UTF-8 text without newline translation and retain BOM/revision state."""
    raw = Path(path).read_bytes()
    token = revision_bytes(raw)
    if raw.startswith(_UTF8_BOM):
        return raw.decode("utf-8-sig"), "utf-8-sig", token
    return raw.decode("utf-8"), "utf-8", token


def encode_utf8_source(text: str, encoding: str) -> bytes:
    if encoding not in {"utf-8", "utf-8-sig"}:
        raise ValueError(f"Unsupported Bannerlord source encoding: {encoding}")
    return str(text).encode(encoding)


def attach_source_revision(payload: dict, path: Path | None = None) -> dict:
    result = dict(payload)
    source = Path(path) if path is not None else Path(str(result.get("path") or ""))
    result["sourceHash"] = source_revision(source)
    return result


def require_source_revision(path: Path, expected) -> None:
    path = Path(path)
    token = str(expected or "").strip()
    if not token:
        raise ValueError("Structured save requires the loaded source revision; reload before saving")
    if not path.is_file():
        raise FileNotFoundError(path)
    if source_revision(path) != token:
        raise ValueError("Structured source changed on disk; reload before saving")



def replace_source_bytes(path: Path, data: bytes, expected) -> str:
    """Stage exact bytes, recheck the loaded revision, back up, and replace atomically."""
    path = Path(path)
    token = str(expected or "").strip()
    if not token:
        raise ValueError("Structured save requires the loaded source revision; reload before saving")
    if not path.is_file():
        raise FileNotFoundError(path)
    temporary = path.with_name(path.name + ".lexeditor.tmp")
    backup = path.with_name(path.name + ".lexeditor.bak")
    paths.clear_write_helper(temporary)
    try:
        temporary.write_bytes(bytes(data))
        require_source_revision(path, token)
        paths.clear_write_helper(backup)
        shutil.copy2(path, backup)
        # Backup creation can take non-trivial time on a slow disk. Recheck once
        # more before the target replacement so a racing external edit wins.
        require_source_revision(path, token)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return str(backup)

MISSING_SOURCE_REVISION = "missing"

def optional_source_revision(path: Path) -> str:
    path = Path(path)
    if not path.exists():
        return MISSING_SOURCE_REVISION
    if not path.is_file():
        raise ValueError(f"Runtime source path is not a file: {path}")
    return source_revision(path)


def require_optional_source_revision(path: Path, expected) -> None:
    token = str(expected or "").strip()
    if not token:
        raise ValueError("Runtime save requires the loaded source revision; reload before saving")
    if optional_source_revision(path) != token:
        raise ValueError("Runtime source changed on disk; reload before saving")
