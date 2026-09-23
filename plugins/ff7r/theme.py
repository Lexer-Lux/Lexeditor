"""FF7R editor theme metadata and private installed-game asset discovery.

Lexeditor never bundles or publishes Square Enix UI assets.  This module can
copy browser-ready theme resources out of the user's own installed PAKs into
Lexeditor's private data cache when they exist, and otherwise reports the
cooked Unreal sources that still require decoding.  The editor always has a
proprietary-data-free FF7R-inspired fallback theme.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .archive import installed_paks
from .tooling import get_file, list_pak


THEME_NAME = "ff7r"
SOUND_SLOTS = ("confirm", "back", "move", "launch", "exit", "save")
FONT_EXTENSIONS = (".woff2", ".woff", ".ttf", ".otf")
IMAGE_EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg")
AUDIO_EXTENSIONS = (".wav", ".ogg", ".mp3")
BROWSER_EXTENSIONS = frozenset((*FONT_EXTENSIONS, *IMAGE_EXTENSIONS, *AUDIO_EXTENSIONS))
COOKED_EXTENSIONS = frozenset((".uasset", ".uexp", ".ubulk"))

# These values are deliberately original CSS, not sampled or bundled game
# data.  Local installed-game resources can be layered over them below.
FALLBACK_THEME = {
    "bg": "#070b12",
    "panel": "#0d1722f2",
    "panel-2": "#132334f2",
    "border": "#456782",
    "text": "#eef7ff",
    "muted": "#91a7ba",
    "accent": "#36b6ee",
    "accent-text": "#ffffff",
    "highlight": "#88dcff",
    "success": "#70d6b1",
    "danger": "#ff6e76",
    "font": '"Lex FF7R Local", Candara, "Segoe UI", system-ui, sans-serif',
    "heading-font": '"Lex FF7R Local", Candara, "Segoe UI", system-ui, sans-serif',
    "radius": "1px",
    "panel-gap": "clamp(9px, .9vw, 14px)",
    "ff7r-background-image": "none",
    "ff7r-panel-image": "none",
}

_SOUND_TOKENS = {
    "confirm": ("confirm", "decision", "decide", "select", "enter", "ok"),
    "back": ("cancel", "back", "return"),
    "move": ("cursor", "move", "focus", "hover", "tick"),
    "launch": ("menuopen", "menu_open", "windowopen", "window_open", "open"),
    "exit": ("menuclose", "menu_close", "windowclose", "window_close", "close", "exit"),
    "save": ("save", "complete", "success"),
}


def theme_cache_root(data_root: Path) -> Path:
    return Path(data_root).resolve() / "theme-assets"


def _safe_internal(path: str) -> str | None:
    value = str(path).replace("\\", "/").lstrip("/")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _pak_signature(paks: Iterable[Path]) -> list[dict]:
    return [
        {
            "path": str(path.resolve()),
            "size": path.stat().st_size,
            "mtimeNs": path.stat().st_mtime_ns,
        }
        for path in paks
    ]


def _load_scan_cache(root: Path, signature: list[dict]) -> dict | None:
    path = root / "source-scan.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if payload.get("schema") != 1 or payload.get("signature") != signature:
        return None
    return payload


def _write_scan_cache(root: Path, payload: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    target = root / "source-scan.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _ui_path(path: str) -> bool:
    lowered = path.casefold()
    return "/gamecontents/menu/" in lowered or "/ui/" in lowered or "/menu/" in lowered


def _score_font(path: str) -> int:
    lowered = path.casefold()
    if Path(lowered).suffix not in FONT_EXTENSIONS or not _ui_path(lowered) or "font" not in lowered:
        return -1
    score = 10
    if "systemfontnormal" in lowered:
        score += 10
    if "resident/font" in lowered:
        score += 5
    return score


def _score_image(path: str, kind: str) -> int:
    lowered = path.casefold()
    if Path(lowered).suffix not in IMAGE_EXTENSIONS or not _ui_path(lowered):
        return -1
    tokens = ("background", "backdrop", "window", "frame") if kind == "background" else ("panel", "window", "frame", "box")
    matches = sum(token in lowered for token in tokens)
    return 10 + matches * 3 if matches else -1


def _score_sound(path: str, slot: str) -> int:
    lowered = path.casefold()
    if Path(lowered).suffix not in AUDIO_EXTENSIONS:
        return -1
    if not ("sound" in lowered or "audio" in lowered or "/se/" in lowered or "sfx" in lowered):
        return -1
    matches = sum(token in lowered for token in _SOUND_TOKENS[slot])
    if not matches:
        return -1
    score = 10 + matches * 4
    if _ui_path(lowered):
        score += 4
    return score


def _unique_best(rows: dict[str, tuple[Path, str]], scorer) -> tuple[Path, str] | None:
    scored = [(scorer(internal), pak, internal) for pak, internal in rows.values()]
    scored = [row for row in scored if row[0] >= 0]
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], row[2].casefold()))
    best = scored[0][0]
    if sum(score == best for score, _pak, _internal in scored) != 1:
        return None
    _score, pak, internal = scored[0]
    return pak, internal


def _copy_direct(source: tuple[Path, str] | None, target_stem: Path) -> str | None:
    if source is None:
        return None
    pak, internal = source
    suffix = Path(internal).suffix.casefold()
    if suffix not in BROWSER_EXTENSIONS:
        return None
    target_stem.parent.mkdir(parents=True, exist_ok=True)
    for old_suffix in BROWSER_EXTENSIONS:
        old = target_stem.with_suffix(old_suffix)
        if old.is_file() and old.suffix.casefold() != suffix:
            old.unlink()
    target = target_stem.with_suffix(suffix)
    data = get_file(pak, internal)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return target.name


def _cooked_samples(paths: Iterable[str]) -> dict[str, list[str]]:
    fonts: list[str] = []
    textures: list[str] = []
    sounds: list[str] = []
    widgets: list[str] = []
    for path in paths:
        lowered = path.casefold()
        if Path(lowered).suffix not in COOKED_EXTENSIONS:
            continue
        if "/gamecontents/menu/resident/font/" in lowered or "systemfont" in lowered:
            if len(fonts) < 24:
                fonts.append(path)
        elif "/gamecontents/menu/resident/texture/" in lowered:
            if len(textures) < 24:
                textures.append(path)
        elif ("sound" in lowered or "/se/" in lowered or "sfx" in lowered) and ("menu" in lowered or "/ui/" in lowered):
            if len(sounds) < 24:
                sounds.append(path)
        elif "/gamecontents/menu/" in lowered and ("widget" in lowered or "/u_" in lowered):
            if len(widgets) < 24:
                widgets.append(path)
    return {"fonts": fonts, "textures": textures, "sounds": sounds, "widgets": widgets}


def scan_installed_theme_sources(game_root: Path, data_root: Path) -> dict:
    """Scan installed PAK manifests and extract only unambiguously browser-ready UI files."""
    root = theme_cache_root(data_root)
    try:
        paks = installed_paks(game_root)
    except FileNotFoundError:
        paks = []
    signature = _pak_signature(paks)
    cached = _load_scan_cache(root, signature)
    if cached is not None:
        return cached
    if not paks:
        payload = {
            "schema": 1,
            "signature": signature,
            "direct": {},
            "cooked": {"fonts": [], "textures": [], "sounds": [], "widgets": []},
        }
        _write_scan_cache(root, payload)
        return payload

    # Key by path so later installed PAKs retain the same override semantics as
    # the gameplay index.  The scan stores names/metadata only; cooked payloads
    # are never copied or served as if a browser could consume them.
    browser_rows: dict[str, tuple[Path, str]] = {}
    cooked_paths: dict[str, str] = {}
    for pak in paks:
        for raw in list_pak(pak):
            internal = _safe_internal(raw)
            if internal is None:
                continue
            suffix = Path(internal).suffix.casefold()
            key = internal.casefold()
            if suffix in BROWSER_EXTENSIONS and _ui_path(internal):
                browser_rows[key] = (pak, internal)
            if suffix in COOKED_EXTENSIONS and (
                "/gamecontents/menu/" in key
                or (("sound" in key or "/se/" in key or "sfx" in key) and ("menu" in key or "/ui/" in key))
            ):
                cooked_paths[key] = internal

    direct: dict[str, str] = {}
    font = _copy_direct(_unique_best(browser_rows, _score_font), root / "font")
    if font:
        direct["font"] = font
    for kind in ("background", "panel"):
        filename = _copy_direct(
            _unique_best(browser_rows, lambda path, kind=kind: _score_image(path, kind)),
            root / kind,
        )
        if filename:
            direct[kind] = filename
    for slot in SOUND_SLOTS:
        filename = _copy_direct(
            _unique_best(browser_rows, lambda path, slot=slot: _score_sound(path, slot)),
            root / "sounds" / slot,
        )
        if filename:
            direct[slot] = f"sounds/{filename}"

    payload = {
        "schema": 1,
        "signature": signature,
        "direct": direct,
        "cooked": _cooked_samples(cooked_paths.values()),
    }
    _write_scan_cache(root, payload)
    return payload


def _existing_variant(root: Path, stem: str, extensions: tuple[str, ...]) -> Path | None:
    for suffix in extensions:
        candidate = root / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _url(path: Path, root: Path) -> str:
    return "/theme-assets/" + path.resolve().relative_to(root.resolve()).as_posix()


def theme_payload(game_root: Path, data_root: Path, *, scan: bool = True) -> dict:
    root = theme_cache_root(data_root)
    scan_result = scan_installed_theme_sources(game_root, data_root) if scan else {
        "direct": {},
        "cooked": {"fonts": [], "textures": [], "sounds": [], "widgets": []},
    }
    font = _existing_variant(root, "font", FONT_EXTENSIONS)
    background = _existing_variant(root, "background", IMAGE_EXTENSIONS)
    panel = _existing_variant(root, "panel", IMAGE_EXTENSIONS)

    theme = dict(FALLBACK_THEME)
    if background:
        theme["ff7r-background-image"] = f'url("{_url(background, root)}")'
    if panel:
        theme["ff7r-panel-image"] = f'url("{_url(panel, root)}")'

    sound_rows = []
    for slot in SOUND_SLOTS:
        asset = _existing_variant(root / "sounds", slot, AUDIO_EXTENSIONS)
        sound_rows.append({
            "slot": slot,
            "available": asset is not None,
            "url": _url(asset, root) if asset else "",
            "source": "installed-game-cache" if asset else "",
        })

    direct_count = int(font is not None) + int(background is not None) + int(panel is not None)
    direct_count += sum(bool(row["available"]) for row in sound_rows)
    cooked = scan_result.get("cooked", {})
    cooked_count = sum(len(cooked.get(kind, [])) for kind in ("fonts", "textures", "sounds", "widgets"))
    return {
        "themeName": THEME_NAME,
        "theme": theme,
        "assetMode": "installed" if direct_count else "fallback",
        "font": {
            "available": font is not None,
            "url": _url(font, root) if font else "",
            "cookedSourceCount": len(cooked.get("fonts", [])),
        },
        "textures": {
            "background": _url(background, root) if background else "",
            "panel": _url(panel, root) if panel else "",
            "cookedSourceCount": len(cooked.get("textures", [])),
        },
        "sounds": {
            "rows": sound_rows,
            "available": sum(bool(row["available"]) for row in sound_rows),
            "total": len(sound_rows),
            "cookedSourceCount": len(cooked.get("sounds", [])),
        },
        "cookedSources": cooked,
        "cookedSourceCount": cooked_count,
        "notes": (
            "Browser-ready UI assets are copied only from this installed game into Lexeditor's private cache. "
            "FF7R's normal UI font, textures, and audio are cooked Unreal resources; they are reported as sources "
            "but are not falsely exposed as web fonts/images/audio until a decoder produces a browser-ready file."
        ),
    }


def theme_asset_file(data_root: Path, relative: str) -> Path | None:
    """Resolve only the small documented set of browser-safe private theme files."""
    root = theme_cache_root(data_root).resolve()
    raw = str(relative).replace("\\", "/").lstrip("/")
    parts = tuple(part for part in raw.split("/") if part)
    if not parts or any(part in {".", ".."} for part in parts):
        return None
    if len(parts) == 1:
        stem = Path(parts[0]).stem
        allowed = stem in {"font", "background", "panel"}
    elif len(parts) == 2 and parts[0] == "sounds":
        allowed = Path(parts[1]).stem in SOUND_SLOTS
    else:
        allowed = False
    suffix = Path(parts[-1]).suffix.casefold()
    if not allowed or suffix not in BROWSER_EXTENSIONS:
        return None
    candidate = (root.joinpath(*parts)).resolve()
    if root not in candidate.parents or not candidate.is_file():
        return None
    return candidate
