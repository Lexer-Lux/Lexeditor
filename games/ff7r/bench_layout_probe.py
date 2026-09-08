"""Read-only ObjectLayout correlation for the FF7R Chapter 3 bench (#427).

The cooked-map bench probe can resolve bench/vending actor exports and, when the
package layout permits it, compare serialized Vector values. Remake's public
`FEndDataTableObjectLayout` contract provides an independent identity surface:
rows carry `LevelName` and `BGActorName`. This module correlates those installed
DataObject rows with the map probe without authorizing actor deletion.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .archive import extract_pair
from .bench_probe import probe_chapter3_bench
from .dataobject import DataObjectPackage


OBJECT_LAYOUT_TABLE = "objectlayout"
AREA_TERM = "slum7"
MAX_ROWS = 512
BENCH_TERMS = ("objcmn_progbench", "benchbreak", "bench")
VENDING_TERMS = ("objcmn_progvendingmachine", "vendingmachine", "vending")


def _basename(asset: str) -> str:
    return PurePosixPath(str(asset)).name.casefold()


def _find_object_layout(index: dict[str, Any]) -> dict[str, Any] | None:
    for row in index.get("assets", ()):
        if row.get("synthetic"):
            continue
        if _basename(str(row.get("asset", ""))) == OBJECT_LAYOUT_TABLE:
            return dict(row)
    return None


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_strings(child)


def _contains_term(values: Iterable[str], terms: Iterable[str]) -> bool:
    haystack = " ".join(str(value).casefold().replace("_", "") for value in values)
    return any(str(term).casefold().replace("_", "") in haystack for term in terms)


def classify_object_layout_rows(package: DataObjectPackage) -> dict[str, Any]:
    """Classify installed ObjectLayout rows by literal bench/vending/Sector 7 evidence."""
    properties = {prop.name for prop in package.properties}
    expected = {
        "UniqueIndex", "Priority", "NodeName", "LevelName", "BGActorName",
        "PushButtonActionID", "AttributeList_Array",
    }
    available = sorted(properties & expected)
    rows: list[dict[str, Any]] = []
    for entry in package.entries[:MAX_ROWS]:
        evidence = [entry.tag, *_walk_strings(entry.values)]
        bench = _contains_term(evidence, BENCH_TERMS)
        vending = _contains_term(evidence, VENDING_TERMS)
        if not bench and not vending:
            continue
        level_name = str(entry.values.get("LevelName", ""))
        node_name = str(entry.values.get("NodeName", ""))
        bg_actor = str(entry.values.get("BGActorName", ""))
        area_evidence = _contains_term((entry.tag, level_name, node_name), (AREA_TERM,))
        rows.append({
            "entry": entry.index,
            "tag": entry.tag,
            "kind": "bench" if bench and not vending else "vending" if vending and not bench else "ambiguous",
            "benchEvidence": bench,
            "vendingEvidence": vending,
            "sector7Evidence": area_evidence,
            "uniqueIndex": entry.values.get("UniqueIndex"),
            "priority": entry.values.get("Priority"),
            "nodeName": node_name,
            "levelName": level_name,
            "bgActorName": bg_actor,
            "pushButtonActionID": str(entry.values.get("PushButtonActionID", "")),
            "attributeList": list(entry.values.get("AttributeList_Array", ()))
            if isinstance(entry.values.get("AttributeList_Array"), list) else [],
        })
    return {
        "asset": package.asset,
        "properties": available,
        "rows": rows,
        "sector7BenchRows": [row for row in rows if row["benchEvidence"] and row["sector7Evidence"]],
        "sector7VendingRows": [row for row in rows if row["vendingEvidence"] and row["sector7Evidence"]],
        "truncated": len(package.entries) > MAX_ROWS,
    }


def _level_matches_path(level_name: str, path: str) -> bool:
    """Require a path-component/stem boundary; never use compact substring matches."""
    level = str(level_name).strip().casefold()
    if not level:
        return False
    normalized = str(path).replace("\\", "/").casefold()
    pure = PurePosixPath(normalized)
    stem = pure.stem
    parts = tuple(part.casefold() for part in pure.parts)
    return bool(
        stem == level
        or stem.startswith(level + "_")
        or level in parts
    )


def _actor_matches_export(actor_name: str, export: dict[str, Any]) -> bool:
    actor = str(actor_name).strip().casefold()
    if not actor:
        return False
    candidates = {
        str(export.get("objectName") or "").casefold(),
        str(export.get("objectPath") or "").split(".")[-1].casefold(),
    }
    return actor in candidates


def correlate_object_layout_rows(
    layout: dict[str, Any],
    bench_report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Require exact BGActorName plus compatible LevelName before correlation."""
    bench_rows = list(layout.get("sector7BenchRows", ()))
    vending_rows = list(layout.get("sector7VendingRows", ()))
    correlations: list[dict[str, Any]] = []
    for candidate in bench_report.get("allEvidenceCandidates", ()):
        path = str(candidate.get("path", ""))
        bench_exports = list(candidate.get("benchExports", ()))
        vending_exports = list(candidate.get("vendingExports", ()))
        for bench_row in bench_rows:
            if not _level_matches_path(str(bench_row.get("levelName", "")), path):
                continue
            matching_benches = [
                export for export in bench_exports
                if _actor_matches_export(str(bench_row.get("bgActorName", "")), export)
            ]
            if not matching_benches:
                continue
            for vending_row in vending_rows:
                if str(vending_row.get("levelName", "")).casefold() != str(bench_row.get("levelName", "")).casefold():
                    continue
                matching_vending = [
                    export for export in vending_exports
                    if _actor_matches_export(str(vending_row.get("bgActorName", "")), export)
                ]
                if not matching_vending:
                    continue
                for bench_export in matching_benches:
                    for vending_export in matching_vending:
                        spatial = [
                            row for row in candidate.get("serializedSpatialPairs", ())
                            if int((row.get("bench") or {}).get("ownerExportIndex", -1)) == int(bench_export.get("index", -2))
                            and int((row.get("vending") or {}).get("ownerExportIndex", -1)) == int(vending_export.get("index", -2))
                        ]
                        correlations.append({
                            "path": path,
                            "levelName": bench_row.get("levelName"),
                            "benchLayoutTag": bench_row.get("tag"),
                            "benchBGActorName": bench_row.get("bgActorName"),
                            "benchExportIndex": bench_export.get("index"),
                            "benchObjectName": bench_export.get("objectName"),
                            "vendingLayoutTag": vending_row.get("tag"),
                            "vendingBGActorName": vending_row.get("bgActorName"),
                            "vendingExportIndex": vending_export.get("index"),
                            "vendingObjectName": vending_export.get("objectName"),
                            "exactActorIdentityCorrelation": True,
                            "sameObjectLayoutLevel": True,
                            "serializedSpatialPair": spatial[0] if spatial else None,
                            "worldSpaceAdjacencyValidated": False,
                            "suppressionAuthorized": False,
                        })
    correlations.sort(key=lambda row: (
        row["serializedSpatialPair"] is None,
        float((row["serializedSpatialPair"] or {}).get("numericDistance", float("inf"))),
        str(row["path"]).casefold(),
        str(row["benchObjectName"]).casefold(),
    ))
    return correlations


def probe_chapter3_bench_with_layout(
    game_root: Path,
    data_root: Path,
    index: dict[str, Any],
) -> dict[str, Any]:
    """Combine map/object evidence with installed ObjectLayout identity evidence."""
    bench_report = probe_chapter3_bench(game_root)
    row = _find_object_layout(index)
    if row is None:
        return {
            **bench_report,
            "objectLayoutResearch": {
                "asset": "",
                "properties": [],
                "rows": [],
                "sector7BenchRows": [],
                "sector7VendingRows": [],
                "truncated": False,
                "error": "ObjectLayout DataObject was not found in the installed catalog",
            },
            "objectLayoutCorrelations": [],
            "objectLayoutCorrelationCount": 0,
        }
    try:
        uasset, uexp = extract_pair(game_root, data_root, index, row["asset"])
        package = DataObjectPackage(uasset, uexp, asset=row["asset"])
        layout = classify_object_layout_rows(package)
        layout["error"] = ""
    except Exception as error:
        layout = {
            "asset": str(row.get("asset", "")),
            "properties": [],
            "rows": [],
            "sector7BenchRows": [],
            "sector7VendingRows": [],
            "truncated": False,
            "error": str(error),
        }
    correlations = correlate_object_layout_rows(layout, bench_report)
    notes = list(bench_report.get("notes", ()))
    notes.extend([
        "ObjectLayout LevelName + BGActorName provides an independent installed identity bridge from a Sector 7 layout row to a specific cooked actor export.",
        "A layout correlation is accepted only when BGActorName exactly matches the resolved export object and LevelName matches a package path component/stem boundary; fuzzy actor/level matching is not used.",
        "Even a unique ObjectLayout + export + Vector correlation remains read-only evidence. Suppression requires a proven per-instance mutation path that removes both visible bench and interaction/navigation behavior while preserving the vending actor.",
    ])
    return {
        **bench_report,
        "objectLayoutResearch": layout,
        "objectLayoutCorrelations": correlations,
        "objectLayoutCorrelationCount": len(correlations),
        "notes": notes,
    }
