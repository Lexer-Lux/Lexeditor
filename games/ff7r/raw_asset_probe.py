"""Read-only probes for cooked FF7R assets outside DataObject/Text resources.

Lexeditor's structured FF7R editor deliberately indexes only formats it can
parse safely. Researching UMG/Blueprint assets still needs a narrow way to find
and inspect the installed cooked package without pretending the generic binary
is editable. This module enumerates matching PAK entries, honors later-PAK
shadowing, extracts only matched .uasset/.uexp files, and reports relevant
printable strings as research evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Iterable

from .archive import installed_paks
from .tooling import get_file, list_pak


PACKAGE_SUFFIXES = (".uasset", ".uexp")
DEFAULT_INTERESTING_TOKENS = (
    "lock",
    "target",
    "marker",
    "reticle",
    "cross",
    "text",
    "color",
    "colour",
    "tint",
    "brush",
    "image",
    "opacity",
    "visibility",
    "visible",
    "hidden",
    "active",
    "widget",
)
MAX_STRINGS_PER_FILE = 192
MAX_SCAN_ERRORS = 128
_ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
_UTF16_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _base_asset(path: str) -> tuple[str, str] | None:
    normalized = _normalize(path)
    folded = normalized.casefold()
    for suffix in PACKAGE_SUFFIXES:
        if folded.endswith(suffix):
            return normalized[:-len(suffix)], suffix
    return None


def select_shadowed_assets(
    pak_listings: Iterable[tuple[str, Iterable[str]]],
    *,
    terms: Iterable[str],
) -> list[dict]:
    """Select matching cooked pairs while applying FF7R's later-PAK override order."""
    folded_terms = tuple(str(term).casefold() for term in terms if str(term).strip())
    if not folded_terms:
        raise ValueError("at least one raw-asset search term is required")

    files: dict[str, dict] = {}
    for pak_name, entries in pak_listings:
        for raw_path in entries:
            parsed = _base_asset(str(raw_path))
            if parsed is None:
                continue
            base, suffix = parsed
            if not any(term in base.casefold() for term in folded_terms):
                continue
            # installed_paks() is sorted deterministically; just like archive.py,
            # later archives replace earlier definitions of the same path.
            key = (base + suffix).casefold()
            files[key] = {"pak": str(pak_name), "path": base + suffix, "suffix": suffix, "asset": base}

    grouped: dict[str, dict] = {}
    for row in files.values():
        key = row["asset"].casefold()
        group = grouped.setdefault(key, {"asset": row["asset"], "files": {}})
        group["files"][row["suffix"]] = {
            "pak": row["pak"],
            "path": row["path"],
        }
    return sorted(grouped.values(), key=lambda row: row["asset"].casefold())


def extract_interesting_strings(
    data: bytes,
    *,
    tokens: Iterable[str] = DEFAULT_INTERESTING_TOKENS,
    limit: int = MAX_STRINGS_PER_FILE,
) -> list[dict]:
    """Return relevant ASCII/UTF-16LE printable strings from one cooked binary."""
    folded_tokens = tuple(str(token).casefold() for token in tokens if str(token).strip())
    if limit <= 0:
        return []
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(encoding: str, offset: int, value: str) -> None:
        normalized = " ".join(value.split())
        if not normalized or not any(token in normalized.casefold() for token in folded_tokens):
            return
        key = (encoding, normalized)
        if key in seen or len(found) >= limit:
            return
        seen.add(key)
        found.append({"encoding": encoding, "offset": offset, "text": normalized})

    for match in _ASCII_RE.finditer(data):
        add("ascii", match.start(), match.group().decode("ascii", errors="replace"))
        if len(found) >= limit:
            return found
    for match in _UTF16_RE.finditer(data):
        add("utf16le", match.start(), match.group().decode("utf-16-le", errors="replace"))
        if len(found) >= limit:
            break
    return found


def _lock_on_text_hits(strings: list[dict]) -> list[dict]:
    hits = []
    for row in strings:
        compact = "".join(ch for ch in row["text"].casefold() if ch.isalnum())
        if "lockon" in compact:
            hits.append(row)
    return hits


def probe_installed_assets(
    game_root: Path,
    *,
    terms: Iterable[str],
    interesting_tokens: Iterable[str] = DEFAULT_INTERESTING_TOKENS,
) -> dict:
    """Find and inspect installed matching cooked assets without modifying them."""
    game_root = Path(game_root).resolve()
    listings: list[tuple[str, list[str]]] = []
    pak_paths: dict[str, Path] = {}
    errors: list[str] = []
    for pak in installed_paks(game_root):
        relative = pak.resolve().relative_to(game_root).as_posix()
        pak_paths[relative] = pak
        try:
            listings.append((relative, list_pak(pak)))
        except Exception as error:
            if len(errors) < MAX_SCAN_ERRORS:
                errors.append(f"{relative}: {error}")

    candidates = select_shadowed_assets(listings, terms=terms)
    results = []
    for candidate in candidates:
        files = []
        for suffix in PACKAGE_SUFFIXES:
            source = candidate["files"].get(suffix)
            if source is None:
                continue
            pak = pak_paths.get(source["pak"])
            if pak is None:
                continue
            try:
                data = get_file(pak, source["path"])
            except Exception as error:
                if len(errors) < MAX_SCAN_ERRORS:
                    errors.append(f"{source['pak']} :: {source['path']}: {error}")
                continue
            strings = extract_interesting_strings(data, tokens=interesting_tokens)
            files.append({
                "suffix": suffix,
                "pak": source["pak"],
                "path": source["path"],
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "interestingStrings": strings,
                "lockOnTextHits": _lock_on_text_hits(strings),
            })
        results.append({"asset": candidate["asset"], "files": files})

    return {
        "terms": list(terms),
        "assets": results,
        "pakCount": len(listings),
        "scanErrors": errors,
        "notes": [
            "Matches are read-only research evidence; cooked UMG/Blueprint packages are not treated as DataObjects.",
            "Later installed PAK definitions shadow earlier files before candidates are reported.",
            "Printable-string hits can identify widget/property/text names but do not by themselves prove a safe edit offset.",
        ],
    }
