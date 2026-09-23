"""Format-agnostic differential save research for FF7R assessed-enemy state (#424).

This module intentionally does not parse or reproduce any third-party FF7R save
format implementation.  It treats save files as opaque bytes and compares
controlled before/after pairs.  Repeating the same experiment from duplicated
pre-Assessment saves lets us distinguish stable state transitions from ordinary
save noise such as timers or position.  Comparing those repeated experiments
across *different* enemies then helps separate shared save metadata from an
enemy-specific byte/bit transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MAX_REPORTED_RUNS = 512
MAX_REPORTED_OFFSETS = 4096
MAX_INTEGER_CANDIDATES = 1024
MAX_GROUPS = 128
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


def _stable_offset_set(pairs: Sequence[SavePair]) -> set[int]:
    changed_sets = [set(_changed_offsets(pair.before, pair.after)) for pair in pairs]
    return set.intersection(*changed_sets) if changed_sets else set()


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


def analyze_experiment_groups(groups: Mapping[str, Sequence[SavePair]]) -> dict[str, Any]:
    """Compare repeated controlled Assess experiments for different enemies.

    Each mapping value should contain repeated before/after pairs for *one*
    enemy/EnemyBookID. Offsets stable within every repetition of one group but
    absent from the other groups are especially useful discriminators. If two
    enemies change the same byte with different stable XOR masks, that is a
    useful bitset lead but still not proof of the save format or Assessed state.
    """
    if not isinstance(groups, Mapping) or not groups:
        raise ValueError("at least one named save experiment group is required")
    if len(groups) > MAX_GROUPS:
        raise ValueError(f"save experiment group count exceeds {MAX_GROUPS}")

    normalized: dict[str, tuple[SavePair, ...]] = {}
    for raw_name, raw_pairs in groups.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("save experiment group names must be non-empty")
        pairs = tuple(raw_pairs)
        if not pairs:
            raise ValueError(f"save experiment group {name!r} has no pairs")
        if any(not isinstance(pair, SavePair) for pair in pairs):
            raise TypeError(f"save experiment group {name!r} must contain SavePair values")
        if name in normalized:
            raise ValueError(f"duplicate save experiment group name: {name}")
        normalized[name] = pairs

    stable_by_group = {
        name: _stable_offset_set(pairs)
        for name, pairs in normalized.items()
    }
    stable_union = set.union(*stable_by_group.values()) if stable_by_group else set()
    shared_stable = set.intersection(*stable_by_group.values()) if stable_by_group else set()
    discriminating = stable_union - shared_stable

    transform_maps: dict[str, dict[int, dict[str, Any]]] = {}
    group_rows = []
    for name, pairs in normalized.items():
        stable = stable_by_group[name]
        transforms = _stable_transform_rows(pairs, stable)
        transform_map = {int(row["offset"]): row for row in transforms}
        transform_maps[name] = transform_map
        others = set.union(*(
            offsets for other_name, offsets in stable_by_group.items()
            if other_name != name
        )) if len(stable_by_group) > 1 else set()
        exclusive = stable - others
        group_rows.append({
            "name": name,
            "pairCount": len(pairs),
            "stableChangedByteCount": len(stable),
            "stableChangedOffsets": sorted(stable)[:MAX_REPORTED_OFFSETS],
            "stableOffsetsTruncated": len(stable) > MAX_REPORTED_OFFSETS,
            "exclusiveStableByteCount": len(exclusive),
            "exclusiveStableOffsets": sorted(exclusive)[:MAX_REPORTED_OFFSETS],
            "exclusiveOffsetsTruncated": len(exclusive) > MAX_REPORTED_OFFSETS,
            "exclusiveStableRuns": [
                {"start": start, "end": end, "length": end - start}
                for start, end in _runs(exclusive)[:MAX_REPORTED_RUNS]
            ],
            "stableTransforms": transforms[:MAX_REPORTED_OFFSETS],
        })

    same_offset_different_xor = []
    for offset in sorted(shared_stable):
        masks: dict[str, int] = {}
        complete = True
        for name in normalized:
            row = transform_maps[name].get(offset)
            if not row or not row.get("sameXorMask") or row.get("xorMask") in (None, 0):
                complete = False
                break
            masks[name] = int(row["xorMask"])
        if complete and len(set(masks.values())) > 1:
            same_offset_different_xor.append({
                "offset": offset,
                "groupXorMasks": masks,
                "singleBitMasks": all(mask & (mask - 1) == 0 for mask in masks.values()),
            })

    shared_transform_rows = []
    for offset in sorted(shared_stable):
        per_group = {
            name: transform_maps[name].get(offset)
            for name in normalized
            if transform_maps[name].get(offset)
        }
        shared_transform_rows.append({
            "offset": offset,
            "groups": per_group,
            "sameXorAcrossGroups": bool(per_group) and len({
                row.get("xorMask") for row in per_group.values()
                if row.get("sameXorMask")
            }) == 1 and all(row.get("sameXorMask") for row in per_group.values()),
        })

    return {
        "groupCount": len(normalized),
        "groups": group_rows,
        "sharedStableByteCount": len(shared_stable),
        "sharedStableOffsets": sorted(shared_stable)[:MAX_REPORTED_OFFSETS],
        "sharedStableOffsetsTruncated": len(shared_stable) > MAX_REPORTED_OFFSETS,
        "sharedStableRuns": [
            {"start": start, "end": end, "length": end - start}
            for start, end in _runs(shared_stable)[:MAX_REPORTED_RUNS]
        ],
        "discriminatingStableByteCount": len(discriminating),
        "discriminatingStableOffsets": sorted(discriminating)[:MAX_REPORTED_OFFSETS],
        "discriminatingOffsetsTruncated": len(discriminating) > MAX_REPORTED_OFFSETS,
        "sameOffsetDifferentXorCandidates": same_offset_different_xor[:MAX_REPORTED_OFFSETS],
        "sameOffsetDifferentXorCandidatesTruncated": len(same_offset_different_xor) > MAX_REPORTED_OFFSETS,
        "sharedStableTransforms": shared_transform_rows[:MAX_REPORTED_OFFSETS],
        "notes": [
            "Shared stable offsets changed for every enemy experiment and are more likely to include save metadata/noise; enemy-specific or mask-specific differences are stronger discriminators, not proof.",
            "Exclusive stable offsets changed reliably for one experiment group and not the others. Repeat with additional EnemyBookIDs before treating them as enemy-state candidates.",
            "A same-byte/different-single-bit XOR pattern across enemies is consistent with a packed bitset hypothesis, but the probe does not infer indexing, bit order, encryption, compression, or field meaning.",
            "Use duplicated pre-Assessment saves, perform exactly one Assess action, save immediately, and keep location/time/inventory/progression as constant as practical.",
            "No save mutation is performed.",
        ],
    }


def analyze_save_paths(path_pairs: Sequence[tuple[Path, Path, str]]) -> dict[str, Any]:
    pairs = [
        SavePair(Path(before).read_bytes(), Path(after).read_bytes(), label)
        for before, after, label in path_pairs
    ]
    return analyze_save_pairs(pairs)
