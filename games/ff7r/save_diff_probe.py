"""Format-agnostic differential save research for FF7R assessed-enemy state (#424).

This module intentionally does not parse or reproduce any third-party FF7R save
format implementation.  It treats save files as opaque bytes and compares
controlled before/after pairs.  Repeating the same experiment from duplicated
pre-Assessment saves lets us distinguish stable state transitions from ordinary
save noise such as timers or position.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


MAX_REPORTED_RUNS = 512
MAX_REPORTED_OFFSETS = 4096
MAX_INTEGER_CANDIDATES = 1024
INTEGER_WIDTHS = (1, 2, 4, 8)


@dataclass(frozen=True)
class SavePair:
    before: bytes
    after: bytes
    label: str = ""


def _changed_offsets(before: bytes, after: bytes) -> list[int]:
    limit = min(len(before), len(after))
    changed = [index for index in range(limit) if before[index] != after[index]]
    if len(before) != len(after):
        changed.extend(range(limit, max(len(before), len(after))))
    return changed


def _runs(offsets: Iterable[int]) -> list[tuple[int, int]]:
    values = sorted(set(int(value) for value in offsets))
    if not values:
        return []
    result: list[tuple[int, int]] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        result.append((start, previous + 1))
        start = previous = value
    result.append((start, previous + 1))
    return result


def _hex_slice(data: bytes, start: int, end: int) -> str:
    if start >= len(data):
        return ""
    return data[start:min(end, len(data))].hex()


def _pair_report(pair: SavePair) -> dict[str, Any]:
    changed = _changed_offsets(pair.before, pair.after)
    runs = _runs(changed)
    run_rows = [
        {
            "start": start,
            "end": end,
            "length": end - start,
            "beforeHex": _hex_slice(pair.before, start, end),
            "afterHex": _hex_slice(pair.after, start, end),
        }
        for start, end in runs[:MAX_REPORTED_RUNS]
    ]
    return {
        "label": pair.label,
        "beforeSize": len(pair.before),
        "afterSize": len(pair.after),
        "sameSize": len(pair.before) == len(pair.after),
        "changedByteCount": len(changed),
        "changedRunCount": len(runs),
        "changedOffsets": changed[:MAX_REPORTED_OFFSETS],
        "offsetsTruncated": len(changed) > MAX_REPORTED_OFFSETS,
        "runs": run_rows,
        "runsTruncated": len(runs) > MAX_REPORTED_RUNS,
    }


def _stable_transform_rows(pairs: Sequence[SavePair], stable_offsets: Iterable[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in sorted(stable_offsets):
        transforms: list[tuple[int, int]] = []
        complete = True
        for pair in pairs:
            if offset >= len(pair.before) or offset >= len(pair.after):
                complete = False
                break
            transforms.append((pair.before[offset], pair.after[offset]))
        if not complete:
            continue
        xor_masks = {before ^ after for before, after in transforms}
        before_values = {before for before, _after in transforms}
        after_values = {after for _before, after in transforms}
        rows.append({
            "offset": offset,
            "transforms": [
                {"before": before, "after": after, "xor": before ^ after}
                for before, after in transforms
            ],
            "sameXorMask": len(xor_masks) == 1,
            "xorMask": next(iter(xor_masks)) if len(xor_masks) == 1 else None,
            "sameBeforeValue": len(before_values) == 1,
            "sameAfterValue": len(after_values) == 1,
            "beforeValue": next(iter(before_values)) if len(before_values) == 1 else None,
            "afterValue": next(iter(after_values)) if len(after_values) == 1 else None,
        })
    return rows


def _integer_candidates(pairs: Sequence[SavePair], stable_offsets: set[int]) -> list[dict[str, Any]]:
    """Report aligned little-endian windows fully contained in stable changed bytes."""
    candidates: list[dict[str, Any]] = []
    if not pairs:
        return candidates
    max_common_size = min(min(len(pair.before), len(pair.after)) for pair in pairs)
    for width in INTEGER_WIDTHS:
        if width > max_common_size:
            continue
        for offset in range(0, max_common_size - width + 1):
            byte_offsets = set(range(offset, offset + width))
            if not byte_offsets.issubset(stable_offsets):
                continue
            transforms = []
            deltas = []
            for pair in pairs:
                before = int.from_bytes(pair.before[offset:offset + width], "little", signed=False)
                after = int.from_bytes(pair.after[offset:offset + width], "little", signed=False)
                transforms.append((before, after))
                deltas.append(after - before)
            if not any(before != after for before, after in transforms):
                continue
            candidates.append({
                "offset": offset,
                "width": width,
                "transforms": [
                    {"before": before, "after": after, "delta": after - before}
                    for before, after in transforms
                ],
                "sameDelta": len(set(deltas)) == 1,
                "delta": deltas[0] if len(set(deltas)) == 1 else None,
            })
            if len(candidates) >= MAX_INTEGER_CANDIDATES:
                return candidates
    return candidates


def analyze_save_pairs(pairs: Sequence[SavePair]) -> dict[str, Any]:
    if not pairs:
        raise ValueError("at least one before/after save pair is required")
    if any(not isinstance(pair, SavePair) for pair in pairs):
        raise TypeError("pairs must contain SavePair values")

    reports = [_pair_report(pair) for pair in pairs]
    changed_sets = [set(_changed_offsets(pair.before, pair.after)) for pair in pairs]
    stable = set.intersection(*changed_sets)
    union = set.union(*changed_sets)
    variable = union - stable
    stable_runs = _runs(stable)
    variable_runs = _runs(variable)

    stable_transforms = _stable_transform_rows(pairs, stable)
    stable_same_transform = [
        row for row in stable_transforms
        if row["sameBeforeValue"] and row["sameAfterValue"]
    ]
    stable_same_xor = [row for row in stable_transforms if row["sameXorMask"]]

    return {
        "pairCount": len(pairs),
        "pairs": reports,
        "allPairsSameSize": all(report["sameSize"] for report in reports),
        "stableChangedByteCount": len(stable),
        "stableChangedOffsets": sorted(stable)[:MAX_REPORTED_OFFSETS],
        "stableOffsetsTruncated": len(stable) > MAX_REPORTED_OFFSETS,
        "stableChangedRuns": [
            {"start": start, "end": end, "length": end - start}
            for start, end in stable_runs[:MAX_REPORTED_RUNS]
        ],
        "stableRunsTruncated": len(stable_runs) > MAX_REPORTED_RUNS,
        "variableChangedByteCount": len(variable),
        "variableChangedOffsets": sorted(variable)[:MAX_REPORTED_OFFSETS],
        "variableOffsetsTruncated": len(variable) > MAX_REPORTED_OFFSETS,
        "variableChangedRuns": [
            {"start": start, "end": end, "length": end - start}
            for start, end in variable_runs[:MAX_REPORTED_RUNS]
        ],
        "variableRunsTruncated": len(variable_runs) > MAX_REPORTED_RUNS,
        "stableTransforms": stable_transforms[:MAX_REPORTED_OFFSETS],
        "stableTransformsTruncated": len(stable_transforms) > MAX_REPORTED_OFFSETS,
        "sameBeforeAfterTransformCount": len(stable_same_transform),
        "sameXorMaskCount": len(stable_same_xor),
        "integerCandidates": _integer_candidates(pairs, stable),
        "notes": [
            "Stable changes are byte offsets that changed in every supplied before/after pair; they are candidates, not proof of Assessed state.",
            "For strongest evidence, duplicate the same pre-Assessment save and repeat the same single-enemy Assess experiment several times before saving immediately.",
            "Timer, position, autosave metadata and unrelated progression can remain in stable changes if the experiment is not controlled.",
            "A convincing Assessed-state candidate should survive repetitions and later correlate with the same EnemyBookID across different enemies or controlled state transitions.",
            "This probe is intentionally format-agnostic and performs no save mutation.",
        ],
    }


def analyze_save_paths(path_pairs: Sequence[tuple[Path, Path, str]]) -> dict[str, Any]:
    pairs = [
        SavePair(Path(before).read_bytes(), Path(after).read_bytes(), label)
        for before, after, label in path_pairs
    ]
    return analyze_save_pairs(pairs)
