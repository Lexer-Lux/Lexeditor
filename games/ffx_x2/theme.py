"""Derive cosmetic FFX/X-2 editor assets from the user's installed archives.

No proprietary game art, font data or audio is committed with Lexeditor. This
module extracts a small, bounded theme cache from the local Steam installation.
Theme extraction is cosmetic: parser/editor/deployment functionality must continue
to work when an asset is absent or its browser-ready format is not yet supported.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable

from .vbf import VBFEntry, VBFIndex, read_entry


MAX_RAW_ASSET = 8 * 1024 * 1024
MAX_RAW_SFX_BANK = 16 * 1024 * 1024
MAX_FONT_ATLASES = 8
MAX_TEXTURES = 10
MAX_SFX_BANKS = 4
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEB_FONT_SUFFIXES = (".ttf", ".otf", ".woff", ".woff2")
PLAYABLE_AUDIO_SUFFIXES = (".wav", ".ogg", ".mp3")


def _fold(path: str) -> str:
    return path.replace("\\", "/").casefold()


def _entries(indexes: dict[str, VBFIndex]) -> Iterable[tuple[str, VBFIndex, VBFEntry]]:
    for source, index in indexes.items():
        for entry in index.entries:
            yield source, index, entry


def _safe_name(entry: VBFEntry) -> str:
    basename = Path(entry.path.replace("\\", "/")).name
    basename = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._") or "asset"
    fingerprint = hashlib.sha256(entry.path.encode("utf-8")).hexdigest()[:12]
    return f"{fingerprint}-{basename}"


def _atomic_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _cache_entry(index: VBFIndex, entry: VBFEntry, root: Path, category: str,
                 maximum: int) -> Path | None:
    if entry.size > maximum:
        return None
    target = root / "raw" / category / _safe_name(entry)
    if not target.is_file() or target.stat().st_size != entry.size:
        _atomic_bytes(target, read_entry(index, entry))
    return target


def _source_token(indexes: dict[str, VBFIndex]) -> tuple[str, dict[str, str]]:
    headers = {name: index.header_md5 for name, index in sorted(indexes.items())}
    material = "|".join(f"{name}:{digest}" for name, digest in headers.items())
    return hashlib.sha256(material.encode("ascii")).hexdigest()[:16], headers


def _background_candidate(indexes: dict[str, VBFIndex]):
    candidates = []
    for source, index, entry in _entries(indexes):
        folded = _fold(entry.path)
        if not folded.endswith("titlemenu.png"):
            continue
        rank = 0
        if source != "meta":
            rank += 20
        if "/us/" not in folded:
            rank += 4
        if "/360p/" in folded:
            rank += 8
        candidates.append((rank, len(entry.path), source, index, entry))
    return min(candidates, default=None, key=lambda row: (row[0], row[1], row[4].path.casefold()))


def _font_candidate(indexes: dict[str, VBFIndex]):
    candidates = []
    for source, index, entry in _entries(indexes):
        folded = _fold(entry.path)
        if not folded.endswith(WEB_FONT_SUFFIXES):
            continue
        if "font" not in folded and "base_ftc" not in folded:
            continue
        candidates.append((0 if "/menu" in folded else 1, entry.size, source, index, entry))
    return min(candidates, default=None, key=lambda row: (row[0], row[1], row[4].path.casefold()))


def _is_font_atlas(path: str) -> bool:
    folded = _fold(path)
    return folded.endswith((".dds.phyre", ".fgen.phyre")) and (
        "base_ftc" in folded or "/fonts/" in folded or "/font/" in folded
    )


def _is_ui_texture(path: str) -> bool:
    folded = _fold(path)
    if not folded.endswith((".dds.phyre", ".png")):
        return False
    if _is_font_atlas(path):
        return False
    return any(term in folded for term in (
        "/menu", "/help", "/flash", "savedata", "pad_icon", "titlemenu", "cursor",
    ))


def _is_sfx_path(path: str) -> bool:
    folded = _fold(path)
    if "/sound_pc/" not in folded and "/sound/" not in folded:
        return False
    if any(term in folded for term in ("/music/", "/voice/", "bgm", "dialog", "movie")):
        return False
    return any(term in folded for term in (
        "/se/", "/sfx/", "se_", "sfx", "system", "menu", "cursor", "cancel", "decide", "button", "common",
    ))


def _load_cached(manifest_path: Path, token: str) -> dict | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("token") != token:
        return None
    background = payload.get("background", {})
    if background.get("ready"):
        relative = background.get("relativePath")
        if not isinstance(relative, str) or not (manifest_path.parent / relative).is_file():
            return None
    font = payload.get("font", {})
    if font.get("webReady"):
        relative = font.get("relativePath")
        if not isinstance(relative, str) or not (manifest_path.parent / relative).is_file():
            return None
    sfx = payload.get("sfx", {})
    if sfx.get("webReady"):
        relative = sfx.get("relativePath")
        if not isinstance(relative, str) or not (manifest_path.parent / relative).is_file():
            return None
    return payload


def build(cache_root: Path, archives: dict[str, VBFIndex], meta_index: VBFIndex | None = None) -> dict:
    """Create or reuse one bounded cache generation and return browser-facing status."""
    indexes = dict(archives)
    if meta_index is not None:
        indexes["meta"] = meta_index
    token, headers = _source_token(indexes)
    generation = Path(cache_root).resolve() / token
    manifest_path = generation / "theme.json"
    cached = _load_cached(manifest_path, token)
    if cached is not None:
        return cached

    generation.mkdir(parents=True, exist_ok=True)
    browser = generation / "browser"
    browser.mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "token": token,
        "source": "installed-game",
        "sourceHeaders": headers,
        "background": {"ready": False},
        "font": {"webReady": False, "atlasRecognized": 0, "atlasCached": 0},
        "textures": {"recognized": 0, "cached": 0, "browserPngCached": 0},
        "sfx": {"webReady": False, "recognizedBanks": 0, "cachedBanks": 0},
    }

    background = _background_candidate(indexes)
    if background is not None:
        _rank, _length, source, index, entry = background
        data = read_entry(index, entry)
        if data.startswith(PNG_MAGIC):
            target = browser / "titlemenu.png"
            _atomic_bytes(target, data)
            payload["background"] = {
                "ready": True,
                "url": f"/theme/{token}/browser/titlemenu.png",
                "relativePath": "browser/titlemenu.png",
                "archivePath": entry.path,
                "sourceArchive": source,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        else:
            payload["background"]["note"] = "Installed title-menu candidate was not a PNG."
    elif meta_index is None:
        payload["background"]["note"] = "metamenu.vbf is unavailable; using the built-in fallback theme."
    else:
        payload["background"]["note"] = "No titlemenu.png was found in the installed archives."

    web_font = _font_candidate(indexes)
    if web_font is not None:
        _rank, _size, source, index, entry = web_font
        suffix = next(suffix for suffix in WEB_FONT_SUFFIXES if _fold(entry.path).endswith(suffix))
        target = browser / f"menu-font{suffix}"
        _atomic_bytes(target, read_entry(index, entry))
        payload["font"].update({
            "webReady": True,
            "url": f"/theme/{token}/browser/{target.name}",
            "relativePath": f"browser/{target.name}",
            "archivePath": entry.path,
            "sourceArchive": source,
        })

    font_atlases = [(source, index, entry) for source, index, entry in _entries(indexes)
                    if _is_font_atlas(entry.path)]
    payload["font"]["atlasRecognized"] = len(font_atlases)
    cached_atlases = 0
    for _source, index, entry in sorted(font_atlases, key=lambda row: (row[2].size, row[2].path.casefold()))[:MAX_FONT_ATLASES]:
        if _cache_entry(index, entry, generation, "fonts", MAX_RAW_ASSET) is not None:
            cached_atlases += 1
    payload["font"]["atlasCached"] = cached_atlases
    if not payload["font"]["webReady"] and font_atlases:
        payload["font"]["note"] = "Bitmap/Phyre font atlases are cached locally; glyph-to-webfont conversion is not integrated yet."

    texture_entries = [(source, index, entry) for source, index, entry in _entries(indexes)
                       if _is_ui_texture(entry.path)]
    payload["textures"]["recognized"] = len(texture_entries)
    cached_textures = 0
    png_textures = 0
    for _source, index, entry in sorted(texture_entries, key=lambda row: (row[2].size, row[2].path.casefold()))[:MAX_TEXTURES]:
        target = _cache_entry(index, entry, generation, "textures", MAX_RAW_ASSET)
        if target is not None:
            cached_textures += 1
            if _fold(entry.path).endswith(".png"):
                png_textures += 1
    payload["textures"].update({"cached": cached_textures, "browserPngCached": png_textures})
    if texture_entries:
        payload["textures"]["note"] = "PNG menu art is browser-ready; DDS/Phyre textures are kept as local raw theme sources until a proved converter is integrated."

    playable = [(source, index, entry) for source, index, entry in _entries(indexes)
                if _is_sfx_path(entry.path) and _fold(entry.path).endswith(PLAYABLE_AUDIO_SUFFIXES)
                and entry.size <= MAX_RAW_ASSET]
    if playable:
        source, index, entry = min(playable, key=lambda row: (row[2].size, row[2].path.casefold()))
        suffix = next(suffix for suffix in PLAYABLE_AUDIO_SUFFIXES if _fold(entry.path).endswith(suffix))
        target = browser / f"ui-sfx{suffix}"
        _atomic_bytes(target, read_entry(index, entry))
        payload["sfx"].update({
            "webReady": True,
            "url": f"/theme/{token}/browser/{target.name}",
            "relativePath": f"browser/{target.name}",
            "archivePath": entry.path,
            "sourceArchive": source,
        })

    sound_banks = [(source, index, entry) for source, index, entry in _entries(indexes)
                   if _is_sfx_path(entry.path) and _fold(entry.path).endswith((".fsb", ".fev"))]
    payload["sfx"]["recognizedBanks"] = len(sound_banks)
    cached_banks = 0
    for _source, index, entry in sorted(sound_banks, key=lambda row: (row[2].size, row[2].path.casefold()))[:MAX_SFX_BANKS]:
        if _cache_entry(index, entry, generation, "sfx", MAX_RAW_SFX_BANK) is not None:
            cached_banks += 1
    payload["sfx"]["cachedBanks"] = cached_banks
    if not payload["sfx"]["webReady"] and sound_banks:
        payload["sfx"]["note"] = "FMOD FSB/FEV UI-sound banks are cached locally; browser playback waits for a proved decoder."

    _atomic_json(manifest_path, payload)
    return payload


def asset_path(cache_root: Path, route: str) -> Path:
    """Resolve a browser theme URL beneath the private cache root."""
    root = Path(cache_root).resolve()
    relative = str(route).replace("\\", "/").strip("/")
    target = (root / relative).resolve()
    if target == root or root not in target.parents or not target.is_file():
        raise FileNotFoundError("Theme asset not found")
    if "browser" not in target.parts:
        raise FileNotFoundError("Raw theme sources are not web-served")
    return target
