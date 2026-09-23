"""Fail-closed ownership decisions for FF7R No More Cheats research.

`cheat_probe.scan_installed_menu_candidates` intentionally returns evidence, not
edits.  This module turns that evidence into an explicit structural-removal
verdict so a ranked/string match can never be mistaken for an authoritative
mutation target.
"""

from __future__ import annotations

from typing import Any


# DataObjectPackage.delete_array_element supports only these fixed-width types.
# Keep the contract local so the read-only decision layer does not need a live
# package object or import writer implementation details at runtime.
SUPPORTED_ARRAY_DELETE_TYPE_CODES = frozenset({1, 2, 3, 4, 7, 9, 11})
DEFAULT_ROW_CANDIDATE_CAP = 128


def _exact_structural_candidates(target: dict[str, Any]) -> list[dict[str, Any]]:
    """Return declared-array selectors backed by an exact installed text ID."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, int]] = set()

    for row in target.get("rowCandidates", ()):
        asset = str(row.get("asset", ""))
        try:
            entry_index = int(row.get("entryIndex", -1))
        except (TypeError, ValueError):
            continue
        record = str(row.get("record", ""))
        matches = list(row.get("matches", ()))
        controls = list(row.get("controlFields", ()))

        for array_candidate in row.get("arrayElementCandidates", ()):
            property_name = str(array_candidate.get("property", ""))
            try:
                array_index = int(array_candidate.get("index", -1))
            except (TypeError, ValueError):
                continue
            if not asset or entry_index < 0 or not property_name or array_index < 0:
                continue

            match_path = f"{property_name}[{array_index}]"
            exact_matches = [
                match
                for match in matches
                if match.get("match") == "text-id"
                and str(match.get("property", "")) == match_path
            ]
            if not exact_matches:
                continue

            identity = (asset, entry_index, property_name, array_index)
            if identity in seen:
                continue
            seen.add(identity)

            type_code = array_candidate.get("typeCode")
            candidates.append({
                "asset": asset,
                "entryIndex": entry_index,
                "record": record,
                "property": property_name,
                "index": array_index,
                "typeCode": type_code,
                "matchedTextIds": sorted({str(match.get("value", "")) for match in exact_matches}),
                "fixedWidthDeleteSupported": type_code in SUPPORTED_ARRAY_DELETE_TYPE_CODES,
                "menuControlEvidence": bool(controls),
                "controlFields": [str(field.get("name", "")) for field in controls if field.get("name")],
            })

    return candidates


def assess_target_removal(
    target: dict[str, Any],
    *,
    scan_errors: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """Classify whether probe evidence identifies one executable removal selector.

    This is deliberately stricter than evidence ranking.  Any incomplete scan,
    truncated row set, unsupported array type, missing menu/control context, or
    multiple exact structural owners blocks mutation.
    """
    reasons: list[str] = []
    candidates = _exact_structural_candidates(target)
    rows = list(target.get("rowCandidates", ()))
    try:
        total_rows = int(target.get("rowCandidateCount", len(rows)))
    except (TypeError, ValueError):
        total_rows = len(rows)
    explicit_count = "rowCandidateCount" in target
    truncated = bool(
        target.get("rowCandidatesTruncated", False)
        or total_rows > len(rows)
        or (not explicit_count and len(rows) >= DEFAULT_ROW_CANDIDATE_CAP)
    )

    if scan_errors:
        reasons.append("scan-errors")
    if truncated:
        reasons.append("row-candidates-truncated")
    if not target.get("textIds"):
        reasons.append("no-installed-text-id")
    if not candidates:
        reasons.append("no-exact-structural-match")

    installed_text_ids = {str(value) for value in target.get("textIds", ()) if str(value)}
    matched_text_ids = {
        text_id
        for candidate in candidates
        for text_id in candidate.get("matchedTextIds", ())
        if text_id
    }
    if installed_text_ids and matched_text_ids != installed_text_ids:
        reasons.append("unresolved-installed-text-ids")

    unsupported = [candidate for candidate in candidates if not candidate["fixedWidthDeleteSupported"]]
    if unsupported:
        reasons.append("unsupported-structural-type")

    missing_context = [candidate for candidate in candidates if not candidate["menuControlEvidence"]]
    if missing_context:
        reasons.append("missing-menu-control-evidence")

    executable = [
        candidate
        for candidate in candidates
        if candidate["fixedWidthDeleteSupported"] and candidate["menuControlEvidence"]
    ]
    if len(candidates) > 1:
        reasons.append("ambiguous-structural-owner")

    actionable = (
        len(candidates) == 1
        and len(executable) == 1
        and not scan_errors
        and not truncated
        and bool(installed_text_ids)
        and matched_text_ids == installed_text_ids
    )
    if actionable:
        reasons.append("unique-exact-structural-owner")

    return {
        "key": str(target.get("key", "")),
        "label": str(target.get("label", "")),
        "status": "ready" if actionable else "blocked",
        "actionable": actionable,
        "reasonCodes": reasons,
        "selector": executable[0] if actionable else None,
        "structuralCandidates": candidates,
    }


def assess_menu_candidate_removals(report: dict[str, Any]) -> dict[str, Any]:
    """Assess every No More Cheats target in a probe report without editing it."""
    scan_errors = tuple(str(error) for error in report.get("scanErrors", ()))
    targets = [
        assess_target_removal(target, scan_errors=scan_errors)
        for target in report.get("targets", ())
    ]
    return {
        "allTargetsActionable": bool(targets) and all(target["actionable"] for target in targets),
        "targets": targets,
        "scanErrors": list(scan_errors),
        "notes": [
            "Actionable means one exact installed text-ID reference resolves to one declared fixed-width array element with menu/control evidence.",
            "Any scan error or truncated candidate set blocks actionability because uniqueness would be unproved.",
            "This assessment is read-only and does not delete, suppress, or rewrite game data.",
        ],
    }
