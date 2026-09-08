"""Read-only probes for cooked FF7R assets outside DataObject/Text resources.

Lexeditor's structured FF7R editor deliberately indexes only formats it can
parse safely. Researching UMG/Blueprint assets still needs a narrow way to find
and inspect the installed cooked package without pretending the generic binary
is editable. This module enumerates matching PAK entries, honors later-PAK
shadowing, extracts only matched .uasset/.uexp files, and reports relevant
printable strings plus bounded resolved object-table ownership as research
evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Iterable

from .archive import installed_paks
from .package_probe import parse_object_table
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
MAX_OBJECT_ROWS_PER_FILE = 48
MAX_SCAN_ERRORS = 128
_ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
# Do not let the final printable byte of an adjacent ASCII string become the
# first UTF-16LE code unit merely because the ASCII terminator is NUL.
_UTF16_RE = re.compile(rb"(?<![\x20-\x7e])(?:[\x20-\x7e]\x00){4,}")


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


def _matched_object_tokens(row: dict[str, Any], tokens: Iterable[str]) -> list[str]:
    searchable = " ".join(
        str(row.get(key) or "")
        for key in ("objectName", "objectPath", "outerPath", "className", "classPath", "classPackage")
    ).casefold()
    return [
        str(token)
        for token in tokens
        if str(token).strip() and str(token).casefold() in searchable
    ]


def extract_object_evidence(
    data: bytes,
    *,
    tokens: Iterable[str] = DEFAULT_INTERESTING_TOKENS,
    limit: int = MAX_OBJECT_ROWS_PER_FILE,
    label: str = "cooked asset",
) -> dict[str, Any]:
    """Resolve a bounded set of matching import/export owners from one .uasset.

    Object-table metadata can establish class/outer ownership more strongly than
    printable strings. It still does not identify or authorize a serialized UMG
    child-property edit, so callers must treat these rows as research evidence.
    """
    if limit <= 0:
        return {
            "objectTableParsed": True,
            "objectTableSummary": {},
            "resolvedImports": [],
            "resolvedExports": [],
        }
    token_list = tuple(str(token) for token in tokens if str(token).strip())
    table = parse_object_table(data, label=label)

    import_rows = []
    for row in table.imports:
        package_index = -(row.index + 1)
        candidate = {
            "index": row.index,
            "packageIndex": package_index,
            "objectName": row.object_name.display,
            "objectPath": table.resolve_path(package_index),
            "outerIndex": row.outer_index,
            "outerPath": table.resolve_path(row.outer_index),
            "classPackage": row.class_package.display,
            "className": row.class_name.display,
        }
        matched = _matched_object_tokens(candidate, token_list)
        if matched:
            candidate["matchedTokens"] = matched
            import_rows.append(candidate)

    export_rows = []
    for candidate in table.export_rows():
        matched = _matched_object_tokens(candidate, token_list)
        if matched:
            export_rows.append({**candidate, "matchedTokens": matched})

    def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Longer matched anchors carry more ownership information than generic
        # tokens such as Text or Color, so retain them first when bounding output.
        return sorted(
            rows,
            key=lambda row: (
                -sum(len(str(token)) for token in row.get("matchedTokens", ())),
                -len(row.get("matchedTokens", ())),
                str(row.get("objectPath") or row.get("objectName") or "").casefold(),
            ),
        )[:limit]

    return {
        "objectTableParsed": True,
        "objectTableSummary": table.summary(),
        "resolvedImports": rank(import_rows),
        "resolvedExports": rank(export_rows),
    }


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
            file_row = {
                "suffix": suffix,
                "pak": source["pak"],
                "path": source["path"],
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "interestingStrings": strings,
                "lockOnTextHits": _lock_on_text_hits(strings),
            }
            if suffix == ".uasset":
                try:
                    file_row.update(extract_object_evidence(
                        data,
                        tokens=interesting_tokens,
                        label=source["path"],
                    ))
                except Exception as error:
                    # Object metadata is a stronger optional research layer. A
                    # package layout we cannot parse remains explicitly unresolved
                    # instead of aborting the printable-string scan or guessing.
                    file_row.update({
                        "objectTableParsed": False,
                        "objectTableError": str(error),
                        "resolvedImports": [],
                        "resolvedExports": [],
                    })
            files.append(file_row)
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
            "Resolved object-table rows can strengthen class/outer ownership, but still do not prove an exact serialized child-property edit.",
        ],
    }
