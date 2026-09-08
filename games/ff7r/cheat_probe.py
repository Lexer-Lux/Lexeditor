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
MAX_ROW_CANDIDATES_PER_TARGET = 128
MAX_CONTROL_FIELDS_PER_ROW = 64
ARRAY_PATH_RE = re.compile(r"^([^.[\]]+)\[(\d+)\]")
CONTROL_FIELD_TERMS = (
    "enable",
    "visible",
    "visibility",
    "select",
    "available",
    "availability",
    "unlock",
    "display",
    "show",
    "hide",
    "menu",
    "option",
    "difficulty",
    "mode",
    "category",
    "group",
    "condition",
)


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


def _control_like(name: str) -> bool:
    normalized = _identifier(name)
    return any(term in normalized for term in CONTROL_FIELD_TERMS)


def _compact_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return {"kind": "array", "length": len(value)}
    if isinstance(value, dict):
        return {"kind": "object", "fields": sorted(str(key) for key in value)[:32]}
    return {"kind": type(value).__name__}


def _property_detail(prop: Any) -> dict:
    api = getattr(prop, "api", None)
    if callable(api):
        try:
            detail = dict(api())
            if detail:
                return detail
        except Exception:
            pass
    return {
        "name": str(getattr(prop, "name", "")),
        "typeCode": getattr(prop, "type_code", None),
        "array": bool(getattr(prop, "is_array", False)),
    }


def _row_control_fields(package: Any, values: Any) -> list[dict]:
    if not isinstance(values, dict):
        return []
    fields = []
    for prop in getattr(package, "properties", ()):
        name = str(getattr(prop, "name", ""))
        if not name or not _control_like(name) or name not in values:
            continue
        fields.append({
            **_property_detail(prop),
            "value": _compact_value(values[name]),
        })
        if len(fields) >= MAX_CONTROL_FIELDS_PER_ROW:
            break
    return fields


def _array_element_candidate(package: Any, path: str) -> dict | None:
    match = ARRAY_PATH_RE.match(path)
    if not match:
        return None
    property_name, index_text = match.groups()
    for prop in getattr(package, "properties", ()):
        if str(getattr(prop, "name", "")) != property_name or not bool(getattr(prop, "is_array", False)):
            continue
        return {
            "property": property_name,
            "index": int(index_text),
            "typeCode": getattr(prop, "type_code", None),
        }
    return None


def _asset_coverage(results: list[dict]) -> list[dict]:
    assets: dict[str, dict] = {}
    for target in results:
        target_key = str(target["key"])
        for row in target.get("rowCandidates", ()):
            asset = str(row.get("asset", ""))
            if not asset:
                continue
            summary = assets.setdefault(asset, {
                "asset": asset,
                "targets": set(),
                "rowCandidates": 0,
                "textIdMatches": 0,
                "identifierMatches": 0,
                "arrayElementCandidates": 0,
            })
            summary["targets"].add(target_key)
            summary["rowCandidates"] += 1
            summary["textIdMatches"] += sum(1 for match in row.get("matches", ()) if match.get("match") == "text-id")
            summary["identifierMatches"] += sum(1 for match in row.get("matches", ()) if match.get("match") == "identifier")
            summary["arrayElementCandidates"] += len(row.get("arrayElementCandidates", ()))
    out = []
    for summary in assets.values():
        out.append({**summary, "targets": sorted(summary["targets"])})
    return sorted(
        out,
        key=lambda row: (
            -len(row["targets"]),
            -int(row["textIdMatches"]),
            -int(row["rowCandidates"]),
            row["asset"].casefold(),
        ),
    )


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
        schema_details: list[dict] = []
        seen_schema: set[tuple[str, str]] = set()
        row_candidates: list[dict] = []
        for asset, package in data_sources:
            for prop in getattr(package, "properties", ()):
                name = str(getattr(prop, "name", ""))
                if _identifier_matches(target, name):
                    schema_hits.append(f"{asset} :: property {name}")
                    schema_key = (asset, name)
                    if schema_key not in seen_schema and len(schema_details) < MAX_MATCHES_PER_TARGET:
                        seen_schema.add(schema_key)
                        schema_details.append({"asset": asset, **_property_detail(prop)})
            for ordinal, entry in enumerate(getattr(package, "entries", ())):
                tag = str(getattr(entry, "tag", ""))
                values = getattr(entry, "values", {})
                row_matches: list[dict] = []
                array_candidates: list[dict] = []
                seen_arrays: set[tuple[str, int]] = set()
                if _identifier_matches(target, tag):
                    key = (asset, tag, "<record>", tag)
                    record_match = {"property": "<record>", "value": tag, "match": "identifier"}
                    row_matches.append(record_match)
                    if key not in seen_refs and len(references) < MAX_MATCHES_PER_TARGET:
                        seen_refs.add(key)
                        references.append({"asset": asset, "record": tag, **record_match})
                for path, value in _walk(values):
                    match = "text-id" if value in text_ids else ("identifier" if _identifier_matches(target, value) else "")
                    if not match:
                        continue
                    row_match = {"property": path, "value": value, "match": match}
                    row_matches.append(row_match)
                    array_candidate = _array_element_candidate(package, path)
                    if array_candidate is not None:
                        array_key = (array_candidate["property"], array_candidate["index"])
                        if array_key not in seen_arrays:
                            seen_arrays.add(array_key)
                            array_candidates.append(array_candidate)
                    key = (asset, tag, path, value)
                    if key in seen_refs or len(references) >= MAX_MATCHES_PER_TARGET:
                        continue
                    seen_refs.add(key)
                    references.append({"asset": asset, "record": tag, **row_match})

                if row_matches and len(row_candidates) < MAX_ROW_CANDIDATES_PER_TARGET:
                    text_id_count = sum(1 for match in row_matches if match["match"] == "text-id")
                    identifier_count = len(row_matches) - text_id_count
                    controls = _row_control_fields(package, values)
                    # This is an evidence ranking only. Exact text-ID ownership
                    # dominates identifier resemblance; structural array evidence
                    # is useful because FF7R's writer can safely remove proved
                    # fixed-width array elements, but the probe never does so.
                    evidence_score = text_id_count * 100 + identifier_count * 20
                    evidence_score += len(array_candidates) * 25 + min(len(controls), 10)
                    row_candidates.append({
                        "asset": asset,
                        "entryIndex": int(getattr(entry, "index", ordinal)),
                        "record": tag,
                        "matches": row_matches,
                        "controlFields": controls,
                        "arrayElementCandidates": array_candidates,
                        "evidenceScore": evidence_score,
                    })

        row_candidates.sort(
            key=lambda row: (-int(row["evidenceScore"]), row["asset"].casefold(), int(row["entryIndex"]))
        )
        results.append({
            "key": target.key,
            "label": target.label,
            "searchTerms": list(target.text_aliases),
            "textMatches": text_hits,
            "textIds": sorted(text_ids),
            "dataReferences": references,
            "schemaMatches": sorted(set(schema_hits))[:MAX_MATCHES_PER_TARGET],
            "schemaDetails": schema_details,
            "rowCandidates": row_candidates,
        })

    return {
        "language": language.upper(),
        "targets": results,
        "assetCoverage": _asset_coverage(results),
        "textResourcesScanned": len(text_sources),
        "dataObjectsScanned": len(data_sources),
        "scanErrors": list(scan_errors),
        "notes": [
            "Exact text-ID references are stronger evidence than identifier-only matches.",
            "Row candidates preserve matched fields plus visibility/selectability/control-like companion fields so the owning menu row can be validated before editing.",
            "Array-element candidates identify structural removal opportunities only when the matched field belongs to a declared DataObject array; they are not automatically removed.",
            "Asset coverage ranks DataObjects that independently reference multiple requested cheat surfaces, which is useful evidence for a shared menu/options owner.",
            "This probe is read-only; matches are candidates until the owning menu row is validated.",
            "Removing or blanking localized strings alone is not an implementation of No More Cheats.",
        ],
    }
