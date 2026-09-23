"""Exact installed-source discovery for the documented FF7R bitmap UI font."""

from __future__ import annotations

from pathlib import Path

from .archive import installed_paks
from .bitmap_font import ATLAS_SUFFIX, GLYPH_SUFFIXES
from .tooling import list_pak


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def discover_documented_bitmap_font_paths(game_root: Path) -> list[str]:
    """Return only exact documented glyph/atlas candidates from installed PAK manifests.

    The general theme scan exposes bounded diagnostic samples. This fallback is
    deliberately narrower: if those samples do not contain the font pair, scan
    manifests for the known suffixes only rather than broadening heuristics.
    """
    suffixes = tuple(suffix.casefold() for suffix in (*GLYPH_SUFFIXES, ATLAS_SUFFIX))
    found: dict[str, str] = {}
    for pak in installed_paks(game_root):
        for raw in list_pak(pak):
            internal = _normalize(raw)
            lowered = internal.casefold()
            if any(lowered.endswith(suffix) for suffix in suffixes):
                # Later PAKs replace earlier definitions, matching archive.py.
                found[lowered] = internal
    return list(found.values())
