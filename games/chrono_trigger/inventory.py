"""Archive-family inventory for Chrono Trigger Steam reverse-engineering work.

The inventory intentionally derives candidates from the user's actual ARC1 index
instead of assuming SNES tables survived at fixed offsets or guessing Steam
filenames. It is read-only and does not decompress candidate resources.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import PurePosixPath
import re

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


def inventory_archive(archive: ResourceArchive, *, sample_limit: int = 40) -> dict:
    paths = [entry.path for entry in archive.entries]
    extensions = Counter((PurePosixPath(path).suffix.casefold() or "<none>") for path in paths)
    top = Counter((PurePosixPath(path).parts[0] if PurePosixPath(path).parts else "<root>") for path in paths)
    directories = Counter()
    for path in paths:
        parent = PurePosixPath(path).parent.as_posix()
        directories[parent] += 1

    candidates: dict[str, dict] = {}
    for family, words in CANDIDATE_KEYWORDS.items():
        scored = []
        for path in paths:
            score = _candidate_score(path, words)
            if score:
                classification = resource_override(path) or classify_resource(path)
                scored.append({
                    "path": path,
                    "score": score,
                    "kind": classification.get("kind", "raw"),
                    "coverage": classification.get("coverage", "raw"),
                    "status": classification.get("status", "unknown"),
                })
        scored.sort(key=lambda row: (-row["score"], row["path"].casefold()))
        candidates[family] = {
            "matchCount": len(scored),
            "samples": scored[:max(1, min(int(sample_limit), 200))],
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
        "method": "ARC1-index-only; no candidate resource payloads were decompressed",
    }
