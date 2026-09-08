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


def analyze_controlled_experiment_groups(
    groups: dict[str, Sequence[SavePair]],
    control_pairs: Sequence[SavePair],
) -> dict[str, Any]:
    """Subtract stable no-op-save offsets from cross-enemy Assess experiments."""
    if not groups:
        raise ValueError("at least one named Assess experiment group is required")
    if not control_pairs:
        raise ValueError("at least one no-op control before/after pair is required")
    if any(not isinstance(pair, SavePair) for pair in control_pairs):
        raise TypeError("control_pairs must contain SavePair values")

    normalized: dict[str, tuple[SavePair, ...]] = {}
    for raw_name, raw_pairs in groups.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("Assess experiment group names must be non-empty")
        pairs = tuple(raw_pairs)
        if not pairs:
            raise ValueError(f"Assess experiment group {name!r} has no pairs")
        if any(not isinstance(pair, SavePair) for pair in pairs):
            raise TypeError(f"Assess experiment group {name!r} must contain SavePair values")
        normalized[name] = pairs

    # Reuse the base analyzer so all existing cross-enemy hypotheses and safety
    # notes remain visible alongside the stricter no-op subtraction layer.
    from .save_diff_probe import analyze_experiment_groups

    group_analysis = analyze_experiment_groups(normalized)
    control = analyze_save_pairs(control_pairs)
    control_stable = _stable_offsets(control_pairs)
    stable_by_group = {
        name: _stable_offsets(pairs)
        for name, pairs in normalized.items()
    }
    candidates_by_group = {
        name: stable - control_stable
        for name, stable in stable_by_group.items()
    }
    candidate_union = set.union(*candidates_by_group.values()) if candidates_by_group else set()
    shared_candidates = set.intersection(*candidates_by_group.values()) if candidates_by_group else set()
    discriminating_candidates = candidate_union - shared_candidates

    rows = []
    for name, pairs in normalized.items():
        candidates = candidates_by_group[name]
        others = set.union(*(
            offsets for other_name, offsets in candidates_by_group.items()
            if other_name != name
        )) if len(candidates_by_group) > 1 else set()
        exclusive = candidates - others
        transforms = _candidate_transforms(pairs, candidates)
        rows.append({
            "name": name,
            "rawStableByteCount": len(stable_by_group[name]),
            "controlSubtractedByteCount": len(candidates),
            "controlSubtractedOffsets": sorted(candidates)[:MAX_REPORTED_OFFSETS],
            "controlSubtractedOffsetsTruncated": len(candidates) > MAX_REPORTED_OFFSETS,
            "exclusiveCandidateByteCount": len(exclusive),
            "exclusiveCandidateOffsets": sorted(exclusive)[:MAX_REPORTED_OFFSETS],
            "exclusiveCandidateOffsetsTruncated": len(exclusive) > MAX_REPORTED_OFFSETS,
            "candidateTransforms": transforms[:MAX_REPORTED_OFFSETS],
            "candidateTransformsTruncated": len(transforms) > MAX_REPORTED_OFFSETS,
        })

    bitset_leads = [
        row for row in group_analysis.get("sameOffsetDifferentXorCandidates", ())
        if int(row.get("offset", -1)) not in control_stable
    ]
    all_experiment_pairs = tuple(
        pair
        for pairs in normalized.values()
        for pair in pairs
    )
    baseline = _baseline_report(all_experiment_pairs, control_pairs)

    return {
        "groupAnalysis": group_analysis,
        "control": control,
        "baseline": baseline,
        "controlStableByteCount": len(control_stable),
        "controlStableOffsets": sorted(control_stable)[:MAX_REPORTED_OFFSETS],
        "controlStableOffsetsTruncated": len(control_stable) > MAX_REPORTED_OFFSETS,
        "groups": rows,
        "sharedCandidateByteCount": len(shared_candidates),
        "sharedCandidateOffsets": sorted(shared_candidates)[:MAX_REPORTED_OFFSETS],
        "sharedCandidateOffsetsTruncated": len(shared_candidates) > MAX_REPORTED_OFFSETS,
        "discriminatingCandidateByteCount": len(discriminating_candidates),
        "discriminatingCandidateOffsets": sorted(discriminating_candidates)[:MAX_REPORTED_OFFSETS],
        "discriminatingCandidateOffsetsTruncated": len(discriminating_candidates) > MAX_REPORTED_OFFSETS,
        "sameOffsetDifferentXorCandidates": bitset_leads[:MAX_REPORTED_OFFSETS],
        "sameOffsetDifferentXorCandidatesTruncated": len(bitset_leads) > MAX_REPORTED_OFFSETS,
        "notes": [
            "Cross-enemy candidate offsets are stable inside an enemy's repeated Assess runs after removing offsets stable in the no-op save controls.",
            "Offsets shared by every enemy after control subtraction can still be Assess-action metadata rather than the per-enemy state; enemy-exclusive or different-XOR candidates remain stronger leads.",
            "sameOffsetDifferentXorCandidates excludes any byte that is itself stable in the no-op controls, but still does not prove a packed EnemyBook bitset.",
            "Use byte-identical duplicated pre-Assessment baselines whenever possible; baseline.byteIdentical reports whether that condition actually held.",
            "No save file is parsed or modified.",
        ],
    }
