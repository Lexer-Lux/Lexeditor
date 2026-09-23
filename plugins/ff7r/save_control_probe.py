"""No-op control subtraction for FF7R Assessed-state save research (#424).

Repeated Assess experiments can isolate byte changes that recur across runs, but
some save-system metadata can recur just as reliably. This module compares those
experiments with repeated no-op controls made from the same duplicated baseline:
load, make no gameplay/progression change, and save immediately.

Control subtraction is byte-and-mask aware. A byte is removed only when repeated
no-op saves reproduce a compatible stable transition from the same byte value.
If Assess and no-op runs touch different bits of the same byte, the residual bits
remain candidates instead of discarding the whole byte.

The result is still evidence only. It does not prove field meaning, EnemyBook
indexing, bit order, compression, encryption, or any safe save mutation layout.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .save_diff_probe import (
    MAX_REPORTED_OFFSETS,
    MAX_REPORTED_RUNS,
    SavePair,
    analyze_experiment_groups,
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


def _transform_row(pairs: Sequence[SavePair], offset: int) -> dict[str, Any] | None:
    transforms = []
    for pair in pairs:
        if offset >= len(pair.before) or offset >= len(pair.after):
            return None
        before = pair.before[offset]
        after = pair.after[offset]
        transforms.append({
            "label": pair.label,
            "before": before,
            "after": after,
            "xor": before ^ after,
        })
    xors = {row["xor"] for row in transforms}
    before_values = {row["before"] for row in transforms}
    after_values = {row["after"] for row in transforms}
    same_xor = len(xors) == 1
    xor_mask = next(iter(xors)) if same_xor else None
    return {
        "offset": offset,
        "transforms": transforms,
        "sameTransform": len(before_values) == 1 and len(after_values) == 1,
        "sameXorMask": same_xor,
        "xorMask": xor_mask,
        "sameBeforeValue": len(before_values) == 1,
        "beforeValue": next(iter(before_values)) if len(before_values) == 1 else None,
        "sameAfterValue": len(after_values) == 1,
        "afterValue": next(iter(after_values)) if len(after_values) == 1 else None,
        "singleBitXor": bool(
            xor_mask is not None
            and xor_mask != 0
            and xor_mask & (xor_mask - 1) == 0
        ),
    }


def _transform_map(pairs: Sequence[SavePair], offsets: Iterable[int]) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for offset in offsets:
        row = _transform_row(pairs, int(offset))
        if row is not None:
            rows[int(offset)] = row
    return rows


def _candidate_transforms(pairs: Sequence[SavePair], offsets: Iterable[int]) -> list[dict[str, Any]]:
    mapping = _transform_map(pairs, offsets)
    return [mapping[offset] for offset in sorted(mapping)]


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


def _compare_control_transition(
    experiment: dict[str, Any] | None,
    control: dict[str, Any] | None,
) -> dict[str, Any]:
    """Classify one stable byte without erasing distinct bits in the same byte."""
    if experiment is None or control is None:
        return {"status": "ambiguous", "reason": "incomplete-transform"}
    if not experiment.get("sameXorMask") or not control.get("sameXorMask"):
        return {"status": "ambiguous", "reason": "unstable-xor-mask"}
    if not experiment.get("sameBeforeValue") or not control.get("sameBeforeValue"):
        return {"status": "ambiguous", "reason": "unstable-before-value"}
    if experiment.get("beforeValue") != control.get("beforeValue"):
        return {"status": "ambiguous", "reason": "different-before-value"}

    experiment_mask = int(experiment.get("xorMask") or 0)
    control_mask = int(control.get("xorMask") or 0)
    residual = experiment_mask & (~control_mask & 0xFF)
    return {
        "status": "fully-explained" if residual == 0 else "residual",
        "reason": "compatible-stable-xor",
        "experimentXorMask": experiment_mask,
        "controlXorMask": control_mask,
        "residualXorMask": residual,
        "singleBitResidual": bool(residual and residual & (residual - 1) == 0),
        "beforeValue": experiment.get("beforeValue"),
    }


def _classify_control_overlap(
    experiment_pairs: Sequence[SavePair],
    control_pairs: Sequence[SavePair],
    experiment_stable: set[int],
    control_stable: set[int],
) -> tuple[set[int], list[dict[str, Any]], list[dict[str, Any]]]:
    overlap = experiment_stable & control_stable
    experiment_map = _transform_map(experiment_pairs, overlap)
    control_map = _transform_map(control_pairs, overlap)
    fully_explained: set[int] = set()
    residual: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for offset in sorted(overlap):
        comparison = _compare_control_transition(
            experiment_map.get(offset), control_map.get(offset))
        row = {"offset": offset, **comparison}
        if comparison["status"] == "fully-explained":
            fully_explained.add(offset)
        elif comparison["status"] == "residual":
            residual.append(row)
        else:
            ambiguous.append(row)
    return fully_explained, residual, ambiguous


def analyze_controlled_save_pairs(
    experiment_pairs: Sequence[SavePair],
    control_pairs: Sequence[SavePair],
) -> dict[str, Any]:
    """Subtract compatible stable no-op-save transitions from Assess runs."""
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
    fully_explained, residual, ambiguous = _classify_control_overlap(
        experiment_pairs, control_pairs, experiment_stable, control_stable)
    candidates = experiment_stable - fully_explained
    control_only = control_stable - experiment_stable
    transforms = _candidate_transforms(experiment_pairs, candidates)
    single_bit = [row for row in transforms if row["singleBitXor"]]
    single_bit_residual = [row for row in residual if row["singleBitResidual"]]
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
        "fullyExplainedControlByteCount": len(fully_explained),
        "fullyExplainedControlOffsets": sorted(fully_explained)[:MAX_REPORTED_OFFSETS],
        "fullyExplainedControlOffsetsTruncated": len(fully_explained) > MAX_REPORTED_OFFSETS,
        "residualBitCandidates": residual[:MAX_REPORTED_OFFSETS],
        "residualBitCandidatesTruncated": len(residual) > MAX_REPORTED_OFFSETS,
        "ambiguousControlOverlap": ambiguous[:MAX_REPORTED_OFFSETS],
        "ambiguousControlOverlapTruncated": len(ambiguous) > MAX_REPORTED_OFFSETS,
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
        "singleBitResidualCandidateCount": len(single_bit_residual),
        "singleBitResidualCandidates": single_bit_residual[:MAX_REPORTED_OFFSETS],
        "singleBitResidualCandidatesTruncated": len(single_bit_residual) > MAX_REPORTED_OFFSETS,
        "notes": [
            "A byte is removed only when repeated no-op controls reproduce a compatible stable transition from the same byte value and cover every stable Assess XOR bit.",
            "If Assess and no-op saves change different bits of the same byte, residualBitCandidates keeps the unexplained Assess bits instead of discarding the byte.",
            "Ambiguous overlap (different starting byte or unstable XOR) remains a candidate rather than being subtracted.",
            "For the strongest control, duplicate one pre-Assessment save byte-for-byte into every Assess and no-op run before launching the game.",
            "A stable single-bit XOR or residual is compatible with a packed flag but does not establish bit order or EnemyBookID mapping.",
            "No save file is parsed or modified.",
        ],
    }


def analyze_controlled_experiment_groups(
    groups: Mapping[str, Sequence[SavePair]],
    control_pairs: Sequence[SavePair],
) -> dict[str, Any]:
    """Apply mask-aware no-op subtraction to cross-enemy Assess experiments."""
    if not isinstance(groups, Mapping) or not groups:
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
        if name in normalized:
            raise ValueError(f"duplicate Assess experiment group name: {name}")
        normalized[name] = pairs

    group_analysis = analyze_experiment_groups(normalized)
    control = analyze_save_pairs(control_pairs)
    control_stable = _stable_offsets(control_pairs)
    control_map = _transform_map(control_pairs, control_stable)
    stable_by_group = {
        name: _stable_offsets(pairs)
        for name, pairs in normalized.items()
    }

    candidates_by_group: dict[str, set[int]] = {}
    group_transform_maps: dict[str, dict[int, dict[str, Any]]] = {}
    group_rows = []
    for name, pairs in normalized.items():
        stable = stable_by_group[name]
        group_map = _transform_map(pairs, stable)
        group_transform_maps[name] = group_map
        fully_explained: set[int] = set()
        residual: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []
        for offset in sorted(stable & control_stable):
            comparison = _compare_control_transition(
                group_map.get(offset), control_map.get(offset))
            row = {"offset": offset, **comparison}
            if comparison["status"] == "fully-explained":
                fully_explained.add(offset)
            elif comparison["status"] == "residual":
                residual.append(row)
            else:
                ambiguous.append(row)
        candidates = stable - fully_explained
        candidates_by_group[name] = candidates
        group_rows.append({
            "name": name,
            "rawStableByteCount": len(stable),
            "fullyExplainedControlByteCount": len(fully_explained),
            "fullyExplainedControlOffsets": sorted(fully_explained)[:MAX_REPORTED_OFFSETS],
            "residualBitCandidates": residual[:MAX_REPORTED_OFFSETS],
            "ambiguousControlOverlap": ambiguous[:MAX_REPORTED_OFFSETS],
            "controlSubtractedByteCount": len(candidates),
            "controlSubtractedOffsets": sorted(candidates)[:MAX_REPORTED_OFFSETS],
            "controlSubtractedOffsetsTruncated": len(candidates) > MAX_REPORTED_OFFSETS,
        })

    candidate_union = set.union(*candidates_by_group.values()) if candidates_by_group else set()
    shared_candidates = set.intersection(*candidates_by_group.values()) if candidates_by_group else set()
    discriminating_candidates = candidate_union - shared_candidates

    rows_by_name = {row["name"]: row for row in group_rows}
    for name, candidates in candidates_by_group.items():
        others = set.union(*(
            offsets for other_name, offsets in candidates_by_group.items()
            if other_name != name
        )) if len(candidates_by_group) > 1 else set()
        exclusive = candidates - others
        transforms = [
            group_transform_maps[name][offset]
            for offset in sorted(candidates)
            if offset in group_transform_maps[name]
        ]
        rows_by_name[name].update({
            "exclusiveCandidateByteCount": len(exclusive),
            "exclusiveCandidateOffsets": sorted(exclusive)[:MAX_REPORTED_OFFSETS],
            "exclusiveCandidateOffsetsTruncated": len(exclusive) > MAX_REPORTED_OFFSETS,
            "candidateTransforms": transforms[:MAX_REPORTED_OFFSETS],
            "candidateTransformsTruncated": len(transforms) > MAX_REPORTED_OFFSETS,
        })

    different_xor_candidates = []
    for offset in sorted(shared_candidates):
        control_row = control_map.get(offset)
        effective_masks: dict[str, int] = {}
        raw_masks: dict[str, int] = {}
        ambiguous_control = False
        complete = True
        for name in normalized:
            group_row = group_transform_maps[name].get(offset)
            if not group_row or not group_row.get("sameXorMask") or group_row.get("xorMask") in (None, 0):
                complete = False
                break
            raw_mask = int(group_row["xorMask"])
            raw_masks[name] = raw_mask
            effective = raw_mask
            if control_row is not None:
                comparison = _compare_control_transition(group_row, control_row)
                if comparison["status"] == "fully-explained":
                    complete = False
                    break
                if comparison["status"] == "residual":
                    effective = int(comparison["residualXorMask"])
                else:
                    ambiguous_control = True
            if effective == 0:
                complete = False
                break
            effective_masks[name] = effective
        if complete and len(set(effective_masks.values())) > 1:
            different_xor_candidates.append({
                "offset": offset,
                "groupXorMasks": effective_masks,
                "rawGroupXorMasks": raw_masks,
                "controlXorMask": (
                    int(control_row["xorMask"])
                    if control_row and control_row.get("sameXorMask") and control_row.get("xorMask") is not None
                    else None
                ),
                "controlCollisionAmbiguous": ambiguous_control,
                "singleBitMasks": all(mask & (mask - 1) == 0 for mask in effective_masks.values()),
            })

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
        "groups": [rows_by_name[name] for name in normalized],
        "sharedCandidateByteCount": len(shared_candidates),
        "sharedCandidateOffsets": sorted(shared_candidates)[:MAX_REPORTED_OFFSETS],
        "sharedCandidateOffsetsTruncated": len(shared_candidates) > MAX_REPORTED_OFFSETS,
        "discriminatingCandidateByteCount": len(discriminating_candidates),
        "discriminatingCandidateOffsets": sorted(discriminating_candidates)[:MAX_REPORTED_OFFSETS],
        "discriminatingCandidateOffsetsTruncated": len(discriminating_candidates) > MAX_REPORTED_OFFSETS,
        "sameOffsetDifferentXorCandidates": different_xor_candidates[:MAX_REPORTED_OFFSETS],
        "sameOffsetDifferentXorCandidatesTruncated": len(different_xor_candidates) > MAX_REPORTED_OFFSETS,
        "notes": [
            "Cross-enemy candidate offsets are stable inside an enemy's repeated Assess runs after removing only no-op transitions that compatibly explain every changed Assess bit.",
            "Different no-op and Assess bits in the same byte are preserved as residual candidates; incompatible starting values or unstable masks remain ambiguous instead of being erased.",
            "Offsets shared by every enemy after control subtraction can still be Assess-action metadata rather than per-enemy state; enemy-exclusive or different-XOR candidates remain stronger leads.",
            "sameOffsetDifferentXorCandidates reports effective masks after compatible no-op bits are removed, while retaining raw masks for auditability.",
            "Use byte-identical duplicated pre-Assessment baselines whenever possible; baseline.byteIdentical reports whether that condition actually held.",
            "No save file is parsed or modified.",
        ],
    }
