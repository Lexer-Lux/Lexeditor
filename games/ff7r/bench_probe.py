"""Read-only installed-asset probe for the Chapter 3 Sector 7 blue bench.

The HP Rebalance tweak must remove exactly the bench next to the vending machine,
not every rest point. FF7R identifies Chapter 3's Sector 7 area with the `slum7`
namespace and exposes dedicated common object program IDs/classes for benches and
vending machines. This probe prefers resolved Unreal object-table evidence and,
when a split map/package exposes exact Vector property tags, reports spatial
correlation without assuming those vectors are already proven world positions.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from .archive import installed_paks
from .cooked_serial_probe import extract_serialized_name_refs
from .dataobject import FormatError
from .package_probe import parse_object_table
from .raw_asset_probe import extract_interesting_strings
from .tooling import get_file, list_pak


AREA_TERM = "slum7"
COOKED_SUFFIXES = (".umap", ".uasset", ".uexp")
OBJECT_TABLE_SUFFIXES = (".umap", ".uasset")
BENCH_TOKENS = (
    "objCmn_ProgBench",
    "EndFieldActionActorBenchBreak",
    "BenchBreak",
    "BenchType",
)
VENDING_TOKENS = (
    "objCmn_ProgVendingMachine",
    "VendingMachine",
)
BENCH_EXPORT_TOKENS = (
    "EndFieldActionActorBenchBreak",
    "BenchBreak",
)
VENDING_EXPORT_TOKENS = (
    "EndFieldActionActorVendingMachine",
    "VendingMachine",
)
LOCATION_PROPERTY_TOKENS = (
    "RelativeLocation",
    "ActorLocation",
    "Location",
)
SCAN_TOKENS = BENCH_TOKENS + VENDING_TOKENS + (
    "FieldAction",
    "ObjectLayout",
    "Location",
    "Transform",
    "PersistentLevel",
)
MAX_CANDIDATE_FILES = 1024
MAX_ERRORS = 128
MAX_SHARED_OUTER_PAIRS = 128
MAX_SPATIAL_PAIRS = 128


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def _split_suffix(path: str) -> tuple[str, str]:
    folded = path.casefold()
    for suffix in COOKED_SUFFIXES:
        if folded.endswith(suffix):
            return path[:-len(suffix)], suffix
    return path, ""


def _matches_token(strings: list[dict], tokens: Iterable[str]) -> list[dict]:
    folded = tuple(token.casefold() for token in tokens)
    return [
        row for row in strings
        if any(token in str(row.get("text", "")).casefold() for token in folded)
    ]


def _matches_export_token(exports: Iterable[dict], tokens: Iterable[str]) -> list[dict]:
    folded = tuple(str(token).casefold() for token in tokens)
    matched = []
    for row in exports:
        searchable = " ".join(
            str(row.get(field) or "")
            for field in ("className", "classPath", "objectName", "objectPath")
        ).casefold()
        if any(token in searchable for token in folded):
            matched.append(row)
    return matched


def _shared_outer_pairs(bench_exports: list[dict], vending_exports: list[dict]) -> list[dict]:
    pairs = []
    for bench in bench_exports:
        bench_outer = bench.get("outerPath")
        if not bench_outer:
            continue
        for vending in vending_exports:
            if vending.get("outerPath") != bench_outer:
                continue
            pairs.append({
                "outerPath": bench_outer,
                "benchExportIndex": bench.get("index"),
                "benchObjectName": bench.get("objectName"),
                "benchClassPath": bench.get("classPath"),
                "vendingExportIndex": vending.get("index"),
                "vendingObjectName": vending.get("objectName"),
                "vendingClassPath": vending.get("classPath"),
            })
            if len(pairs) >= MAX_SHARED_OUTER_PAIRS:
                return pairs
    return pairs


def _ref_owned_by_export(ref: dict[str, Any], owner: dict[str, Any]) -> bool:
    owner_path = str(owner.get("objectPath") or "")
    owner_name = str(owner.get("objectName") or "")
    ref_path = str(ref.get("objectPath") or "")
    ref_outer = str(ref.get("outerPath") or "")
    if owner_path and (ref_path == owner_path or ref_outer == owner_path):
        return True
    if owner_path and (ref_path.startswith(owner_path + ".") or ref_outer.startswith(owner_path + ".")):
        return True
    if owner_name:
        segments = tuple(part for part in (ref_path + "." + ref_outer).split(".") if part)
        return owner_name in segments
    return False


def _owned_vector_refs(serialized: dict[str, Any], owners: list[dict]) -> list[dict]:
    if not serialized.get("mappingTrusted"):
        return []
    rows = []
    for ref in serialized.get("refs", ()):
        if not ref.get("vectorValuePlausible"):
            continue
        matching_owners = [owner for owner in owners if _ref_owned_by_export(ref, owner)]
        if not matching_owners:
            continue
        for owner in matching_owners:
            rows.append({
                "ownerExportIndex": owner.get("index"),
                "ownerObjectName": owner.get("objectName"),
                "ownerObjectPath": owner.get("objectPath"),
                "propertyName": ref.get("name"),
                "propertyExportIndex": ref.get("exportIndex"),
                "propertyObjectName": ref.get("objectName"),
                "propertyObjectPath": ref.get("objectPath"),
                "propertyOuterPath": ref.get("outerPath"),
                "vector": dict(ref.get("vectorValue") or {}),
            })
            if len(rows) >= MAX_SPATIAL_PAIRS:
                return rows
    return rows


def pair_spatial_vectors(bench_vectors: Iterable[dict], vending_vectors: Iterable[dict]) -> list[dict]:
    """Pair decoded vectors by numeric distance without claiming world-space semantics."""
    pairs = []
    for bench in bench_vectors:
        bv = bench.get("vector") or {}
        try:
            bx, by, bz = float(bv["x"]), float(bv["y"]), float(bv["z"])
        except (KeyError, TypeError, ValueError):
            continue
        for vending in vending_vectors:
            vv = vending.get("vector") or {}
            try:
                vx, vy, vz = float(vv["x"]), float(vv["y"]), float(vv["z"])
            except (KeyError, TypeError, ValueError):
                continue
            values = (bx, by, bz, vx, vy, vz)
            if not all(math.isfinite(value) for value in values):
                continue
            distance = math.sqrt((bx - vx) ** 2 + (by - vy) ** 2 + (bz - vz) ** 2)
            pairs.append({
                "bench": dict(bench),
                "vending": dict(vending),
                "samePropertyName": str(bench.get("propertyName")) == str(vending.get("propertyName")),
                "numericDistance": distance,
                "coordinateSpaceValidated": False,
                "worldSpaceAdjacencyValidated": False,
            })
    pairs.sort(key=lambda row: (
        float(row["numericDistance"]),
        str(row["bench"].get("ownerObjectName") or "").casefold(),
        str(row["vending"].get("ownerObjectName") or "").casefold(),
    ))
    return pairs[:MAX_SPATIAL_PAIRS]


def rank_bench_candidates(files: Iterable[dict]) -> list[dict]:
    """Rank already-scanned files; exact object/serialized evidence dominates strings."""
    ranked = []
    for row in files:
        strings = list(row.get("interestingStrings", []))
        bench = _matches_token(strings, BENCH_TOKENS)
        vending = _matches_token(strings, VENDING_TOKENS)
        bench_exports = list(row.get("benchExports", []))
        vending_exports = list(row.get("vendingExports", []))
        shared_outer_pairs = list(row.get("sharedOuterPairs", []))
        spatial_pairs = list(row.get("serializedSpatialPairs", []))
        if not bench and not vending and not bench_exports and not vending_exports:
            continue

        score = (100 if bench and vending else 0) + len(bench) * 10 + len(vending) * 10
        score += len(bench_exports) * 250 + len(vending_exports) * 250
        if bench_exports and vending_exports:
            score += 1000
        score += len(shared_outer_pairs) * 2000
        # Decoded vectors tied to resolved owners are stronger localization
        # evidence, but their coordinate space remains explicitly unvalidated.
        if spatial_pairs:
            score += 3000
            if spatial_pairs[0].get("samePropertyName"):
                score += 500
        path = str(row.get("path", ""))
        if path.casefold().endswith(".umap"):
            score += 25
        ranked.append({
            **row,
            "benchEvidence": bench,
            "vendingEvidence": vending,
            "containsBenchAndVending": bool(bench and vending),
            "containsBenchAndVendingExports": bool(bench_exports and vending_exports),
            "containsSerializedSpatialPair": bool(spatial_pairs),
            "nearestSerializedSpatialPair": spatial_pairs[0] if spatial_pairs else None,
            "score": score,
        })
    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("path", "")).casefold()),
    )


def _object_table_evidence(data: bytes, path: str) -> dict:
    if not path.casefold().endswith(OBJECT_TABLE_SUFFIXES):
        return {
            "objectTable": None,
            "benchExports": [],
            "vendingExports": [],
            "sharedOuterPairs": [],
            "objectTableError": None,
        }
    try:
        table = parse_object_table(data, label=path)
    except FormatError as error:
        return {
            "objectTable": None,
            "benchExports": [],
            "vendingExports": [],
            "sharedOuterPairs": [],
            "objectTableError": str(error),
        }
    exports = table.export_rows()
    bench_exports = _matches_export_token(exports, BENCH_EXPORT_TOKENS)
    vending_exports = _matches_export_token(exports, VENDING_EXPORT_TOKENS)
    return {
        "objectTable": table.summary(),
        "benchExports": bench_exports,
        "vendingExports": vending_exports,
        "sharedOuterPairs": _shared_outer_pairs(bench_exports, vending_exports),
        "objectTableError": None,
    }


def probe_chapter3_bench(game_root: Path) -> dict:
    game_root = Path(game_root).resolve()
    selected: dict[str, dict] = {}
    errors: list[str] = []
    pak_count = 0
    for pak in installed_paks(game_root):
        pak_count += 1
        relative_pak = pak.resolve().relative_to(game_root).as_posix()
        try:
            entries = list_pak(pak)
        except Exception as error:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{relative_pak}: {error}")
            continue
        for raw in entries:
            path = _normalize(raw)
            folded = path.casefold()
            if AREA_TERM not in folded or not folded.endswith(COOKED_SUFFIXES):
                continue
            selected[folded] = {"pak": relative_pak, "path": path}

    scanned = []
    truncated = len(selected) > MAX_CANDIDATE_FILES
    for source in sorted(selected.values(), key=lambda row: row["path"].casefold())[:MAX_CANDIDATE_FILES]:
        pak = game_root / source["pak"]
        try:
            data = get_file(pak, source["path"])
        except Exception as error:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{source['pak']} :: {source['path']}: {error}")
            continue
        strings = extract_interesting_strings(data, tokens=SCAN_TOKENS)
        object_evidence = _object_table_evidence(data, source["path"])
        if (
            not strings
            and not object_evidence["benchExports"]
            and not object_evidence["vendingExports"]
        ):
            continue

        serialized: dict[str, Any] = {}
        bench_vectors: list[dict] = []
        vending_vectors: list[dict] = []
        spatial_pairs: list[dict] = []
        base, suffix = _split_suffix(source["path"])
        if (
            suffix in (".umap", ".uasset")
            and (object_evidence["benchExports"] or object_evidence["vendingExports"])
        ):
            uexp_source = selected.get((base + ".uexp").casefold())
            if uexp_source:
                try:
                    uexp = get_file(game_root / uexp_source["pak"], uexp_source["path"])
                    serialized = extract_serialized_name_refs(
                        data,
                        uexp,
                        tokens=LOCATION_PROPERTY_TOKENS,
                        label=source["path"],
                    )
                    bench_vectors = _owned_vector_refs(
                        serialized, object_evidence["benchExports"]
                    )
                    vending_vectors = _owned_vector_refs(
                        serialized, object_evidence["vendingExports"]
                    )
                    spatial_pairs = pair_spatial_vectors(bench_vectors, vending_vectors)
                except Exception as error:
                    if len(errors) < MAX_ERRORS:
                        errors.append(
                            f"{source['pak']} :: {source['path']}: serialized location probe failed: {error}"
                        )

        scanned.append({
            "pak": source["pak"],
            "path": source["path"],
            "size": len(data),
            "interestingStrings": strings,
            **object_evidence,
            "serializedLocationEvidence": serialized,
            "benchVectorEvidence": bench_vectors,
            "vendingVectorEvidence": vending_vectors,
            "serializedSpatialPairs": spatial_pairs,
        })

    ranked = rank_bench_candidates(scanned)
    paired = [row for row in ranked if row["containsBenchAndVending"]]
    object_paired = [row for row in ranked if row["containsBenchAndVendingExports"]]
    spatial = [row for row in ranked if row["containsSerializedSpatialPair"]]
    return {
        "area": AREA_TERM,
        "pakCount": pak_count,
        "matchingCookedFiles": len(selected),
        "scannedCookedFiles": min(len(selected), MAX_CANDIDATE_FILES),
        "truncated": truncated,
        "spatialCandidates": spatial,
        "objectPairedCandidates": object_paired,
        "pairedCandidates": paired,
        "allEvidenceCandidates": ranked,
        "scanErrors": errors,
        "knownContracts": {
            "benchActorClass": "EndFieldActionActorBenchBreak",
            "benchProgramId": "objCmn_ProgBench",
            "vendingActorClass": "EndFieldActionActorVendingMachine",
            "vendingProgramId": "objCmn_ProgVendingMachine",
            "sector7Namespace": AREA_TERM,
        },
        "notes": [
            "Resolved bench/vending exports sharing an authored outer are stronger evidence than printable identifiers in the same file.",
            "When an exact old-format Vector StructProperty is serialized under a resolved bench/vending owner, its three float32 components are reported and numeric pair distances are ranked.",
            "A small numeric Vector distance does not by itself prove world-space adjacency: actor/component ownership, RelativeLocation parent space, level transforms and the exact vending-side coordinate source must agree before suppression is authorized.",
            "The object/serialized probes are read-only and fail closed on unsupported cooked package layouts.",
            "This probe does not remove anything; the exact authored actor/object identity must be established before suppression.",
            "A global objCmn_ProgBench replacement is explicitly unsafe because it would affect unrelated benches.",
        ],
    }
