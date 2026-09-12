"""Archive-family inventory for Chrono Trigger Steam reverse-engineering work.

The inventory derives candidates from the user's actual ARC1 metadata instead
of assuming SNES tables survived at fixed offsets or guessing Steam filenames.
By default it is index-only. An explicit size-peek mode may additionally read
only each candidate block's decoded four-byte uncompressed-size prefix; it
still never inflates candidate payloads.
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


def _selected_families(families) -> list[str]:
    if families is None:
        return list(CANDIDATE_KEYWORDS)
    selected: list[str] = []
    for value in families:
        family = str(value).strip().casefold()
        if family not in CANDIDATE_KEYWORDS:
            raise ValueError(
                f"unknown candidate family {value!r}; expected one of {', '.join(CANDIDATE_KEYWORDS)}"
            )
        if family not in selected:
            selected.append(family)
    if not selected:
        raise ValueError("at least one candidate family must be selected")
    return selected


def _probe_clusters(family: str, scored: list[dict], *, use_declared_size: bool) -> list[dict]:
    """Recommend repeated path/size clusters for the bounded payload probe.

    These rows are triage hints only. Equal sizes and directories do not imply
    equal record semantics.
    """
    groups: dict[tuple[str, int], list[str]] = {}
    size_key = "declaredSize" if use_declared_size else "storedSize"
    for row in scored:
        size = row.get(size_key)
        if not isinstance(size, int):
            continue
        parent = PurePosixPath(row["path"]).parent.as_posix()
        groups.setdefault((parent, size), []).append(row["path"])
    recommendations = []
    for (parent, size), paths in groups.items():
        if len(paths) < 2:
            continue
        recommendations.append({
            "pathPrefix": parent,
            "sizeBasis": size_key,
            size_key: size,
            "count": len(paths),
            "samplePaths": sorted(paths, key=str.casefold)[:5],
            "probeArgs": {"family": family, "pathPrefix": parent},
        })
    recommendations.sort(key=lambda row: (-row["count"], row["pathPrefix"].casefold(), row[size_key]))
    return recommendations[:40]


def inventory_archive(
    archive: ResourceArchive, *, sample_limit: int = 40, peek_declared_sizes: bool = False,
    families=None,
) -> dict:
    entries = list(archive.entries)
    paths = [entry.path for entry in entries]
    by_path = {entry.path: entry for entry in entries}
    extensions = Counter((PurePosixPath(path).suffix.casefold() or "<none>") for path in paths)
    top = Counter((PurePosixPath(path).parts[0] if PurePosixPath(path).parts else "<root>") for path in paths)
    directories = Counter()
    for path in paths:
        parent = PurePosixPath(path).parent.as_posix()
        directories[parent] += 1

    selected_families = _selected_families(families)
    size_peeker = getattr(archive, "declared_payload_size", None)
    if peek_declared_sizes and not callable(size_peeker):
        raise ValueError("archive does not support declared payload-size peeking")

    # A resource path can match more than one candidate family (for example an
    # enemy file under Game/battle). Read its four-byte prefix at most once.
    declared_cache: dict[str, tuple[int | None, str | None]] = {}

    def declared_for(path: str, entry) -> tuple[int | None, str | None]:
        if path in declared_cache:
            return declared_cache[path]
        try:
            value = int(size_peeker(entry))
        except Exception as error:
            result = (None, str(error))
        else:
            result = (value, None)
        declared_cache[path] = result
        return result

    candidates: dict[str, dict] = {}
    for family in selected_families:
        words = CANDIDATE_KEYWORDS[family]
        scored = []
        family_directories = Counter()
        family_extensions = Counter()
        family_sizes = Counter()
        family_declared_sizes = Counter()
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
            if peek_declared_sizes:
                declared_size, declared_error = declared_for(path, entry)
                if declared_error is not None:
                    row["declaredSizeError"] = declared_error
                else:
                    row["declaredSize"] = declared_size
                    family_declared_sizes[declared_size] += 1
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
            "declaredSizeClusters": _counter_rows(family_declared_sizes, key="declaredSize"),
            "probeClusters": _probe_clusters(family, scored, use_declared_size=peek_declared_sizes),
        }

    directory_rows = [
        {"path": directory, "count": count}
        for directory, count in directories.most_common()
    ]
    if peek_declared_sizes:
        method = (
            "ARC1 index + four-byte decoded entry-size prefixes only; candidate directory/extension/stored-size/"
            "declared-size clusters and probe-ready repeated path/size groups; repeated candidate paths are peeked "
            "once; no candidate gzip payloads were decompressed"
        )
    else:
        method = (
            "ARC1-index-only; candidate directories/extensions/stored sizes and probe-ready repeated path/size groups "
            "use index metadata only; no candidate resource payloads were decompressed"
        )
    return {
        "kind": "chrono-trigger-resource-inventory",
        "archive": str(archive.path),
        "resourceCount": len(paths),
        "selectedFamilies": selected_families,
        "peekDeclaredSizes": bool(peek_declared_sizes),
        "peekedResourceCount": len(declared_cache),
        "extensions": dict(sorted(extensions.items(), key=lambda row: (-row[1], row[0]))),
        "topLevel": dict(sorted(top.items(), key=lambda row: (-row[1], row[0].casefold()))),
        "directories": directory_rows,
        "candidates": candidates,
        "method": method,
    }
