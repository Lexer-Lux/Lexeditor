"""Cosmetic Dark Souls theme from the player's installed game.

No proprietary game art, font data or audio is committed with Lexeditor. This
module builds a small, bounded theme cache from the local installation:

- title art: the ``Title`` texture from ``menu/<language>/menu_local.tpf.dcx``,
  rendered to PNG through the proved TPF/DDS preview pipeline (assets.py);
- menu fonts: ``font/<language>/DSFont24.ccm.dcx``, ``TalkFont24.ccm.dcx`` and
  ``*.fnt`` are recognized and cached raw; bitmap-to-webfont conversion is
  not integrated, so the editor falls back to an engraved serif stack;
- interface sounds: ``sound/frpg_sm*.fsb`` banks are inventoried through a
  read-only FSB4 header parse and their ``.fev`` projects cached raw; streams
  extract to browser-playable MPEG on demand (``sfx_extract``). The menu
  bank ``frpg_main.fsb`` carries the proved UI events (``CURSOL_MOVE``,
  ``CURSOL_SELECT``, ``CURSOL_CANCEL``), mapped to shell slots below.

FSB payloads (up to 126 MB a bank) are never copied: only their stream counts
and the small ``.fev`` project files land in the cache. Theme extraction is
cosmetic: the editor must keep working when any asset is absent or unreadable,
so every part degrades to a note instead of raising.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct

from .assets import dds_info, parse_tpf, render_png
from .formats import FormatError, inflate

# The installed ENGLISH pack is 2 MB compressed / 26 MB plain with 7 textures.
MAX_MENU_PACK = 64 * 1024 * 1024
MAX_TITLE_TEXTURES = 64
MAX_FONT_FILES = 6
MAX_RAW_FONT = 8 * 1024 * 1024
MAX_FEV_FILES = 8
MAX_RAW_FEV = 4 * 1024 * 1024
MAX_FSB_STREAMS = 20000
FSB_SAMPLE_HEADER = 80
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
FONT_NAMES = ("DSFont24.ccm.dcx", "TalkFont24.ccm.dcx")


def cache_root() -> Path:
    """The private theme cache, outside the checkout and the game."""
    override = os.environ.get("LEXEDITOR_DS1_THEME_CACHE")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "Lexeditor" / "cache" / "ds1-theme"


def _menu_packs(game_root: Path) -> list[Path]:
    packs = sorted((game_root / "menu").glob("*/menu_local.tpf.dcx")) if game_root.is_dir() else []
    return sorted(packs, key=lambda path: (path.parent.name != "ENGLISH", path.as_posix()))


def _font_candidates(game_root: Path) -> list[Path]:
    font_dir = game_root / "font"
    if not font_dir.is_dir():
        return []
    found: list[Path] = []
    for language in sorted(path for path in font_dir.iterdir() if path.is_dir()):
        for name in FONT_NAMES:
            candidate = language / name
            if candidate.is_file():
                found.append(candidate)
        found.extend(sorted(path for path in language.glob("*.fnt") if path.is_file()))
        if len(found) >= MAX_FONT_FILES * 4:
            break
    return found[:MAX_FONT_FILES * 4]


def _sound_banks(game_root: Path) -> list[Path]:
    sound_dir = game_root / "sound"
    if not sound_dir.is_dir():
        return []
    banks = [path for path in sound_dir.glob("frpg_sm*.fsb") if path.is_file()]
    main = sound_dir / "frpg_main.fsb"
    if main.is_file():
        banks.append(main)
    return sorted(banks)


def _sound_projects(game_root: Path) -> list[Path]:
    sound_dir = game_root / "sound"
    if not sound_dir.is_dir():
        return []
    projects = [path for path in sound_dir.glob("frpg_sm*.fev") if path.is_file()]
    main = sound_dir / "frpg_main.fev"
    if main.is_file():
        projects.append(main)
    return sorted(projects)


def _signature(game_root: Path | None) -> tuple[str, list[str]]:
    if game_root is None or not game_root.is_dir():
        return "nogame", []
    inputs: list[str] = []
    for path in _menu_packs(game_root) + _font_candidates(game_root) + _sound_banks(game_root) + _sound_projects(game_root):
        try:
            stat = path.stat()
        except OSError:
            continue
        inputs.append(f"{path.relative_to(game_root).as_posix()}:{stat.st_size}:{stat.st_mtime_ns}")
    material = "|".join(sorted(inputs))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], sorted(inputs)


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


def _cache_raw(source: Path, target: Path, maximum: int) -> bool:
    try:
        if source.stat().st_size > maximum:
            return False
        data = source.read_bytes()
    except OSError:
        return False
    if len(data) > maximum:
        return False
    if target.is_file() and target.stat().st_size == len(data):
        return True
    _atomic_bytes(target, data)
    return True


def _fsb_streams(path: Path) -> int | None:
    """Stream count from an FSB4 bank header, or None when unproven.

    Measured against the installed banks: ``FSB4`` magic, a stream count, then
    80-byte sample headers each starting with its own size. Anything else is
    reported by name and size only, never parsed further.
    """
    try:
        with path.open("rb") as stream:
            header = stream.read(48)
            if len(header) < 48 or header[:4] != b"FSB4":
                return None
            _magic, count, _shdrsize, _datasize = struct.unpack_from("<4sIII", header, 0)
            if not 1 <= count <= MAX_FSB_STREAMS:
                return None
            first = stream.read(FSB_SAMPLE_HEADER)
            if len(first) < FSB_SAMPLE_HEADER or struct.unpack_from("<H", first, 0)[0] != FSB_SAMPLE_HEADER:
                return None
            return count
    except (OSError, struct.error):
        return None


def _tpf_payload(pack: Path) -> bytes:
    raw = pack.read_bytes()
    if len(raw) > MAX_MENU_PACK:
        raise FormatError("That menu pack is too large to theme from")
    if raw[:4] == b"DCX\0":
        return bytes(inflate(raw))
    if raw[:4] == b"TPF\0":
        return raw
    raise FormatError("That is not a Dark Souls menu texture pack")


def _title_part(game_root: Path, generation: Path) -> dict:
    packs = _menu_packs(game_root)
    part: dict = {"ready": False, "packs": len(packs), "textures": 0}
    if not packs:
        part["note"] = "No menu/menu_local.tpf.dcx was found; the title art stays unextracted."
        return part
    try:
        payload = _tpf_payload(packs[0])
        textures = parse_tpf(payload)[:MAX_TITLE_TEXTURES]
    except (OSError, FormatError, ValueError, struct.error) as error:
        part["note"] = f"The menu pack could not be read ({error}); the title art stays unextracted."
        return part
    part["textures"] = len(textures)
    match = next((entry for entry in textures if entry["name"].casefold() == "title"), None)
    if match is None:
        part["note"] = "The menu pack carries no Title texture."
        return part
    try:
        blob = payload[match["offset"]:match["offset"] + match["size"]]
        info = dds_info(blob)
        png = render_png(blob)
    except (OSError, FormatError, ValueError) as error:
        part["note"] = f"The Title texture could not be rendered ({error})."
        return part
    if not png.startswith(PNG_MAGIC):
        part["note"] = "The Title texture did not render to a PNG."
        return part
    target = generation / "browser" / "title.png"
    _atomic_bytes(target, png)
    part.update({
        "ready": True,
        "url": f"/theme/{generation.name}/browser/title.png",
        "relativePath": "browser/title.png",
        "archivePath": packs[0].relative_to(game_root).as_posix(),
        "width": info["width"], "height": info["height"], "format": info["format"],
        "sha256": hashlib.sha256(png).hexdigest(),
    })
    return part


def _font_part(game_root: Path, generation: Path) -> dict:
    candidates = _font_candidates(game_root)
    part: dict = {"webReady": False, "recognized": len(candidates), "cached": 0}
    cached = 0
    for source in sorted(candidates, key=lambda path: (
            path.suffix != ".dcx", path.name not in FONT_NAMES, path.as_posix()))[:MAX_FONT_FILES]:
        target = generation / "raw" / "fonts" / f"{source.parent.name}-{source.name}"
        if _cache_raw(source, target, MAX_RAW_FONT):
            cached += 1
    part["cached"] = cached
    if candidates:
        part["note"] = ("Menu font sources are cached locally; bitmap-to-webfont "
                        "conversion is not integrated, so headings use an engraved serif fallback.")
    else:
        part["note"] = "No font/ menu font sources were found."
    return part


def _sfx_part(game_root: Path, generation: Path) -> dict:
    banks = _sound_banks(game_root)
    projects = _sound_projects(game_root)
    part: dict = {"webReady": False, "recognizedBanks": len(banks), "streams": 0,
                  "banks": [], "cachedProjects": 0}
    streams = 0
    for bank in banks:
        count = _fsb_streams(bank)
        try:
            size = bank.stat().st_size
        except OSError:
            continue
        if count is not None:
            streams += count
        part["banks"].append({"name": bank.name, "size": size, "streams": count})
    part["streams"] = streams
    cached = 0
    for source in sorted(projects, key=lambda path: path.name)[:MAX_FEV_FILES]:
        if _cache_raw(source, generation / "raw" / "sfx" / source.name, MAX_RAW_FEV):
            cached += 1
    part["cachedProjects"] = cached
    if banks:
        part["note"] = ("FMOD sound banks stream browser-playable MPEG once extracted; "
                        "the frpg_main menu bank feeds the shell sound slots.")
    else:
        part["note"] = "No sound/frpg_sm or frpg_main sound banks were found."
    return part


def _load_cached(manifest_path: Path, token: str) -> dict | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("token") != token:
        return None
    title = payload.get("title", {})
    if title.get("ready"):
        relative = title.get("relativePath")
        if not isinstance(relative, str) or not (manifest_path.parent / relative).is_file():
            return None
    return payload


def fallback(note: str) -> dict:
    """The editor-safe theme state when extraction cannot run."""
    return {
        "token": "nogame",
        "source": "fallback",
        "title": {"ready": False, "packs": 0, "textures": 0, "note": note},
        "font": {"webReady": False, "recognized": 0, "cached": 0, "note": note},
        "sfx": {"webReady": False, "recognizedBanks": 0, "streams": 0, "banks": [],
                "cachedProjects": 0, "note": note},
    }


def build(cache_root: Path, game_root: Path | None) -> dict:
    """Create or reuse one bounded cache generation and return browser-facing status."""
    if game_root is None or not Path(game_root).is_dir():
        return fallback("Select the installed game before extracting its theme.")
    game_root = Path(game_root)
    token, _inputs = _signature(game_root)
    generation = Path(cache_root).resolve() / token
    manifest_path = generation / "theme.json"
    cached = _load_cached(manifest_path, token)
    if cached is not None:
        return cached

    generation.mkdir(parents=True, exist_ok=True)
    (generation / "browser").mkdir(parents=True, exist_ok=True)
    payload: dict = {
        "token": token,
        "source": "installed-game",
        "title": _title_part(game_root, generation),
        "font": _font_part(game_root, generation),
        "sfx": _sfx_part(game_root, generation),
    }
    _atomic_json(manifest_path, payload)
    for sibling in generation.parent.iterdir():
        if sibling.name == token or not sibling.is_dir():
            continue
        shutil.rmtree(sibling, ignore_errors=True)
    return payload


# On-demand interface-sound extraction, bounded: at most this many
# cached streams totalling this many bytes per generation. Old
# generations (and their sounds) are pruned by build().
MAX_SFX_FILES = 256
MAX_SFX_BYTES = 64 * 1024 * 1024
_BANK_NAME = re.compile(r"(frpg_sm\d+|frpg_main)\.fsb\Z")
_STREAM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.wav\Z")


def _sfx_bank(game_root: Path, bank: str) -> Path:
    """The bank file for a client-supplied bank name, or an error that
    names no filesystem layout."""
    if not _BANK_NAME.fullmatch(str(bank or "")):
        raise ValueError("Unknown sound bank")
    target = (Path(game_root) / "sound" / bank)
    if not target.is_file():
        raise ValueError("Unknown sound bank")
    return target


def sfx_streams(cache_root: Path, game_root: Path | None, bank: str) -> list[dict]:
    """[{name, duration, size}] for one interface bank's proved streams."""
    from . import fsb as _fsb
    if game_root is None or not Path(game_root).is_dir():
        raise ValueError("Select the installed game before listing its sounds")
    return [{"name": entry["name"], "duration": entry["duration"], "size": entry["size"]}
            for entry in _fsb.parse_table(_sfx_bank(Path(game_root), bank))]


def sfx_extract(cache_root: Path, game_root: Path | None, bank: str, stream: str) -> str:
    """Extract one interface stream to clean browser-playable MPEG in
    the current generation's browser files, returning its theme URL."""
    from . import fsb as _fsb
    if game_root is None or not Path(game_root).is_dir():
        raise ValueError("Select the installed game before extracting its sounds")
    if not _STREAM_NAME.fullmatch(str(stream or "")):
        raise ValueError("Unknown sound stream")
    state = build(Path(cache_root), Path(game_root))
    if state.get("source") != "installed-game":
        raise ValueError("Select the installed game before extracting its sounds")
    table = _fsb.parse_table(_sfx_bank(Path(game_root), bank))
    entry = next((item for item in table if item["name"] == stream), None)
    if entry is None:
        raise ValueError("Unknown sound stream")
    folder = Path(cache_root).resolve() / state["token"] / "browser" / "sfx" / Path(bank).stem
    target = folder / (Path(stream).stem + ".mp3")
    if target.is_file():
        return f"/theme/{state['token']}/browser/sfx/{Path(bank).stem}/{target.name}"
    cached = sorted(folder.glob("*.mp3")) if folder.is_dir() else []
    if len(cached) >= MAX_SFX_FILES or sum(path.stat().st_size for path in cached) >= MAX_SFX_BYTES:
        raise ValueError("The theme sound cache is full")
    _atomic_bytes(target, _fsb.extract_mp3(_sfx_bank(Path(game_root), bank), entry))
    return f"/theme/{state['token']}/browser/sfx/{Path(bank).stem}/{target.name}"


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


# Menu UI events, proved against the installed frpg_main bank and its FEV
# event paths (/frpg_main/CURSOL_MOVE and siblings): the cursor tick, the
# confirm blip, the cancel sound and the game-start jingle. exit/save have
# no proved source and stay silent.
MENU_SOUNDS = {
    "move": ("frpg_main.fsb", "CURSOL_MOVE.wav"),
    "confirm": ("frpg_main.fsb", "CURSOL_SELECT.wav"),
    "back": ("frpg_main.fsb", "CURSOL_CANCEL.wav"),
    "launch": ("frpg_main.fsb", "GAMESTART.wav"),
}


def menu_sound_rows(cache_root, game_root):
    """{ready, rows} for the six shell slots, mirroring core.theme_sounds."""
    from core.theme_sounds import SOUND_SLOTS
    rows = []
    for slot in SOUND_SLOTS:
        mapped = MENU_SOUNDS.get(slot)
        if mapped is None or game_root is None or not Path(game_root).is_dir():
            rows.append({"slot": slot, "available": False, "sourceId": None,
                         "url": "", "message": "No proven source sound is mapped."})
            continue
        bank, stream = mapped
        try:
            url = sfx_extract(Path(cache_root), Path(game_root), bank, stream)
        except (ValueError, OSError, FormatError) as error:
            rows.append({"slot": slot, "available": False, "sourceId": stream,
                         "url": "", "message": f"{bank} {stream} is unavailable ({error})."})
            continue
        duration = ""
        try:
            entry = next(item for item in sfx_streams(Path(cache_root), Path(game_root), bank)
                         if item["name"] == stream)
            duration = f", {entry['duration']:.2f}s"
        except (ValueError, OSError, FormatError):
            pass
        rows.append({"slot": slot, "available": True, "sourceId": stream,
                     "url": url, "message": f"From {bank} {stream}{duration}."})
    return {"ready": any(row["available"] for row in rows), "rows": rows}
