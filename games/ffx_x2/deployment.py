"""Reversible deployment of Lexeditor FFX/X-2 file overlays into Fahrenheit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


MOD_ID = "lexeditor-ffx-x2"
MANIFEST_NAME = f"{MOD_ID}.manifest.json"
MARKER_NAME = ".lexeditor-deployment.json"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _project_files(project_root: Path) -> list[tuple[Path, Path]]:
    rows: list[tuple[Path, Path]] = []
    project_root = Path(project_root).resolve()
    for game in ("x", "x2"):
        root = project_root / "efl" / game
        if not root.is_dir():
            continue
        for source in sorted(root.rglob("*")):
            if source.is_symlink():
                raise ValueError(f"Project overlays may not contain symlinks: {source}")
            if not source.is_file():
                continue
            relative = source.relative_to(project_root)
            rows.append((source, relative))
    return rows


def _manifest() -> dict:
    return {
        "Id": MOD_ID,
        "Name": "Lexeditor FFX/X-2 Project",
        "Desc": "File replacements staged by the Lexeditor FFX/X-2 collection plugin.",
        "Authors": "Lexeditor contributors",
        "Version": "0.1.0",
        "Link": "https://github.com/Lexer-Lux/Lexeditor",
        "Dependencies": [],
        "LoadAfter": [],
        "Flags": "NONE",
    }


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".lexeditor.tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def _loadorder_path(game_root: Path) -> Path:
    return Path(game_root) / "fahrenheit" / "mods" / "loadorder"


def _mod_root(game_root: Path) -> Path:
    return Path(game_root) / "fahrenheit" / "mods" / MOD_ID


def _fahrenheit_ready(game_root: Path) -> bool:
    root = Path(game_root) / "fahrenheit"
    return (root / "bin" / "fhstage0.exe").is_file() and (root / "mods").is_dir()


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Deployed mod contains a symlink: {path}")
        if path.is_file() and path.name != MARKER_NAME:
            result[path.relative_to(root).as_posix()] = _hash_file(path)
    return result


def _read_marker(root: Path) -> dict | None:
    marker = root / MARKER_NAME
    if not marker.is_file():
        return None
    try:
        value = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read Lexeditor deployment marker: {error}") from error
    if not isinstance(value, dict) or value.get("modId") != MOD_ID or not isinstance(value.get("files"), dict):
        raise RuntimeError("The deployed FFX/X-2 mod has an invalid Lexeditor ownership marker")
    return value


def _assert_owned_unchanged(root: Path) -> dict:
    marker = _read_marker(root)
    if marker is None:
        raise RuntimeError(
            f"Refusing to replace an existing Fahrenheit mod not owned by Lexeditor: {root}"
        )
    current = _snapshot(root)
    if current != marker["files"]:
        raise RuntimeError(
            "The deployed Lexeditor Fahrenheit mod was changed externally; revert or reconcile it manually first"
        )
    return marker


def _loadorder_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8-sig", errors="replace").splitlines()


def _enable_loadorder(path: Path) -> None:
    lines = _loadorder_lines(path)
    if MOD_ID.casefold() not in {line.strip().casefold() for line in lines if line.strip()}:
        lines.append(MOD_ID)
    _atomic_text(path, "\n".join(lines) + "\n")


def _disable_loadorder(path: Path) -> None:
    if not path.exists():
        return
    lines = [line for line in _loadorder_lines(path) if line.strip().casefold() != MOD_ID.casefold()]
    _atomic_text(path, ("\n".join(lines) + "\n") if lines else "")


def status(game_root: Path, project_root: Path) -> dict:
    game_root, project_root = Path(game_root), Path(project_root)
    mod_root = _mod_root(game_root)
    marker = None
    changed = False
    if mod_root.is_dir():
        try:
            marker = _read_marker(mod_root)
            changed = marker is None or _snapshot(mod_root) != marker.get("files", {})
        except RuntimeError:
            changed = True
    project_files = _project_files(project_root)
    loadorder = _loadorder_lines(_loadorder_path(game_root))
    return {
        "fahrenheitReady": _fahrenheit_ready(game_root),
        "fahrenheitRoot": str(game_root / "fahrenheit"),
        "projectFileCount": len(project_files),
        "deployed": mod_root.is_dir() and marker is not None,
        "deployedChangedExternally": changed,
        "enabled": MOD_ID.casefold() in {line.strip().casefold() for line in loadorder if line.strip()},
        "modRoot": str(mod_root),
        "launch": str(game_root / "fahrenheit" / "bin" / "fhstage0.exe"),
    }


def deploy(game_root: Path, project_root: Path) -> dict:
    """Install one Lexeditor-owned file-only Fahrenheit mod and enable it."""
    game_root, project_root = Path(game_root), Path(project_root)
    if not _fahrenheit_ready(game_root):
        raise FileNotFoundError(
            f"Fahrenheit is not installed at {game_root / 'fahrenheit'}; install it before deploying"
        )
    files = _project_files(project_root)
    if not files:
        raise RuntimeError("The project has no FFX/X-2 replacement files to deploy")

    mods_root = game_root / "fahrenheit" / "mods"
    mod_root = _mod_root(game_root)
    if mod_root.exists():
        if not mod_root.is_dir():
            raise RuntimeError(f"Fahrenheit mod path is not a directory: {mod_root}")
        _assert_owned_unchanged(mod_root)

    staging: Path | None = Path(tempfile.mkdtemp(prefix=f".{MOD_ID}-", dir=mods_root))
    try:
        for source, relative in files:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        (staging / MANIFEST_NAME).write_text(
            json.dumps(_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        snapshot = _snapshot(staging)
        (staging / MARKER_NAME).write_text(json.dumps({
            "schema": 1,
            "modId": MOD_ID,
            "projectRoot": str(project_root.resolve()),
            "files": snapshot,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        backup = mods_root / f".{MOD_ID}.previous"
        if backup.exists():
            shutil.rmtree(backup)
        if mod_root.exists():
            os.replace(mod_root, backup)
        try:
            os.replace(staging, mod_root)
            staging = None
            _enable_loadorder(_loadorder_path(game_root))
        except Exception:
            if mod_root.exists():
                shutil.rmtree(mod_root)
            if backup.exists():
                os.replace(backup, mod_root)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return status(game_root, project_root)


def revert(game_root: Path, project_root: Path) -> dict:
    """Remove only the unchanged Lexeditor-owned deployment and loadorder entry."""
    game_root, project_root = Path(game_root), Path(project_root)
    mod_root = _mod_root(game_root)
    if mod_root.exists():
        if not mod_root.is_dir():
            raise RuntimeError(f"Fahrenheit mod path is not a directory: {mod_root}")
        _assert_owned_unchanged(mod_root)
        shutil.rmtree(mod_root)
    _disable_loadorder(_loadorder_path(game_root))
    return status(game_root, project_root)
