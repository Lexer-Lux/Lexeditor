"""Read-only installed-asset probe for the Chapter 3 Sector 7 blue bench.

The Better Restore tweak must remove exactly the bench next to the vending machine,
not every rest point. FF7R identifies Chapter 3's Sector 7 area with the `slum7`
namespace and exposes dedicated common object program IDs/classes for benches and
vending machines. This probe scans only cooked `slum7` map/package files and
prefers resolved Unreal object-table evidence over printable-string hints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .archive import installed_paks
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


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


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


def rank_bench_candidates(files: Iterable[dict]) -> list[dict]:
    """Rank already-scanned files; exact object-table evidence dominates strings."""
    ranked = []
    for row in files:
        strings = list(row.get("interestingStrings", []))
        bench = _matches_token(strings, BENCH_TOKENS)
        vending = _matches_token(strings, VENDING_TOKENS)
        bench_exports = list(row.get("benchExports", []))
        vending_exports = list(row.get("vendingExports", []))
        shared_outer_pairs = list(row.get("sharedOuterPairs", []))
        if not bench and not vending and not bench_exports and not vending_exports:
            continue

        score = (100 if bench and vending else 0) + len(bench) * 10 + len(vending) * 10
        # A resolved export/class is much stronger than a string living anywhere
        # in the package. A bench/vending pair with the same authored outer is
        # stronger still, though it does not prove physical adjacency.
        score += len(bench_exports) * 250 + len(vending_exports) * 250
        if bench_exports and vending_exports:
            score += 1000
        score += len(shared_outer_pairs) * 2000
        path = str(row.get("path", ""))
        if path.casefold().endswith(".umap"):
            score += 25
        ranked.append({
            **row,
            "benchEvidence": bench,
            "vendingEvidence": vending,
            # Preserve the original string-evidence contract for callers/tests.
            "containsBenchAndVending": bool(bench and vending),
            "containsBenchAndVendingExports": bool(bench_exports and vending_exports),
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
    # Later PAKs replace earlier definitions of the exact same cooked path.
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
        scanned.append({
            "pak": source["pak"],
            "path": source["path"],
            "size": len(data),
            "interestingStrings": strings,
            **object_evidence,
        })

    ranked = rank_bench_candidates(scanned)
    paired = [row for row in ranked if row["containsBenchAndVending"]]
    object_paired = [row for row in ranked if row["containsBenchAndVendingExports"]]
    return {
        "area": AREA_TERM,
        "pakCount": pak_count,
        "matchingCookedFiles": len(selected),
        "scannedCookedFiles": min(len(selected), MAX_CANDIDATE_FILES),
        "truncated": truncated,
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
            "A shared outer such as PersistentLevel does not prove world-space adjacency; transform/instance identity still must be established before suppression.",
            "The object-table parser is read-only and fails closed on unsupported cooked package layouts.",
            "This probe does not remove anything; the exact authored actor/object identity must be established before suppression.",
            "A global objCmn_ProgBench replacement is explicitly unsafe because it would affect unrelated benches.",
        ],
    }
