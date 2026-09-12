"""Whole-file optimistic-concurrency tokens for structured Bannerlord editors."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path


def source_revision(path: Path) -> str:
    path = Path(path)
    if not path.is_file():
        return ""
    return sha256(path.read_bytes()).hexdigest()


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
