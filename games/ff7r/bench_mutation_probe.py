"""Read-only mutation-surface inventory for the exact Chapter 3 bench (#427).

Before attempting a cooked-map actor deletion, inspect the installed ObjectLayout
row that already identifies the authored bench instance. This module inventories
its actual schema/value surface and ranks fields whose *names* are related to
visibility, interaction, actions, collision, navigation, state or attributes.
It also reports values observed on other installed rows.

This is discovery only. Property names and alternative values do not establish
semantics, and this module never edits a DataObject or authorizes suppression.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from .dataobject import DataObjectPackage


MAX_ALTERNATIVES = 24
MAX_ROWS_PER_ALTERNATIVE = 8
IDENTITY_FIELDS = {
    "UniqueIndex",
    "NodeName",
    "LevelName",
    "BGActorName",
}
FIELD_TOKEN_WEIGHTS = {
    "visible": 10,
    "visibility": 10,
    "hidden": 10,
    "enable": 9,
    "disable": 9,
    "collision": 8,
    "navigation": 8,
    "nav": 6,
    "interact": 8,
    "pushbutton": 8,
    "action": 7,
    "attribute": 6,
    "state": 5,
    "actor": 3,
    "priority": 1,
}
LITERAL_STATE_TOKENS = (
    "disable",
    "disabled",
    "hidden",
    "inactive",
    "invalid",
    "none",
    "off",
)


def _canonical_value(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _field_score(name: str) -> tuple[int, list[str]]:
    folded = str(name).casefold().replace("_", "")
    matched = sorted(
        token for token in FIELD_TOKEN_WEIGHTS
        if token in folded
    )
    return sum(FIELD_TOKEN_WEIGHTS[token] for token in matched), matched


def _literal_state_tokens(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    folded = value.casefold()
    return sorted(token for token in LITERAL_STATE_TOKENS if token in folded)


def _property_api(package: DataObjectPackage) -> dict[str, dict[str, Any]]:
    return {prop.name: prop.api() for prop in package.properties}


def _entry_by_index(package: DataObjectPackage) -> dict[int, Any]:
    return {int(entry.index): entry for entry in package.entries}


def _alternative_values(
    package: DataObjectPackage,
    property_name: str,
    current_value: Any,
) -> list[dict[str, Any]]:
    current_key = _canonical_value(current_value)
    grouped: dict[str, dict[str, Any]] = {}
    for entry in package.entries:
        if property_name not in entry.values:
            continue
        value = entry.values[property_name]
        key = _canonical_value(value)
        if key == current_key:
            continue
        bucket = grouped.setdefault(key, {
            "value": value,
            "count": 0,
            "exampleEntries": [],
            "literalStateTokens": _literal_state_tokens(value),
        })
        bucket["count"] += 1
        if len(bucket["exampleEntries"]) < MAX_ROWS_PER_ALTERNATIVE:
            bucket["exampleEntries"].append({
                "entry": entry.index,
                "tag": entry.tag,
            })

    rows = sorted(
        grouped.values(),
        key=lambda row: (
            not bool(row["literalStateTokens"]),
            -int(row["count"]),
            _canonical_value(row["value"]),
        ),
    )
    return rows[:MAX_ALTERNATIVES]


def analyze_object_layout_mutation_surface(
    package: DataObjectPackage,
    layout: Mapping[str, Any],
) -> dict[str, Any]:
    """Inventory installed fields/alternatives for exact Sector 7 bench rows."""
    property_api = _property_api(package)
    entries = _entry_by_index(package)
    bench_rows = list(layout.get("sector7BenchRows", ()))
    vending_rows = list(layout.get("sector7VendingRows", ()))
    all_properties = [property_api[name] for name in sorted(property_api)]

    row_reports: list[dict[str, Any]] = []
    for bench_row in bench_rows:
        entry_index = int(bench_row.get("entry", -1))
        entry = entries.get(entry_index)
        if entry is None:
            row_reports.append({
                "entry": entry_index,
                "tag": bench_row.get("tag"),
                "error": "classified bench row does not exist in parsed package",
                "fieldCandidates": [],
            })
            continue

        same_level_vending = [
            row for row in vending_rows
            if str(row.get("levelName", "")).casefold()
            == str(bench_row.get("levelName", "")).casefold()
        ]
        vending_entries = [
            entries.get(int(row.get("entry", -1)))
            for row in same_level_vending
        ]
        vending_entries = [row for row in vending_entries if row is not None]

        candidates: list[dict[str, Any]] = []
        for name, meta in property_api.items():
            if name in IDENTITY_FIELDS:
                continue
            score, tokens = _field_score(name)
            if score <= 0:
                continue
            current = entry.values.get(name)
            alternatives = _alternative_values(package, name, current)
            vending_values = []
            seen_vending: set[str] = set()
            for vending_entry in vending_entries:
                value = vending_entry.values.get(name)
                key = _canonical_value(value)
                if key in seen_vending:
                    continue
                seen_vending.add(key)
                vending_values.append(value)

            candidates.append({
                "property": name,
                "label": meta.get("label"),
                "type": meta.get("type"),
                "typeCode": meta.get("typeCode"),
                "array": bool(meta.get("array")),
                "writerEditable": bool(meta.get("editable")),
                "nameEvidenceScore": score,
                "matchedNameTokens": tokens,
                "currentValue": current,
                "sameLevelVendingValues": vending_values,
                "differsFromEverySameLevelVendingValue": bool(
                    vending_values
                    and all(
                        _canonical_value(current) != _canonical_value(value)
                        for value in vending_values
                    )
                ),
                "alternativeValueCount": len(alternatives),
                "alternativeValues": alternatives,
                "literalStateAlternativeCount": sum(
                    bool(row["literalStateTokens"]) for row in alternatives
                ),
                "semanticMeaningValidated": False,
                "mutationAuthorized": False,
            })

        candidates.sort(key=lambda row: (
            not bool(row["writerEditable"]),
            -int(row["nameEvidenceScore"]),
            -int(row["literalStateAlternativeCount"]),
            str(row["property"]).casefold(),
        ))
        row_reports.append({
            "entry": entry.index,
            "tag": entry.tag,
            "levelName": bench_row.get("levelName"),
            "bgActorName": bench_row.get("bgActorName"),
            "pushButtonActionID": bench_row.get("pushButtonActionID"),
            "attributeList": bench_row.get("attributeList"),
            "rawValues": dict(entry.values),
            "sameLevelVendingRowCount": len(vending_entries),
            "fieldCandidateCount": len(candidates),
            "fieldCandidates": candidates,
            "error": "",
        })

    ranked_property_names: dict[str, dict[str, Any]] = {}
    for row in row_reports:
        for candidate in row.get("fieldCandidates", ()):
            name = str(candidate["property"])
            bucket = ranked_property_names.setdefault(name, {
                "property": name,
                "nameEvidenceScore": candidate["nameEvidenceScore"],
                "matchedNameTokens": candidate["matchedNameTokens"],
                "writerEditable": candidate["writerEditable"],
                "benchRowCount": 0,
                "rowsWithLiteralStateAlternatives": 0,
            })
            bucket["benchRowCount"] += 1
            if candidate["literalStateAlternativeCount"]:
                bucket["rowsWithLiteralStateAlternatives"] += 1
    ranked = sorted(ranked_property_names.values(), key=lambda row: (
        not bool(row["writerEditable"]),
        -int(row["nameEvidenceScore"]),
        -int(row["rowsWithLiteralStateAlternatives"]),
        str(row["property"]).casefold(),
    ))

    return {
        "implementationReady": False,
        "suppressionAuthorized": False,
        "asset": package.asset,
        "propertyCount": len(all_properties),
        "properties": all_properties,
        "sector7BenchRowCount": len(bench_rows),
        "benchRows": row_reports,
        "rankedPropertyCandidateCount": len(ranked),
        "rankedPropertyCandidates": ranked,
        "notes": [
            "Field ranking is based only on property-name tokens; it does not infer whether a boolean/enum/value actually hides, disables or deletes an actor.",
            "Alternative values are observed values from other installed ObjectLayout rows, not recommendations. Boolean alternatives are intentionally not labelled active/inactive because field polarity may be inverted.",
            "Literal state-looking alternatives are strings containing words such as disabled/hidden/inactive/none/off and are only reverse-engineering leads.",
            "Identity fields (UniqueIndex, NodeName, LevelName, BGActorName) are excluded from mutation ranking so changing instance identity is never suggested as a suppression mechanism.",
            "writerEditable reports only the existing conservative DataObject writer's type capability; it is not proof that editing this field is gameplay-safe.",
            "No ObjectLayout values are modified by this probe.",
        ],
    }
