"""ReShade presets that travel with a Lexeditor mod.

Three requirements pull against each other, so the shape is deliberate:

  * one ReShade managed by Lexeditor rather than a copy inside every mod,
  * each mod carrying its own preset and any shaders its author actually wrote,
  * and a published mod still working for someone who has never used Lexeditor.

The last one decides the format. A mod ships a plain ReShade preset plus a
manifest naming the shader repositories it needs. Anyone with ReShade already
installed can drop the preset in and install those repositories by hand. Nothing
here invents a container that only Lexeditor can open.

Shader repositories are named, never copied: several common ones forbid
redistribution, so a mod that bundled them would not be safe to publish.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

MANIFEST_NAME = "reshade.json"
RESHADE_DIR = "reshade"
PRESET_SUFFIXES = (".ini",)
SHADER_SUFFIXES = (".fx", ".fxh")
# The loader DLL name depends on the renderer the game uses.
RENDERER_DLLS = {
    "dx9": "d3d9.dll", "dx10": "d3d10.dll", "dx11": "d3d11.dll",
    "dx12": "d3d12.dll", "dxgi": "dxgi.dll", "opengl": "opengl32.dll",
    "vulkan": "vulkan-1.dll",
}


def _reshade_root(project_root: Path) -> Path:
    return Path(project_root) / RESHADE_DIR


def manifest_path(project_root: Path) -> Path:
    return _reshade_root(project_root) / MANIFEST_NAME


def read_manifest(project_root: Path) -> dict:
    """Return the mod's ReShade manifest, defaulted when it has none yet."""
    path = manifest_path(project_root)
    payload: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, ValueError):
            payload = {}
    return {
        "enabled": bool(payload.get("enabled", False)),
        "preset": str(payload.get("preset", "") or ""),
        "renderer": str(payload.get("renderer", "") or ""),
        "repositories": [
            {"name": str(entry.get("name", "")), "version": str(entry.get("version", ""))}
            for entry in payload.get("repositories", [])
            if isinstance(entry, dict) and entry.get("name")
        ],
    }


def write_manifest(project_root: Path, manifest: dict) -> dict:
    """Persist the manifest, creating the mod's reshade folder if needed."""
    root = _reshade_root(project_root)
    root.mkdir(parents=True, exist_ok=True)
    clean = {
        "enabled": bool(manifest.get("enabled", False)),
        "preset": str(manifest.get("preset", "") or ""),
        "renderer": str(manifest.get("renderer", "") or ""),
        "repositories": [
            {"name": str(entry.get("name", "")), "version": str(entry.get("version", ""))}
            for entry in manifest.get("repositories", [])
            if isinstance(entry, dict) and entry.get("name")
        ],
    }
    manifest_path(project_root).write_text(
        json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    return clean


def _listing(root: Path, suffixes: tuple[str, ...]) -> list[str]:
    if not root.is_dir():
        return []
    found = []
    for folder, folders, files in os.walk(root):
        folders[:] = [name for name in folders if not name.startswith(".")]
        for name in sorted(files):
            if Path(name).suffix.lower() in suffixes:
                found.append(str(Path(folder, name).relative_to(root)).replace("\\", "/"))
    return sorted(found)


def installed_renderer(game_root: Path | None) -> str:
    """Name the ReShade loader already present in the game folder, if any."""
    if not game_root:
        return ""
    root = Path(game_root)
    for renderer, dll in RENDERER_DLLS.items():
        candidate = root / dll
        if not candidate.is_file():
            continue
        try:
            head = candidate.read_bytes()[:2_000_000]
        except OSError:
            continue
        # ReShade's own DLL carries its name; a game's real d3d11.dll does not.
        if b"ReShade" in head:
            return renderer
    return ""


# Lexeditor keeps ONE ReShade and installs it per game. The user supplies that
# copy once - ReShade is not vendored here, because which build to ship is their
# decision and not one a mod editor should make quietly on their behalf.
STORE = Path(os.environ.get("LOCALAPPDATA", "")) / "Lexeditor" / "reshade"
STORE_DLL = "ReShade64.dll"


def store_dll() -> Path:
    return STORE / STORE_DLL


def store_state() -> dict:
    dll = store_dll()
    return {"path": str(dll), "present": dll.is_file(),
            "bytes": dll.stat().st_size if dll.is_file() else 0}


NEWLINE = chr(10)
REPOSITORIES_NAME = "repositories.json"


def repositories_path() -> Path:
    return STORE / REPOSITORIES_NAME


def _clean_repository(entry: dict) -> dict | None:
    name = str(entry.get("name", "") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "version": str(entry.get("version", "") or "").strip(),
        "url": str(entry.get("url", "") or "").strip(),
    }


def repositories() -> list[dict]:
    """The shader repositories this machine has, shared by every project.

    One list per machine, not per mod. A mod's manifest names a repository and
    a version; it never carries the shaders, because several of the common
    repositories forbid redistribution.
    """
    path = repositories_path()
    if not path.is_file():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    found = [_clean_repository(entry) for entry in loaded if isinstance(entry, dict)]
    return sorted((entry for entry in found if entry), key=lambda entry: entry["name"].lower())


def write_repositories(entries: list[dict]) -> list[dict]:
    """Replace the machine's repository list. Last name written wins."""
    by_name: dict[str, dict] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        clean = _clean_repository(entry)
        if clean:
            by_name[clean["name"].lower()] = clean
    ordered = sorted(by_name.values(), key=lambda entry: entry["name"].lower())
    STORE.mkdir(parents=True, exist_ok=True)
    repositories_path().write_text(
        json.dumps(ordered, indent=2) + NEWLINE, encoding="utf-8")
    return ordered


def add_repository(name: str, version: str = "", url: str = "") -> list[dict]:
    """Add or update one repository by name."""
    if not str(name or "").strip():
        raise ValueError("A repository needs a name.")
    return write_repositories(
        [*repositories(), {"name": name, "version": version, "url": url}])


def remove_repository(name: str) -> list[dict]:
    """Forget one repository. The mods that name it still name it."""
    wanted = str(name or "").strip().lower()
    return write_repositories(
        [entry for entry in repositories() if entry["name"].lower() != wanted])


def repository_status(manifest: dict) -> list[dict]:
    """Say, per repository the mod needs, whether this machine has it.

    A version the mod names and the machine does not match is reported as a
    mismatch rather than as missing, because the shaders are there but may not
    be the ones the preset was authored against.
    """
    have = {entry["name"].lower(): entry for entry in repositories()}
    status = []
    for needed in manifest.get("repositories", []):
        name = str(needed.get("name", "") or "")
        wanted = str(needed.get("version", "") or "")
        mine = have.get(name.lower())
        if mine is None:
            state = "missing"
        elif wanted and mine["version"] and wanted != mine["version"]:
            state = "version-mismatch"
        else:
            state = "present"
        status.append({"name": name, "version": wanted,
                       "installedVersion": mine["version"] if mine else "",
                       "url": mine["url"] if mine else "",
                       "state": state})
    return status


EXPORT_NOTE_NAME = "INSTALL-RESHADE.txt"


def export_note(project_root: Path, game_root: Path | None = None) -> str:
    """The text a person installing this mod by hand needs, and nothing else.

    It names the preset file, the loader DLL the game wants, and every shader
    repository with the version the preset was authored against. It does not
    describe Lexeditor, because the reader may never have used it.
    """
    state = snapshot(project_root, game_root)
    manifest = state["manifest"]
    preset = manifest["preset"] or "(no preset chosen)"
    renderer = manifest["renderer"] or state["installedRenderer"] or ""
    loader = RENDERER_DLLS.get(renderer, "") if renderer else ""
    lines = [
        "Installing this mod's ReShade preset by hand",
        "=" * 44,
        "",
        "You do not need Lexeditor for any of this.",
        "",
        "1. Install ReShade from https://reshade.me into the game folder.",
    ]
    lines.append(
        f"   This game loads it as {loader}." if loader
        else "   Pick the loader for the game's renderer when ReShade asks.")
    lines += [
        "",
        "2. Install these shader repositories in ReShade's setup. They are not",
        "   included here, because their licences do not all allow it.",
    ]
    needed = manifest["repositories"]
    if needed:
        for entry in needed:
            version = f" (version {entry['version']})" if entry.get("version") else ""
            lines.append(f"   - {entry['name']}{version}")
    else:
        lines.append("   - none; this preset uses only the shaders below.")
    lines += ["", f"3. Copy {preset} into the game's reshade-presets folder and",
              "   select it in ReShade's overlay."]
    if state["shaders"]:
        lines += ["",
                  "4. Copy these shaders, which are this mod's own work, into",
                  "   ReShade's shaders folder:"]
        lines += [f"   - {name}" for name in state["shaders"]]
    lines.append("")
    return NEWLINE.join(lines)


def write_export_note(project_root: Path, game_root: Path | None = None) -> str:
    """Put the note beside the preset, where anyone unpacking the mod finds it."""
    root = _reshade_root(Path(project_root))
    root.mkdir(parents=True, exist_ok=True)
    path = root / EXPORT_NOTE_NAME
    path.write_text(export_note(project_root, game_root), encoding="utf-8")
    return str(path)


def adopt(source: Path) -> dict:
    """Take the user's ReShade DLL as Lexeditor's one copy."""
    source = Path(source)
    if not source.is_file():
        raise ValueError(f"No file at {source}")
    try:
        head = source.read_bytes()[:2_000_000]
    except OSError as error:
        raise ValueError(f"Could not read {source}: {error}") from error
    if b"ReShade" not in head:
        raise ValueError(f"{source.name} does not look like a ReShade DLL")
    STORE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, store_dll())
    return store_state()


def install(game_root: Path, renderer: str) -> dict:
    """Place Lexeditor's ReShade in one game, under the loader name it needs."""
    game_root = Path(game_root)
    dll_name = RENDERER_DLLS.get(str(renderer).lower())
    if not dll_name:
        raise ValueError(f"Unknown renderer: {renderer}")
    if not game_root.is_dir():
        raise ValueError(f"No game folder at {game_root}")
    source = store_dll()
    if not source.is_file():
        raise ValueError("Lexeditor has no ReShade to install yet")
    target = game_root / dll_name
    # A game's own d3d11.dll is not ours to replace. Only an existing ReShade
    # may be overwritten, and only by another ReShade.
    if target.is_file():
        try:
            existing = target.read_bytes()[:2_000_000]
        except OSError as error:
            raise ValueError(f"Could not read {target}: {error}") from error
        if b"ReShade" not in existing:
            raise ValueError(
                f"{dll_name} already exists in this game and is not ReShade. "
                "Lexeditor will not overwrite it.")
    shutil.copy2(source, target)
    return {"installed": True, "renderer": str(renderer).lower(), "path": str(target)}


def uninstall(game_root: Path) -> dict:
    """Remove ReShade from one game. Only a DLL that IS ReShade is deleted."""
    game_root = Path(game_root)
    removed = []
    for renderer, dll_name in RENDERER_DLLS.items():
        target = game_root / dll_name
        if not target.is_file():
            continue
        try:
            if b"ReShade" not in target.read_bytes()[:2_000_000]:
                continue
            target.unlink()
        except OSError:
            continue
        removed.append({"renderer": renderer, "path": str(target)})
    return {"removed": removed}


def snapshot(project_root: Path, game_root: Path | None = None) -> dict:
    """Everything the Tweaks page needs to describe this mod's ReShade state."""
    root = _reshade_root(project_root)
    manifest = read_manifest(project_root)
    presets = _listing(root, PRESET_SUFFIXES)
    presets = [name for name in presets if Path(name).name != MANIFEST_NAME]
    shaders = _listing(root / "shaders", SHADER_SUFFIXES)
    renderer = installed_renderer(game_root)
    return {
        "path": str(root),
        "hasFolder": root.is_dir(),
        "manifest": manifest,
        "presets": presets,
        "shaders": shaders,
        "installedRenderer": renderer,
        "reshadeInstalled": bool(renderer),
        "store": store_state(),
        "renderers": sorted(RENDERER_DLLS),
        "repositories": repositories(),
        "repositoryStatus": repository_status(manifest),
        "exportNote": EXPORT_NOTE_NAME,
        # A preset that names no file, or names one that is not there, would
        # silently do nothing at play time. Say so instead.
        "ready": bool(manifest["enabled"] and manifest["preset"]
                      and manifest["preset"] in presets and renderer),
    }
