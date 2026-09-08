"""Read-only current-install research for FF7R's post-launch cheat/convenience menus.

The public generated SDK predates several 2026 menu additions, so this module
starts from the installed localized labels, resolves their text IDs, and then
finds exact DataObject references plus identifier-like candidates. Results are
research evidence only; no row is removed until its ownership/semantics are
validated.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class CheatTarget:
    key: str
    label: str
    text_aliases: tuple[str, ...]
    identifier_aliases: tuple[str, ...]


TARGETS = (
    CheatTarget("fastStart", "Fast / Head Start", ("fast start", "head start"), ("faststart", "headstart")),
    CheatTarget("easyMode", "Easy Mode", ("easy mode", "easy"), ("easymode", "difficultyeasy", "easy")),
    CheatTarget("giftBox", "Gift Box", ("gift box",), ("giftbox",)),
    CheatTarget(
        "streamlinedProgression",
        "Streamlined Progression",
        ("streamlined progression",),
        ("streamlinedprogression", "streamlineprogression"),
    ),
)

MAX_MATCHES_PER_TARGET = 128


def _plain(value: str) -> str:
    value = re.sub(r"<[^>]*>", " ", value)
    return " ".join(value.casefold().split())


def _identifier(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _walk(value: Any, path: str = ""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}" if path else str(key))


def _text_matches(target: CheatTarget, text: str) -> bool:
    normalized = _plain(text)
    if target.key == "easyMode":
        # Bare "easy" is useful only as an exact difficulty-label match; a
        # substring search would drown the probe in unrelated prose.
        return normalized == "easy" or "easy mode" in normalized
    return any(alias in normalized for alias in target.text_aliases)


def _identifier_matches(target: CheatTarget, value: str) -> bool:
    normalized = _identifier(value)
    if not normalized:
        return False
    if target.key == "easyMode":
        return normalized in {"easy", "easymode", "difficultyeasy"} or "easymode" in normalized
    return any(alias in normalized for alias in target.identifier_aliases)


def scan_installed_menu_candidates(
    text_sources: Iterable[tuple[str, Any]],
    data_sources: Iterable[tuple[str, Any]],
    *,
    language: str = "US",
    scan_errors: Iterable[str] = (),
) -> dict:
    """Scan already-parsed text/DataObject packages for the four requested options."""
    text_sources = list(text_sources)
    data_sources = list(data_sources)
    results = []

    for target in TARGETS:
        text_hits: list[dict] = []
        text_ids: set[str] = set()
        for asset, package in text_sources:
            for entry in getattr(package, "entries", ()):
                candidates = [("TEXT", getattr(entry, "text", ""))]
                candidates.extend(
                    (getattr(sub, "id", "SUB"), getattr(sub, "text", ""))
                    for sub in getattr(entry, "subentries", ())
                )
                for field, text in candidates:
                    if isinstance(text, str) and _text_matches(target, text):
                        text_id = str(getattr(entry, "id", getattr(entry, "key", "")))
                        if text_id:
                            text_ids.add(text_id)
                        if len(text_hits) < MAX_MATCHES_PER_TARGET:
                            text_hits.append({"asset": asset, "textId": text_id, "field": field, "text": text})

        references: list[dict] = []
        seen_refs: set[tuple[str, str, str, str]] = set()
        schema_hits: list[str] = []
        for asset, package in data_sources:
            for prop in getattr(package, "properties", ()):
                name = str(getattr(prop, "name", ""))
                if _identifier_matches(target, name):
                    schema_hits.append(f"{asset} :: property {name}")
            for entry in getattr(package, "entries", ()):
                tag = str(getattr(entry, "tag", ""))
                if _identifier_matches(target, tag):
                    key = (asset, tag, "<record>", tag)
                    if key not in seen_refs and len(references) < MAX_MATCHES_PER_TARGET:
                        seen_refs.add(key)
                        references.append({"asset": asset, "record": tag, "property": "<record>", "value": tag, "match": "identifier"})
                for path, value in _walk(getattr(entry, "values", {})):
                    match = "text-id" if value in text_ids else ("identifier" if _identifier_matches(target, value) else "")
                    if not match:
                        continue
                    key = (asset, tag, path, value)
                    if key in seen_refs or len(references) >= MAX_MATCHES_PER_TARGET:
                        continue
                    seen_refs.add(key)
                    references.append({"asset": asset, "record": tag, "property": path, "value": value, "match": match})

        results.append({
            "key": target.key,
            "label": target.label,
            "searchTerms": list(target.text_aliases),
            "textMatches": text_hits,
            "textIds": sorted(text_ids),
            "dataReferences": references,
            "schemaMatches": sorted(set(schema_hits))[:MAX_MATCHES_PER_TARGET],
        })

    return {
        "language": language.upper(),
        "targets": results,
        "textResourcesScanned": len(text_sources),
        "dataObjectsScanned": len(data_sources),
        "scanErrors": list(scan_errors),
        "notes": [
            "Exact text-ID references are stronger evidence than identifier-only matches.",
            "This probe is read-only; matches are candidates until the owning menu row is validated.",
            "Removing or blanking localized strings alone is not an implementation of No More Cheats.",
        ],
    }
