"""Read-only coordinate-space evidence for the Chapter 3 bench (#427).

The existing bench probe can decode Vector-valued ``RelativeLocation`` tags and
rank bench/vending pairs by raw numeric distance. That is not enough: two
relative locations are comparable only when their component ownership and
coordinate parent are known.

This stage decodes old-format UE4 ObjectProperty values as FPackageIndex only
when the existing serialized-property probe has already proved the exact tag
layout. It then requires:

* an exact ``RootComponent`` ObjectProperty on the actor export;
* an exact Vector ``RelativeLocation`` on that root-component export; and
* an exact ``AttachParent`` ObjectProperty on both roots before declaring the
  two vectors to share a coordinate parent.

Absence of AttachParent is deliberately *not* interpreted as null/default.
Even a common parent only proves a common relative coordinate frame; it does not
prove world-space distance, physical adjacency, or authorize bench suppression.
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
from typing import Any, Iterable, Mapping, Sequence

from .archive import installed_paks
from .bench_probe import AREA_TERM, probe_chapter3_bench
from .cooked_serial_probe import extract_serialized_name_refs
from .package_probe import PackageObjectTable, parse_object_table
from .tooling import get_file, list_pak


COORDINATE_TOKENS = ("RootComponent", "AttachParent", "RelativeLocation")
COOKED_SUFFIXES = (".umap", ".uasset", ".uexp")
MAX_ERRORS = 128
MAX_PAIR_RESULTS = 256


def decode_object_property_ref(
    ref: Mapping[str, Any],
    table: PackageObjectTable,
) -> dict[str, Any]:
    """Decode one exact ObjectProperty value as a bounded FPackageIndex.

    Generic 4-byte-looking payloads are rejected unless the upstream property
    parser proved the full old-format tag layout and exact ObjectProperty type.
    """
    result = {
        "valid": False,
        "packageIndex": None,
        "targetKind": None,
        "targetPath": None,
        "targetExportIndex": None,
        "targetImportIndex": None,
        "reason": "not-an-exact-object-property",
    }
    if not isinstance(ref, Mapping):
        return result
    if ref.get("propertyType") != "ObjectProperty":
        return result
    if not ref.get("propertyTagLayoutPlausible"):
        return result
    if ref.get("declaredValueSize") != 4:
        return {**result, "reason": "object-property-size-is-not-four"}
    raw_hex = ref.get("valueHex")
    if not isinstance(raw_hex, str):
        return {**result, "reason": "object-property-value-missing"}
    try:
        raw = bytes.fromhex(raw_hex)
    except ValueError:
        return {**result, "reason": "object-property-value-is-not-hex"}
    if len(raw) != 4:
        return {**result, "reason": "object-property-value-length-is-not-four"}

    package_index = struct.unpack("<i", raw)[0]
    if package_index == 0:
        return {
            **result,
            "valid": True,
            "packageIndex": 0,
            "targetKind": "null",
            "reason": "explicit-null-package-index",
        }

    target_path = table.resolve_path(package_index)
    if target_path is None:
        return {
            **result,
            "packageIndex": package_index,
            "reason": "package-index-does-not-resolve",
        }
    if package_index > 0:
        target_export = package_index - 1
        if not 0 <= target_export < len(table.exports):
            return {
                **result,
                "packageIndex": package_index,
                "reason": "export-package-index-out-of-range",
            }
        return {
            **result,
            "valid": True,
            "packageIndex": package_index,
            "targetKind": "export",
            "targetPath": target_path,
            "targetExportIndex": target_export,
            "reason": "resolved-export-package-index",
        }

    target_import = -package_index - 1
    if not 0 <= target_import < len(table.imports):
        return {
            **result,
            "packageIndex": package_index,
            "reason": "import-package-index-out-of-range",
        }
    return {
        **result,
        "valid": True,
        "packageIndex": package_index,
        "targetKind": "import",
        "targetPath": target_path,
        "targetImportIndex": target_import,
        "reason": "resolved-import-package-index",
    }


def _exact_refs(
    refs: Iterable[Mapping[str, Any]],
    *,
    export_index: int,
    name: str,
) -> list[Mapping[str, Any]]:
    folded = name.casefold()
    return [
        ref
        for ref in refs
        if int(ref.get("exportIndex", -1)) == int(export_index)
        and str(ref.get("name", "")).casefold() == folded
    ]


def _unique_decoded_object_ref(
    refs: Iterable[Mapping[str, Any]],
    table: PackageObjectTable,
    *,
    export_index: int,
    name: str,
) -> dict[str, Any]:
    matches = _exact_refs(refs, export_index=export_index, name=name)
    decoded = [decode_object_property_ref(ref, table) for ref in matches]
    valid = [row for row in decoded if row["valid"]]
    if not matches:
        status = "not-serialized"
    elif len(matches) != 1:
        status = "ambiguous-property-tag"
    elif len(valid) != 1:
        status = "invalid-property-value"
    else:
        status = "unique-decoded-property"
    return {
        "status": status,
        "matchCount": len(matches),
        "validDecodedCount": len(valid),
        "decoded": decoded,
        "unique": valid[0] if status == "unique-decoded-property" else None,
    }


def _unique_root_location(
    refs: Iterable[Mapping[str, Any]],
    *,
    root_export_index: int,
) -> dict[str, Any]:
    matches = _exact_refs(
        refs,
        export_index=root_export_index,
        name="RelativeLocation",
    )
    valid = [
        ref for ref in matches
        if ref.get("propertyType") == "StructProperty"
        and ref.get("propertyTagLayoutPlausible")
        and str((ref.get("typeMetadata") or {}).get("structName", "")).casefold() == "vector"
        and ref.get("declaredValueSize") == 12
        and ref.get("vectorValuePlausible")
        and isinstance(ref.get("vectorValue"), Mapping)
    ]
    if not matches:
        status = "not-serialized"
    elif len(matches) != 1:
        status = "ambiguous-property-tag"
    elif len(valid) != 1:
        status = "invalid-vector-value"
    else:
        status = "unique-decoded-vector"
    value = dict(valid[0]["vectorValue"]) if status == "unique-decoded-vector" else None
    return {
        "status": status,
        "matchCount": len(matches),
        "validDecodedCount": len(valid),
        "vector": value,
    }


def analyze_actor_root_coordinate_space(
    table: PackageObjectTable,
    refs: Iterable[Mapping[str, Any]],
    actor_export_index: int,
) -> dict[str, Any]:
    """Resolve one actor -> RootComponent -> RelativeLocation/AttachParent chain."""
    rows = tuple(refs)
    exports = table.export_rows()
    actor_index = int(actor_export_index)
    if not 0 <= actor_index < len(exports):
        return {
            "resolved": False,
            "actorExportIndex": actor_index,
            "reason": "actor-export-index-out-of-range",
        }

    root = _unique_decoded_object_ref(
        rows, table, export_index=actor_index, name="RootComponent"
    )
    root_value = root.get("unique")
    if not root_value or root_value.get("targetKind") != "export":
        return {
            "resolved": False,
            "actorExportIndex": actor_index,
            "actorObjectName": exports[actor_index].get("objectName"),
            "actorObjectPath": exports[actor_index].get("objectPath"),
            "rootComponent": root,
            "reason": "unique-export-root-component-unresolved",
        }

    root_index = int(root_value["targetExportIndex"])
    root_row = exports[root_index]
    location = _unique_root_location(rows, root_export_index=root_index)
    attach_parent = _unique_decoded_object_ref(
        rows, table, export_index=root_index, name="AttachParent"
    )
    return {
        "resolved": True,
        "actorExportIndex": actor_index,
        "actorObjectName": exports[actor_index].get("objectName"),
        "actorObjectPath": exports[actor_index].get("objectPath"),
        "rootComponent": root,
        "rootComponentExportIndex": root_index,
        "rootComponentObjectName": root_row.get("objectName"),
        "rootComponentObjectPath": root_row.get("objectPath"),
        "relativeLocation": location,
        "attachParent": attach_parent,
        "explicitAttachParentResolved": attach_parent.get("status") == "unique-decoded-property",
        "reason": "root-component-resolved",
    }


def _finite_vector(value: Mapping[str, Any] | None) -> tuple[float, float, float] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        result = (float(value["x"]), float(value["y"]), float(value["z"]))
    except (KeyError, TypeError, ValueError):
        return None
    return result if all(math.isfinite(component) for component in result) else None


def compare_actor_root_coordinate_spaces(
    table: PackageObjectTable,
    refs: Iterable[Mapping[str, Any]],
    bench_actor_export_index: int,
    vending_actor_export_index: int,
) -> dict[str, Any]:
    """Test whether exact bench/vending root locations share an explicit parent."""
    rows = tuple(refs)
    bench = analyze_actor_root_coordinate_space(
        table, rows, bench_actor_export_index
    )
    vending = analyze_actor_root_coordinate_space(
        table, rows, vending_actor_export_index
    )

    bench_parent = (bench.get("attachParent") or {}).get("unique")
    vending_parent = (vending.get("attachParent") or {}).get("unique")
    both_explicit = bool(
        bench.get("explicitAttachParentResolved")
        and vending.get("explicitAttachParentResolved")
        and bench_parent
        and vending_parent
    )
    same_parent = bool(
        both_explicit
        and bench_parent.get("packageIndex") == vending_parent.get("packageIndex")
    )
    bench_vector = _finite_vector(
        (bench.get("relativeLocation") or {}).get("vector")
    )
    vending_vector = _finite_vector(
        (vending.get("relativeLocation") or {}).get("vector")
    )
    relative_distance = None
    if same_parent and bench_vector is not None and vending_vector is not None:
        relative_distance = math.sqrt(sum(
            (left - right) ** 2
            for left, right in zip(bench_vector, vending_vector)
        ))

    if not bench.get("resolved") or not vending.get("resolved"):
        status = "actor-root-unresolved"
    elif bench_vector is None or vending_vector is None:
        status = "root-relative-location-unresolved"
    elif not both_explicit:
        status = "attach-parent-not-explicitly-serialized"
    elif not same_parent:
        status = "different-explicit-attach-parents"
    else:
        status = "shared-explicit-relative-coordinate-parent"

    return {
        "implementationReady": False,
        "status": status,
        "bench": bench,
        "vending": vending,
        "bothAttachParentsExplicitlyDecoded": both_explicit,
        "sharedExplicitAttachParent": same_parent,
        "sharedAttachParentPackageIndex": (
            bench_parent.get("packageIndex") if same_parent else None
        ),
        "sharedAttachParentPath": (
            bench_parent.get("targetPath") if same_parent else None
        ),
        "relativeCoordinateDistanceValidated": relative_distance is not None,
        "relativeCoordinateDistance": relative_distance,
        "worldSpaceDistanceValidated": False,
        "worldSpaceAdjacencyValidated": False,
        "suppressionAuthorized": False,
        "notes": [
            "RootComponent and AttachParent are accepted only from exact, layout-proven four-byte ObjectProperty tags.",
            "RelativeLocation is accepted only from an exact 12-byte Vector StructProperty serialized on the resolved RootComponent export itself.",
            "Missing AttachParent is unknown, not null: delta/default serialization could omit it, so absence never proves a shared coordinate frame.",
            "Equal explicitly decoded AttachParent FPackageIndex values prove a shared relative coordinate parent within this package. Explicit null (index 0) also counts as the same serialized parent state.",
            "A shared parent makes the two raw RelativeLocation vectors comparable in one local frame, but parent transform/scale and gameplay geometry still prevent calling the numeric distance a proven world-space adjacency measurement.",
            "No cooked bytes are modified by this probe.",
        ],
    }


def correlate_layout_with_coordinate_evidence(
    layout_correlations: Sequence[Mapping[str, Any]],
    coordinate_pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join exact ObjectLayout actor identity to coordinate-parent evidence."""
    by_key: dict[tuple[str, int, int], list[Mapping[str, Any]]] = {}
    for row in coordinate_pairs:
        key = (
            str(row.get("path", "")).casefold(),
            int(row.get("benchExportIndex", -1)),
            int(row.get("vendingExportIndex", -1)),
        )
        by_key.setdefault(key, []).append(row)

    joined = []
    for raw in layout_correlations:
        row = dict(raw)
        key = (
            str(row.get("path", "")).casefold(),
            int(row.get("benchExportIndex", -1)),
            int(row.get("vendingExportIndex", -1)),
        )
        matches = by_key.get(key, [])
        evidence = matches[0].get("coordinateSpace") if len(matches) == 1 else None
        row.update({
            "coordinateEvidenceMatchCount": len(matches),
            "coordinateSpaceEvidence": evidence,
            "relativeCoordinateDistanceValidated": bool(
                evidence and evidence.get("relativeCoordinateDistanceValidated")
            ),
            "relativeCoordinateDistance": (
                evidence.get("relativeCoordinateDistance") if evidence else None
            ),
            # Identity + coordinate-space correlation still does not authorize
            # mutation or turn a local-frame distance into world-space proof.
            "worldSpaceAdjacencyValidated": False,
            "suppressionAuthorized": False,
        })
        joined.append(row)
    return joined


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def _source_map(game_root: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    selected: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for pak in installed_paks(game_root):
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
    return selected, errors


def _split_package_path(path: str) -> tuple[str, str]:
    folded = path.casefold()
    for suffix in COOKED_SUFFIXES:
        if folded.endswith(suffix):
            return path[:-len(suffix)], suffix
    return path, ""


def probe_chapter3_bench_coordinate_space(game_root: Path) -> dict[str, Any]:
    """Run root/parent coordinate analysis for installed bench-vending actor pairs."""
    root = Path(game_root).resolve()
    bench_report = probe_chapter3_bench(root)
    selected, errors = _source_map(root)
    pair_rows: list[dict[str, Any]] = []

    for candidate in bench_report.get("objectPairedCandidates", ()):
        path = str(candidate.get("path", ""))
        base, suffix = _split_package_path(path)
        if suffix not in (".umap", ".uasset"):
            continue
        source = selected.get(path.casefold())
        companion = selected.get((base + ".uexp").casefold())
        if source is None or companion is None:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{path}: matching .uexp source was not found")
            continue
        try:
            uasset = get_file(root / source["pak"], source["path"])
            uexp = get_file(root / companion["pak"], companion["path"])
            table = parse_object_table(uasset, label=path)
            serialized = extract_serialized_name_refs(
                uasset,
                uexp,
                tokens=COORDINATE_TOKENS,
                label=path,
            )
        except Exception as error:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{path}: coordinate-space probe failed: {error}")
            continue
        if not serialized.get("mappingTrusted"):
            if len(errors) < MAX_ERRORS:
                errors.append(
                    f"{path}: serialized mapping not trusted: "
                    f"{serialized.get('mappingReason', 'unknown')}"
                )
            continue

        refs = serialized.get("refs", ())
        for bench_export in candidate.get("benchExports", ()):
            for vending_export in candidate.get("vendingExports", ()):
                if len(pair_rows) >= MAX_PAIR_RESULTS:
                    break
                coordinate = compare_actor_root_coordinate_spaces(
                    table,
                    refs,
                    int(bench_export.get("index", -1)),
                    int(vending_export.get("index", -1)),
                )
                pair_rows.append({
                    "path": path,
                    "pak": source["pak"],
                    "benchExportIndex": bench_export.get("index"),
                    "benchObjectName": bench_export.get("objectName"),
                    "vendingExportIndex": vending_export.get("index"),
                    "vendingObjectName": vending_export.get("objectName"),
                    "coordinateSpace": coordinate,
                })
            if len(pair_rows) >= MAX_PAIR_RESULTS:
                break
        if len(pair_rows) >= MAX_PAIR_RESULTS:
            break

    pair_rows.sort(key=lambda row: (
        not bool(row["coordinateSpace"].get("relativeCoordinateDistanceValidated")),
        float(row["coordinateSpace"].get("relativeCoordinateDistance") or float("inf")),
        str(row.get("path", "")).casefold(),
        str(row.get("benchObjectName", "")).casefold(),
        str(row.get("vendingObjectName", "")).casefold(),
    ))
    comparable = [
        row for row in pair_rows
        if row["coordinateSpace"].get("relativeCoordinateDistanceValidated")
    ]
    return {
        "implementationReady": False,
        "area": AREA_TERM,
        "pairCount": len(pair_rows),
        "pairResultsTruncated": len(pair_rows) >= MAX_PAIR_RESULTS,
        "relativeCoordinateComparablePairCount": len(comparable),
        "pairs": pair_rows,
        "scanErrors": errors,
        "worldSpaceAdjacencyValidated": False,
        "suppressionAuthorized": False,
        "notes": [
            "This follow-up intentionally re-reads only Sector 7 candidate packages and never writes them.",
            "ObjectLayout exact actor identity can be joined later with correlate_layout_with_coordinate_evidence using path + bench/vending export indices.",
            "A validated common relative parent removes one coordinate-space ambiguity but is not a bench-deletion authorization; exact Chapter 3 instance identity and mutation/in-game acceptance remain separate gates.",
        ],
    }
