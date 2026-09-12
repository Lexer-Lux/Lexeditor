"""Project-bounded raw C# source editing for Terraria/tModLoader projects."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import tempfile


UTF8_BOM = b"\xef\xbb\xbf"
MAX_SOURCE_FILE = 2 * 1024 * 1024
IGNORED_PARTS = frozenset({".git", ".pytest_cache", "__pycache__", "out", "obj", "bin", ".vs"})


def source_target(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("Source path is required")
    project = Path(root).resolve()
    target = (project / relative).resolve()
    if (
        target == project
        or project not in target.parents
        or target.suffix.casefold() != ".cs"
    ):
        raise ValueError("Invalid C# source path")
    return target


def _read_source(root: Path, relative: str) -> tuple[Path, bytes, str, str]:
    project = Path(root).resolve()
    target = source_target(project, relative)
    if not target.is_file():
        raise ValueError("C# source file does not exist")
    data = target.read_bytes()
    if len(data) > MAX_SOURCE_FILE:
        raise ValueError("C# source file is too large for text editing")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("C# source file is not UTF-8 text") from error
    if "\x00" in text:
        raise ValueError("C# source file contains NUL bytes")
    return target, data, text, target.relative_to(project).as_posix()


def source_index(root: Path) -> dict:
    project = Path(root).resolve()
    files: list[dict] = []
    if not project.is_dir():
        return {"root": str(project), "files": files}
    candidates = sorted(
        (
            path for path in project.rglob("*.cs")
            if path.is_file() and not IGNORED_PARTS.intersection(path.relative_to(project).parts)
        ),
        key=lambda path: path.relative_to(project).as_posix().casefold(),
    )
    for path in candidates:
        relative = path.relative_to(project).as_posix()
        try:
            _target, data, text, canonical = _read_source(project, relative)
            files.append({
                "path": canonical,
                "bytes": len(data),
                "lines": len(text.splitlines()),
                "editable": True,
                "error": "",
            })
        except (OSError, ValueError) as error:
            files.append({
                "path": relative,
                "bytes": 0,
                "lines": 0,
                "editable": False,
                "error": str(error),
            })
    return {"root": str(project), "files": files}


def source_file_state(root: Path, relative: str) -> dict:
    _target, data, text, canonical = _read_source(root, relative)
    return {
        "path": canonical,
        "sha256": sha256(data).hexdigest(),
        "text": text,
        "bytes": len(data),
        "lines": len(text.splitlines()),
        "editable": True,
    }


def _match_original_newlines(original: str, replacement: str) -> str:
    normalized = replacement.replace("\r\n", "\n").replace("\r", "\n")
    if "\r\n" in original and original.count("\n") == original.count("\r\n"):
        return normalized.replace("\n", "\r\n")
    return normalized


def _atomic_replace(target: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".lexeditor-source-", delete=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def save_source(root: Path, relative: str, text: object, expected_sha256: str) -> dict:
    target, data, original, canonical = _read_source(root, relative)
    current_sha = sha256(data).hexdigest()
    if expected_sha256 != current_sha:
        raise ValueError(f"{canonical} changed outside Lexeditor; reload before saving")
    if not isinstance(text, str):
        raise ValueError("C# source content must be text")
    if "\x00" in text:
        raise ValueError("C# source content contains NUL bytes")

    changed = _match_original_newlines(original, text)
    if changed == original:
        return source_file_state(root, canonical)
    encoded = (UTF8_BOM if data.startswith(UTF8_BOM) else b"") + changed.encode("utf-8")
    if len(encoded) > MAX_SOURCE_FILE:
        raise ValueError("C# source file is too large for text editing")
    _atomic_replace(target, encoded)
    return source_file_state(root, canonical)
