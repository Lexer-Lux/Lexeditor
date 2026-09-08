"""Read-only installed-asset probe for the Chapter 3 Sector 7 blue bench.

The Better Restore tweak must remove exactly the bench next to the vending machine,
not every rest point.  FF7R identifies Chapter 3's Sector 7 area with the `slum7`
namespace and exposes dedicated common object program IDs for benches and vending
machines.  This probe scans only cooked `slum7` map/package files and ranks files
that contain evidence for both object types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .archive import installed_paks
from .raw_asset_probe import extract_interesting_strings
from .tooling import get_file, list_pak


AREA_TERM = "slum7"
COOKED_SUFFIXES = (".umap", ".uasset", ".uexp")
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
SCAN_TOKENS = BENCH_TOKENS + VENDING_TOKENS + (
    "FieldAction",
    "ObjectLayout",
    "Location",
    "Transform",
    "PersistentLevel",
)
MAX_CANDIDATE_FILES = 1024
MAX_ERRORS = 128


def _normalize(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("/")


def _matches_token(strings: list[dict], tokens: Iterable[str]) -> list[dict]:
    folded = tuple(token.casefold() for token in tokens)
    return [
        row for row in strings
        if any(token in str(row.get("text", "")).casefold() for token in folded)
    ]


def rank_bench_candidates(files: Iterable[dict]) -> list[dict]:
    """Rank already-scanned files; useful for tests and installed probing."""
    ranked = []
    for row in files:
        strings = list(row.get("interestingStrings", []))
        bench = _matches_token(strings, BENCH_TOKENS)
        vending = _matches_token(strings, VENDING_TOKENS)
        if not bench and not vending:
            continue
        score = (100 if bench and vending else 0) + len(bench) * 10 + len(vending) * 10
        path = str(row.get("path", ""))
        if path.casefold().endswith(".umap"):
            score += 25
        ranked.append({
            **row,
            "benchEvidence": bench,
            "vendingEvidence": vending,
            "containsBenchAndVending": bool(bench and vending),
            "score": score,
        })
    return sorted(
        ranked,
        key=lambda row: (-int(row["score"]), str(row.get("path", "")).casefold()),
    )


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
        if not strings:
            continue
        scanned.append({
            "pak": source["pak"],
            "path": source["path"],
            "size": len(data),
            "interestingStrings": strings,
        })

    ranked = rank_bench_candidates(scanned)
    paired = [row for row in ranked if row["containsBenchAndVending"]]
    return {
        "area": AREA_TERM,
        "pakCount": pak_count,
        "matchingCookedFiles": len(selected),
        "scannedCookedFiles": min(len(selected), MAX_CANDIDATE_FILES),
        "truncated": truncated,
        "pairedCandidates": paired,
        "allEvidenceCandidates": ranked,
        "scanErrors": errors,
        "knownContracts": {
            "benchActorClass": "EndFieldActionActorBenchBreak",
            "benchProgramId": "objCmn_ProgBench",
            "vendingProgramId": "objCmn_ProgVendingMachine",
            "sector7Namespace": AREA_TERM,
        },
        "notes": [
            "Files containing both bench and vending identifiers are the strongest candidates for the requested Chapter 3 pair.",
            "This probe does not remove anything; the exact authored actor/object identity must be established before suppression.",
            "A global objCmn_ProgBench replacement is explicitly unsafe because it would affect unrelated benches.",
        ],
    }
