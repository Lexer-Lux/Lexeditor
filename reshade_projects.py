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
        # A preset that names no file, or names one that is not there, would
        # silently do nothing at play time. Say so instead.
        "ready": bool(manifest["enabled"] and manifest["preset"]
                      and manifest["preset"] in presets and renderer),
    }
