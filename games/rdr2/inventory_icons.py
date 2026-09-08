"""On-demand RDR2 inventory artwork that must come from the installed game.

Most catalog artwork is checked in under ``assets/dictionary_icons``.  A small
set of Story Mode catalog references points at UI_ITEMVIEWER textures that are
not in the base dictionary: the C5/C6 treasure maps live in the
``dlc_content_extra`` dictionary instead.  Resolve those seven names from the
user's installed game into Lexeditor's private cache rather than redistributing
another copy of Rockstar's texture data.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import subprocess
import threading
import zlib
from pathlib import Path

try:
    from .paths import GAME_ROOT, LEXEDITOR_ROOT, PRIVATE_DATA_ROOT
except ImportError:
    from paths import GAME_ROOT, LEXEDITOR_ROOT, PRIVATE_DATA_ROOT


DLC_TREASURE_MAP_IDS = frozenset({
    "treasure_map_c5_m1",
    "treasure_map_c5_m2",
    "treasure_map_c5_m3",
    "treasure_map_c6_m1",
    "treasure_map_c6_m2",
    "treasure_map_c6_m3",
    "treasure_map_c6_m4",
})

_DLC_ARCHIVE = Path("x64") / "dlcpacks" / "dlc_content_extra" / "dlc.rpf"
_DLC_ENTRY = "x64/textures/ui/ui_itemviewer.ytd"
_TOOL_ROOT = LEXEDITOR_ROOT / "tools" / "rpf-cli" / "bin"
_TOOL = _TOOL_ROOT / "RpfCli.exe"
_CACHE_ROOT = PRIVATE_DATA_ROOT / "inventory-icons" / "ui_itemviewer"
_SAFE_ID = re.compile(r"[a-z0-9_]{1,128}\Z")
_RSC8_MAGIC = 0x38435352
_lock = threading.RLock()
_loaded = {}


def _archive_generation(archive: Path) -> str:
    stat = archive.stat()
    identity = f"{archive.resolve()}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:20]


def _normalize_decoded_rsc8(data: bytes) -> bytes:
    """Turn RpfCli's decoded RSC8 into a standard deflate RSC8.

    ``RPF8.GetFile(..., true)`` decrypts/decompresses a resource, then rebuilds
    its 16-byte RSC8 header with compressor id ``None``.  texfury intentionally
    handles normal game RSC8 compressors (deflate/Oodle), not that internal CLI
    representation.  Recompress the already-decoded virtual+physical payload
    with raw deflate and encode compressor id 1.  No texture bytes are changed.
    """
    if len(data) < 16:
        raise ValueError("decoded RSC8 is shorter than its header")
    magic, version_field, virtual_flags, physical_flags = struct.unpack_from("<IIII", data, 0)
    if magic != _RSC8_MAGIC:
        raise ValueError(f"decoded resource has bad RSC8 magic 0x{magic:08X}")

    virtual_size = virtual_flags & 0xFFFFFFF0
    physical_size = physical_flags & 0xFFFFFFF0
    expected = virtual_size + physical_size
    payload = data[16:]
    if len(payload) < expected:
        raise ValueError(
            f"decoded RSC8 payload is truncated ({len(payload)} < {expected})"
        )
    payload = payload[:expected]

    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    compressed = compressor.compress(payload) + compressor.flush()
    # RSC8 stores compressor_id - 1 in bits 8..12.  Deflate is id 1 => 0.
    version_field &= ~(0x1F << 8)
    return struct.pack(
        "<IIII", magic, version_field, virtual_flags, physical_flags
    ) + compressed


def _extract_dictionary(archive: Path, generation: str) -> Path:
    cache = _CACHE_ROOT / generation
    normalized = cache / "dlc_content_extra_ui_itemviewer.ytd"
    if normalized.is_file():
        return normalized
    if not _TOOL.is_file():
        raise FileNotFoundError(f"RDR2 extractor is missing: {_TOOL}")

    cache.mkdir(parents=True, exist_ok=True)
    decoded = cache / "dlc_content_extra_ui_itemviewer.decoded.ytd"
    temporary = decoded.with_suffix(decoded.suffix + ".tmp")
    normalized_tmp = normalized.with_suffix(normalized.suffix + ".tmp")
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            [str(_TOOL), str(archive), _DLC_ENTRY, str(temporary)],
            cwd=_TOOL_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=flags,
        )
        if result.returncode != 0 or not temporary.is_file():
            detail = (result.stderr or result.stdout or "RpfCli extraction failed").strip()
            raise RuntimeError(detail)
        normalized_tmp.write_bytes(_normalize_decoded_rsc8(temporary.read_bytes()))
        normalized_tmp.replace(normalized)
        return normalized
    finally:
        temporary.unlink(missing_ok=True)
        normalized_tmp.unlink(missing_ok=True)
        decoded.unlink(missing_ok=True)


def _load_dictionary(archive: Path, generation: str):
    known = _loaded.get(generation)
    if known is not None:
        return known

    # texfury is a normal Lexeditor dependency, but import lazily so plugin
    # syntax/unit checks do not need its native codec loaded unless artwork is
    # actually requested.
    from texfury import ITD

    dictionary = ITD.load(_extract_dictionary(archive, generation))
    _loaded.clear()  # An installed-game update starts a new generation.
    _loaded[generation] = dictionary
    return dictionary


def _write_png(dictionary, texture_id: str, target: Path) -> Path | None:
    try:
        texture = dictionary.get(texture_id)
    except KeyError:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        texture.to_pil().save(temporary, format="PNG")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def resolve_inventory_icon(texture_id: str) -> Path | None:
    """Return a private cached PNG for one supported missing UI_ITEMVIEWER id.

    The public HTTP path is user-controlled, so only the seven proven texture
    names are accepted.  Archive and entry paths are constants and source RPFs
    are read-only.
    """
    texture_id = str(texture_id or "").strip().lower()
    if not _SAFE_ID.fullmatch(texture_id) or texture_id not in DLC_TREASURE_MAP_IDS:
        return None

    archive = GAME_ROOT / _DLC_ARCHIVE
    if not archive.is_file():
        return None

    with _lock:
        generation = _archive_generation(archive)
        target = _CACHE_ROOT / generation / f"{texture_id}.png"
        if target.is_file():
            return target
        try:
            return _write_png(_load_dictionary(archive, generation), texture_id, target)
        except (OSError, RuntimeError, ValueError, ImportError):
            # Artwork is optional UI enrichment.  A missing/unsupported game
            # build should leave the normal broken-image state rather than make
            # the whole RDR2 editor request fail with HTTP 500.
            return None
