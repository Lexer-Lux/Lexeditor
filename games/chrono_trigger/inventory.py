"""Archive-family inventory for Chrono Trigger Steam reverse-engineering work.

The inventory intentionally derives candidates from the user's actual ARC1 index
instead of assuming SNES tables survived at fixed offsets or guessing Steam
filenames. It is read-only and does not decompress candidate resources.
"""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from .coverage import resource_override
from .data import classify_resource
from .resources import ResourceArchive


CANDIDATE_KEYWORDS = {
    "battle": ("battle", "btl", "combat"),
    "enemy": ("enemy", "monster", "mob", "boss"),
    "tech": ("tech", "skill", "ability", "magic", "spell"),
    "item": ("item", "weapon", "armor", "helmet", "accessory", "equip"),
    "shop": ("shop", "store", "merchant"),
    "party": ("party", "player", "character", "chara"),
}


def _parts(path: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in PurePosixPath(path).parts)


def _candidate_score(path: str, words: tuple[str, ...]) -> int:
    lower = path.casefold()
    parts = _parts(path)
    score = 0
    for word in words:
        if word in parts:
            score += 4
        if any(part.startswith(word) or part.endswith(word) for part in parts):
            score += 2
        if word in lower:
            score += 1
    return score


def _counter_rows(counter: Counter, *, key: str, limit: int = 40) -> list[dict]:
    """Return stable most-common rows without implying payload semantics."""
    return [
        {key: value, "count": count}
        for value, count in sorted(counter.items(), key=lambda row: (-row[1], str(row[0]).casefold()))[:limit]
    ]


def inventory_archive(archive: ResourceArchive, *, sample_limit: int = 40) -> dict:
    entries = list(archive.entries)
    paths = [entry.path for entry in entries]
    by_path = {entry.path: entry for entry in entries}
    extensions = Counter((PurePosixPath(path).suffix.casefold() or "<none>") for path in paths)
    top = Counter((PurePosixPath(path).parts[0] if PurePosixPath(path).parts else "<root>") for path in paths)
    directories = Counter()
    for path in paths:
        parent = PurePosixPath(path).parent.as_posix()
        directories[parent] += 1

    candidates: dict[str, dict] = {}
    for family, words in CANDIDATE_KEYWORDS.items():
        scored = []
        family_directories = Counter()
        family_extensions = Counter()
        family_sizes = Counter()
        for path in paths:
            score = _candidate_score(path, words)
            if not score:
                continue
            classification = resource_override(path) or classify_resource(path)
            entry = by_path[path]
            stored_size = getattr(entry, "stored_size", None)
            row = {
                "path": path,
                "score": score,
                "kind": classification.get("kind", "raw"),
                "coverage": classification.get("coverage", "raw"),
                "status": classification.get("status", "unknown"),
            }
            if isinstance(stored_size, int) and stored_size >= 0:
                row["storedSize"] = stored_size
                family_sizes[stored_size] += 1
            scored.append(row)
            family_directories[PurePosixPath(path).parent.as_posix()] += 1
            family_extensions[PurePosixPath(path).suffix.casefold() or "<none>"] += 1
        scored.sort(key=lambda row: (-row["score"], row["path"].casefold()))
        candidates[family] = {
            "matchCount": len(scored),
            "samples": scored[:max(1, min(int(sample_limit), 200))],
            "directoryClusters": _counter_rows(family_directories, key="path"),
            "extensionClusters": _counter_rows(family_extensions, key="extension"),
            "storedSizeClusters": _counter_rows(family_sizes, key="storedSize"),
        }

    # Directory clusters are particularly useful for anonymous/generated file
    # names where keyword search only matches the parent folder.
    directory_rows = [
        {"path": directory, "count": count}
        for directory, count in directories.most_common()
    ]
    return {
        "kind": "chrono-trigger-resource-inventory",
        "archive": str(archive.path),
        "resourceCount": len(paths),
        "extensions": dict(sorted(extensions.items(), key=lambda row: (-row[1], row[0]))),
        "topLevel": dict(sorted(top.items(), key=lambda row: (-row[1], row[0].casefold()))),
        "directories": directory_rows,
        "candidates": candidates,
        "method": "ARC1-index-only; candidate directories/extensions/stored sizes use index metadata only; no candidate resource payloads were decompressed",
    }
