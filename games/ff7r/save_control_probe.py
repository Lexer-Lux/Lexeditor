"""No-op control subtraction for FF7R Assessed-state save research (#424).

Repeated Assess experiments can isolate byte changes that recur across runs, but
some save-system metadata can recur just as reliably. This module compares those
experiments with repeated no-op controls made from the same duplicated baseline:
load, make no gameplay/progression change, and save immediately.

The result is still evidence only. Removing control-stable offsets can make an
Assessed-state candidate much stronger, but does not prove the save field's
meaning, encoding, EnemyBook indexing, bit order, compression, or encryption.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .save_diff_probe import (
    MAX_REPORTED_OFFSETS,
    MAX_REPORTED_RUNS,
    SavePair,
    analyze_save_pairs,
)


def _changed_offsets(before: bytes, after: bytes) -> set[int]:
    limit = min(len(before), len(after))
    changed = {index for index in range(limit) if before[index] != after[index]}
    if len(before) != len(after):
        changed.update(range(limit, max(len(before), len(after))))
    return changed


def _stable_offsets(pairs: Sequence[SavePair]) -> set[int]:
    changed = [_changed_offsets(pair.before, pair.after) for pair in pairs]
    return set.intersection(*changed) if changed else set()


def _runs(offsets: Iterable[int]) -> list[dict[str, int]]:
    ordered = sorted(set(int(offset) for offset in offsets))
    if not ordered:
        return []
    rows: list[dict[str, int]] = []
    start = previous = ordered[0]
    for offset in ordered[1:]:
        if offset == previous + 1:
            previous = offset
            continue
        rows.append({"start": start, "end": previous + 1, "length": previous + 1 - start})
        start = previous = offset
    rows.append({"start": start, "end": previous + 1, "length": previous + 1 - start})
    return rows


def _candidate_transforms(pairs: Sequence[SavePair], offsets: Iterable[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in sorted(offsets):
        transforms = []
        complete = True
        for pair in pairs:
            if offset >= len(pair.before) or offset >= len(pair.after):
                complete = False
                break
            before = pair.before[offset]
            after = pair.after[offset]
            transforms.append({
                "label": pair.label,
                "before": before,
                "after": after,
                "xor": before ^ after,
            })
        if not complete:
            continue
        xors = {row["xor"] for row in transforms}
        before_values = {row["before"] for row in transforms}
        after_values = {row["after"] for row in transforms}
        same_xor = len(xors) == 1
        xor_mask = next(iter(xors)) if same_xor else None
        rows.append({
            "offset": offset,
            "transforms": transforms,
            "sameTransform": len(before_values) == 1 and len(after_values) == 1,
            "sameXorMask": same_xor,
            "xorMask": xor_mask,
            "singleBitXor": bool(
                xor_mask is not None
                and xor_mask != 0
                and xor_mask & (xor_mask - 1) == 0
            ),
        })
    return rows


def _baseline_report(experiment_pairs: Sequence[SavePair], control_pairs: Sequence[SavePair]) -> dict[str, Any]:
    pairs = tuple(experiment_pairs) + tuple(control_pairs)
    first = pairs[0].before
    equal = [pair.before == first for pair in pairs]
    return {
        "sampleCount": len(pairs),
        "byteIdentical": all(equal),
        "sizeSet": sorted({len(pair.before) for pair in pairs}),
        "mismatchedSamples": [
            index for index, matches in enumerate(equal) if not matches
        ][:MAX_REPORTED_OFFSETS],
        "mismatchedSamplesTruncated": sum(not matches for matches in equal) > MAX_REPORTED_OFFSETS,
    }


def analyze_controlled_save_pairs(
    experiment_pairs: Sequence[SavePair],
    control_pairs: Sequence[SavePair],
) -> dict[str, Any]:
    """Subtract stable no-op-save changes from repeated Assess experiments."""
    if not experiment_pairs:
        raise ValueError("at least one Assess before/after pair is required")
    if not control_pairs:
        raise ValueError("at least one no-op control before/after pair is required")
    if any(not isinstance(pair, SavePair) for pair in experiment_pairs):
        raise TypeError("experiment_pairs must contain SavePair values")
    if any(not isinstance(pair, SavePair) for pair in control_pairs):
        raise TypeError("control_pairs must contain SavePair values")

    experiment = analyze_save_pairs(experiment_pairs)
    control = analyze_save_pairs(control_pairs)
    experiment_stable = _stable_offsets(experiment_pairs)
    control_stable = _stable_offsets(control_pairs)
    overlap = experiment_stable & control_stable
    candidates = experiment_stable - control_stable
    control_only = control_stable - experiment_stable
    transforms = _candidate_transforms(experiment_pairs, candidates)
    single_bit = [row for row in transforms if row["singleBitXor"]]
    baseline = _baseline_report(experiment_pairs, control_pairs)

    candidate_runs = _runs(candidates)
    overlap_runs = _runs(overlap)
    return {
        "experiment": experiment,
        "control": control,
        "baseline": baseline,
        "experimentStableByteCount": len(experiment_stable),
        "controlStableByteCount": len(control_stable),
        "controlOverlapByteCount": len(overlap),
        "controlOverlapOffsets": sorted(overlap)[:MAX_REPORTED_OFFSETS],
        "controlOverlapOffsetsTruncated": len(overlap) > MAX_REPORTED_OFFSETS,
        "controlOverlapRuns": overlap_runs[:MAX_REPORTED_RUNS],
        "controlOverlapRunsTruncated": len(overlap_runs) > MAX_REPORTED_RUNS,
        "controlOnlyStableByteCount": len(control_only),
        "controlOnlyStableOffsets": sorted(control_only)[:MAX_REPORTED_OFFSETS],
        "controlOnlyOffsetsTruncated": len(control_only) > MAX_REPORTED_OFFSETS,
        "candidateByteCount": len(candidates),
        "candidateOffsets": sorted(candidates)[:MAX_REPORTED_OFFSETS],
        "candidateOffsetsTruncated": len(candidates) > MAX_REPORTED_OFFSETS,
        "candidateRuns": candidate_runs[:MAX_REPORTED_RUNS],
        "candidateRunsTruncated": len(candidate_runs) > MAX_REPORTED_RUNS,
        "candidateTransforms": transforms[:MAX_REPORTED_OFFSETS],
        "candidateTransformsTruncated": len(transforms) > MAX_REPORTED_OFFSETS,
        "singleBitCandidateCount": len(single_bit),
        "singleBitCandidates": single_bit[:MAX_REPORTED_OFFSETS],
        "singleBitCandidatesTruncated": len(single_bit) > MAX_REPORTED_OFFSETS,
        "notes": [
            "Candidate offsets changed in every Assess experiment but not in every no-op save control; this removes repeatable save-system noise but does not prove Assessed-state semantics.",
            "For the strongest control, duplicate one pre-Assessment save byte-for-byte into every Assess and no-op run before launching the game.",
            "baseline.byteIdentical=false weakens the experiment because pre-run state already differed; the report remains read-only rather than silently discarding data.",
            "A stable single-bit XOR candidate is compatible with a packed flag but does not establish bit order or EnemyBookID mapping.",
            "No save file is parsed or modified.",
        ],
    }
