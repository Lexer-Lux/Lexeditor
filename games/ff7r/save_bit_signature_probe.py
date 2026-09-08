"""Bit-level cross-enemy Assessed-state save research for FF7R (#424).

Repeated controlled diffs can produce per-bit candidates after no-op subtraction.
A second, held-out set can be analyzed independently and compared against the
discovery set so recurrence in the training runs is not mistaken for validation.
Known EnemyBookIDs can additionally be supplied to test a narrow hypothesis: the
reproduced bits form one contiguous bitset indexed by EnemyBookID.

This remains read-only research evidence. A repeated bit signature or contiguous
indexed layout does not prove save serialization semantics or that writing it is
safe.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .save_control_probe import (
    _compare_control_transition,
    _stable_offsets,
    _transform_map,
    analyze_controlled_experiment_groups,
)
from .save_diff_probe import MAX_REPORTED_OFFSETS, SavePair


def _is_single_bit(mask: int) -> bool:
    return mask != 0 and mask & (mask - 1) == 0


def _bit_index(mask: int) -> int:
    return mask.bit_length() - 1


def analyze_controlled_bit_signatures(
    groups: Mapping[str, Sequence[SavePair]],
    control_pairs: Sequence[SavePair],
) -> dict[str, Any]:
    """Resolve stable cross-enemy byte diffs into fail-closed bit signatures."""
    controlled = analyze_controlled_experiment_groups(groups, control_pairs)
    normalized = {
        str(raw_name).strip(): tuple(raw_pairs)
        for raw_name, raw_pairs in groups.items()
    }

    control_stable = _stable_offsets(control_pairs)
    control_map = _transform_map(control_pairs, control_stable)

    effective_by_group: dict[str, dict[int, int]] = {}
    raw_by_group: dict[str, dict[int, int]] = {}
    unresolved_by_group: dict[str, dict[int, str]] = {}

    for name, pairs in normalized.items():
        stable = _stable_offsets(pairs)
        transform_map = _transform_map(pairs, stable)
        effective: dict[int, int] = {}
        raw_masks: dict[int, int] = {}
        unresolved: dict[int, str] = {}

        for offset in sorted(stable):
            row = transform_map.get(offset)
            if row is None:
                unresolved[offset] = "incomplete-transform"
                continue
            if not row.get("sameXorMask") or row.get("xorMask") in (None, 0):
                unresolved[offset] = "unstable-xor-mask"
                continue
            if not row.get("sameBeforeValue"):
                unresolved[offset] = "unstable-before-value"
                continue

            raw_mask = int(row["xorMask"])
            raw_masks[offset] = raw_mask
            effective_mask = raw_mask
            control_row = control_map.get(offset)
            if control_row is not None:
                comparison = _compare_control_transition(row, control_row)
                status = comparison.get("status")
                if status == "fully-explained":
                    continue
                if status == "residual":
                    effective_mask = int(comparison.get("residualXorMask") or 0)
                else:
                    unresolved[offset] = str(comparison.get("reason") or "ambiguous-control")
                    continue

            if effective_mask:
                effective[offset] = effective_mask

        effective_by_group[name] = effective
        raw_by_group[name] = raw_masks
        unresolved_by_group[name] = unresolved

    candidate_offsets = sorted(set().union(*(
        set(offsets) for offsets in effective_by_group.values()
    ))) if effective_by_group else []
    unresolved_offsets = sorted(set().union(*(
        set(offsets) for offsets in unresolved_by_group.values()
    ))) if unresolved_by_group else []

    offset_rows: list[dict[str, Any]] = []
    exclusive_single_bits: list[dict[str, Any]] = []
    packed_flag_bytes: list[dict[str, Any]] = []

    for offset in candidate_offsets:
        group_masks = {
            name: masks[offset]
            for name, masks in effective_by_group.items()
            if offset in masks
        }
        raw_masks = {
            name: masks[offset]
            for name, masks in raw_by_group.items()
            if offset in masks
        }
        unresolved_groups = {
            name: reasons[offset]
            for name, reasons in unresolved_by_group.items()
            if offset in reasons
        }
        control_row = control_map.get(offset)
        control_mask = (
            int(control_row["xorMask"])
            if control_row
            and control_row.get("sameXorMask")
            and control_row.get("xorMask") is not None
            else None
        )

        bit_rows = []
        for bit in range(8):
            mask = 1 << bit
            owners = sorted(name for name, value in group_masks.items() if value & mask)
            if not owners:
                continue
            bit_rows.append({
                "bit": bit,
                "mask": mask,
                "groups": owners,
                "groupCount": len(owners),
            })

            if len(owners) == 1 and not unresolved_groups:
                owner = owners[0]
                owner_mask = group_masks[owner]
                if _is_single_bit(owner_mask):
                    exclusive_single_bits.append({
                        "group": owner,
                        "offset": offset,
                        "bit": bit,
                        "mask": mask,
                        "rawMask": raw_masks.get(owner),
                        "controlXorMask": control_mask,
                    })

        masks = list(group_masks.values())
        packed = bool(
            len(group_masks) >= 2
            and not unresolved_groups
            and all(_is_single_bit(mask) for mask in masks)
            and len(set(masks)) == len(masks)
        )
        if packed:
            packed_flag_bytes.append({
                "offset": offset,
                "groupBits": {
                    name: _bit_index(mask)
                    for name, mask in sorted(group_masks.items())
                },
                "groupMasks": dict(sorted(group_masks.items())),
                "rawGroupMasks": dict(sorted(raw_masks.items())),
                "controlXorMask": control_mask,
            })

        offset_rows.append({
            "offset": offset,
            "groupMasks": dict(sorted(group_masks.items())),
            "rawGroupMasks": dict(sorted(raw_masks.items())),
            "unresolvedGroups": dict(sorted(unresolved_groups.items())),
            "controlXorMask": control_mask,
            "activeGroupCount": len(group_masks),
            "allActiveMasksSingleBit": bool(masks) and all(_is_single_bit(mask) for mask in masks),
            "distinctActiveMasks": len(set(masks)) == len(masks),
            "packedDistinctSingleBitCandidate": packed,
            "bits": bit_rows,
        })

    exclusive_single_bits.sort(key=lambda row: (row["offset"], row["bit"], row["group"]))
    packed_flag_bytes.sort(key=lambda row: row["offset"])

    return {
        "implementationReady": False,
        "controlled": controlled,
        "candidateOffsetCount": len(candidate_offsets),
        "candidateOffsets": candidate_offsets[:MAX_REPORTED_OFFSETS],
        "candidateOffsetsTruncated": len(candidate_offsets) > MAX_REPORTED_OFFSETS,
        "unresolvedOffsetCount": len(unresolved_offsets),
        "unresolvedOffsets": unresolved_offsets[:MAX_REPORTED_OFFSETS],
        "unresolvedOffsetsTruncated": len(unresolved_offsets) > MAX_REPORTED_OFFSETS,
        "offsetSignatures": offset_rows[:MAX_REPORTED_OFFSETS],
        "offsetSignaturesTruncated": len(offset_rows) > MAX_REPORTED_OFFSETS,
        "exclusiveSingleBitFlagCandidateCount": len(exclusive_single_bits),
        "exclusiveSingleBitFlagCandidates": exclusive_single_bits[:MAX_REPORTED_OFFSETS],
        "exclusiveSingleBitFlagCandidatesTruncated": len(exclusive_single_bits) > MAX_REPORTED_OFFSETS,
        "packedFlagByteCandidateCount": len(packed_flag_bytes),
        "packedFlagByteCandidates": packed_flag_bytes[:MAX_REPORTED_OFFSETS],
        "packedFlagByteCandidatesTruncated": len(packed_flag_bytes) > MAX_REPORTED_OFFSETS,
        "notes": [
            "Bit signatures are computed only from repeated stable XOR masks with stable starting byte values.",
            "Compatible no-op XOR bits are subtracted before per-bit signatures are formed; ambiguous control collisions block trusted per-bit promotion at that offset.",
            "A packedFlagByteCandidate requires at least two enemy groups to toggle distinct single bits in the same byte with no unresolved group evidence at that offset.",
            "exclusiveSingleBitFlagCandidates are high-value mapping leads, not proof of EnemyBook indexing or authorization to mutate a save.",
            "The probe never parses or writes FF7R save structures.",
        ],
    }


def _candidate_key(row: Mapping[str, Any]) -> tuple[str, int, int]:
    return (
        str(row.get("group", "")),
        int(row.get("offset", -1)),
        int(row.get("mask", 0)),
    )


def _key_row(key: tuple[str, int, int]) -> dict[str, Any]:
    group, offset, mask = key
    return {
        "group": group,
        "offset": offset,
        "bit": _bit_index(mask) if _is_single_bit(mask) else None,
        "mask": mask,
    }


def validate_controlled_bit_signatures(
    discovery_groups: Mapping[str, Sequence[SavePair]],
    control_pairs: Sequence[SavePair],
    holdout_groups: Mapping[str, Sequence[SavePair]],
) -> dict[str, Any]:
    """Compare independently analyzed discovery and held-out Assess experiments."""
    discovery = analyze_controlled_bit_signatures(discovery_groups, control_pairs)
    holdout = analyze_controlled_bit_signatures(holdout_groups, control_pairs)

    discovery_keys = {
        _candidate_key(row)
        for row in discovery.get("exclusiveSingleBitFlagCandidates", ())
    }
    holdout_keys = {
        _candidate_key(row)
        for row in holdout.get("exclusiveSingleBitFlagCandidates", ())
    }
    discovery_names = {str(name).strip() for name in discovery_groups}
    holdout_names = {str(name).strip() for name in holdout_groups}

    confirmed = sorted(discovery_keys & holdout_keys)
    missing = sorted(discovery_keys - holdout_keys)
    unexpected = sorted(holdout_keys - discovery_keys)
    missing_groups = sorted(discovery_names - holdout_names)
    extra_groups = sorted(holdout_names - discovery_names)
    all_confirmed = bool(discovery_keys) and not missing and not missing_groups
    exact_agreement = bool(all_confirmed and not unexpected and not extra_groups)

    return {
        "implementationReady": False,
        "discovery": discovery,
        "holdout": holdout,
        "discoveryCandidateCount": len(discovery_keys),
        "holdoutCandidateCount": len(holdout_keys),
        "confirmedCandidateCount": len(confirmed),
        "confirmedCandidates": [_key_row(key) for key in confirmed],
        "missingCandidateCount": len(missing),
        "missingCandidates": [_key_row(key) for key in missing],
        "unexpectedCandidateCount": len(unexpected),
        "unexpectedCandidates": [_key_row(key) for key in unexpected],
        "missingHoldoutGroups": missing_groups,
        "extraHoldoutGroups": extra_groups,
        "allDiscoveryCandidatesConfirmed": all_confirmed,
        "exactHoldoutAgreement": exact_agreement,
        "notes": [
            "Discovery and holdout groups are analyzed independently with the same no-op control subtraction rules before candidate sets are compared.",
            "A confirmed candidate must reproduce the same enemy/group, byte offset and effective single-bit mask in the held-out experiments.",
            "The caller must ensure holdout saves are genuinely independent runs; this function cannot detect reused files or experimental leakage.",
            "Even exact held-out recurrence remains format-agnostic evidence only and does not prove EnemyBook index ordering or authorize save mutation.",
        ],
    }


def _normalize_enemy_indices(enemy_indices: Mapping[str, int]) -> dict[str, int]:
    if not isinstance(enemy_indices, Mapping):
        raise TypeError("enemy indices must be a mapping")
    normalized: dict[str, int] = {}
    used_indices: dict[int, str] = {}
    for raw_name, raw_index in enemy_indices.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("enemy/group names cannot be empty")
        if name in normalized:
            raise ValueError(f"duplicate enemy/group name: {name}")
        if isinstance(raw_index, bool) or not isinstance(raw_index, int) or raw_index < 0:
            raise ValueError(f"EnemyBookID for {name} must be a non-negative integer")
        previous = used_indices.get(raw_index)
        if previous is not None:
            raise ValueError(
                f"EnemyBookID {raw_index} is assigned to both {previous} and {name}"
            )
        normalized[name] = raw_index
        used_indices[raw_index] = name
    if not normalized:
        raise ValueError("at least one EnemyBookID mapping is required")
    return normalized


def assess_indexed_bitset_layout(
    bit_analysis: Mapping[str, Any],
    enemy_indices: Mapping[str, int],
) -> dict[str, Any]:
    """Test whether reproduced per-enemy bits fit one EnemyBookID-indexed bitset.

    This does not infer EnemyBookIDs. The caller supplies independently known IDs
    and this function asks whether candidate save-bit absolute positions satisfy
    ``absolute_bit = base_bit + EnemyBookID`` across multiple enemies.
    """
    if not isinstance(bit_analysis, Mapping):
        raise TypeError("bit analysis must be a mapping")
    indices = _normalize_enemy_indices(enemy_indices)
    if "confirmedCandidates" in bit_analysis:
        source_field = "confirmedCandidates"
        source_kind = "holdout-confirmed"
    else:
        source_field = "exclusiveSingleBitFlagCandidates"
        source_kind = "discovery"
    raw_candidates = bit_analysis.get(source_field, ())
    if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes, bytearray)):
        raise ValueError(f"{source_field} must be a candidate sequence")

    candidate_rows: list[dict[str, Any]] = []
    candidate_counts: dict[str, int] = {name: 0 for name in indices}
    layouts: dict[int, list[dict[str, Any]]] = {}
    for raw_row in raw_candidates:
        if not isinstance(raw_row, Mapping):
            raise ValueError(f"{source_field} contains a non-object candidate")
        group = str(raw_row.get("group", "")).strip()
        if group not in indices:
            continue
        offset = raw_row.get("offset")
        mask = raw_row.get("mask")
        bit = raw_row.get("bit")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError(f"candidate offset for {group} must be a non-negative integer")
        if isinstance(mask, bool) or not isinstance(mask, int) or not _is_single_bit(mask) or mask > 0x80:
            raise ValueError(f"candidate mask for {group} must be one byte-wide single bit")
        expected_bit = _bit_index(mask)
        if bit is None:
            bit = expected_bit
        if isinstance(bit, bool) or not isinstance(bit, int) or bit != expected_bit or not 0 <= bit <= 7:
            raise ValueError(f"candidate bit/mask disagree for {group}")

        enemy_index = indices[group]
        absolute_bit = offset * 8 + bit
        base_bit = absolute_bit - enemy_index
        row = {
            "group": group,
            "enemyBookId": enemy_index,
            "offset": offset,
            "bit": bit,
            "mask": mask,
            "absoluteBit": absolute_bit,
            "candidateBaseBit": base_bit,
            "baseIsNonNegative": base_bit >= 0,
        }
        candidate_rows.append(row)
        candidate_counts[group] += 1
        if base_bit >= 0:
            layouts.setdefault(base_bit, []).append(row)

    mapped_groups = sorted(indices)
    groups_with_candidates = sorted(name for name, count in candidate_counts.items() if count)
    groups_without_candidates = sorted(name for name, count in candidate_counts.items() if not count)
    layout_rows: list[dict[str, Any]] = []
    for base_bit, support in layouts.items():
        supporting_groups = sorted({row["group"] for row in support})
        missing_groups = sorted(set(mapped_groups) - set(supporting_groups))
        conflicting_groups = sorted(
            name
            for name in missing_groups
            if candidate_counts.get(name, 0) > 0
        )
        extra_candidate_groups = sorted(
            name
            for name in supporting_groups
            if candidate_counts.get(name, 0) != 1
        )
        predicted = {
            name: {
                "enemyBookId": enemy_index,
                "absoluteBit": base_bit + enemy_index,
                "offset": (base_bit + enemy_index) // 8,
                "bit": (base_bit + enemy_index) % 8,
                "mask": 1 << ((base_bit + enemy_index) % 8),
            }
            for name, enemy_index in sorted(indices.items())
        }
        exact = bool(
            len(supporting_groups) == len(mapped_groups)
            and not missing_groups
            and not extra_candidate_groups
        )
        layout_rows.append({
            "baseBit": base_bit,
            "baseByteOffset": base_bit // 8,
            "baseBitInByte": base_bit % 8,
            "supportGroupCount": len(supporting_groups),
            "mappedGroupCount": len(mapped_groups),
            "supportingGroups": supporting_groups,
            "missingGroups": missing_groups,
            "conflictingGroups": conflicting_groups,
            "extraCandidateGroups": extra_candidate_groups,
            "supportFraction": len(supporting_groups) / len(mapped_groups),
            "plausibleContiguousBitsetCandidate": len(supporting_groups) >= 2,
            "exactMappedAgreement": exact,
            "predictedLocations": predicted,
        })

    layout_rows.sort(
        key=lambda row: (
            not row["exactMappedAgreement"],
            -row["supportGroupCount"],
            row["baseBit"],
        )
    )
    best_support = max((row["supportGroupCount"] for row in layout_rows), default=0)
    best_rows = [row for row in layout_rows if row["supportGroupCount"] == best_support]
    exact_rows = [row for row in layout_rows if row["exactMappedAgreement"]]
    unique_best = bool(best_support >= 2 and len(best_rows) == 1)

    return {
        "implementationReady": False,
        "candidateSource": source_kind,
        "candidateField": source_field,
        "enemyBookIds": dict(sorted(indices.items())),
        "mappedGroupCount": len(mapped_groups),
        "groupsWithCandidates": groups_with_candidates,
        "groupsWithoutCandidates": groups_without_candidates,
        "candidateCountByGroup": dict(sorted(candidate_counts.items())),
        "mappedCandidateCount": len(candidate_rows),
        "mappedCandidates": candidate_rows[:MAX_REPORTED_OFFSETS],
        "mappedCandidatesTruncated": len(candidate_rows) > MAX_REPORTED_OFFSETS,
        "layoutCandidateCount": len(layout_rows),
        "layoutCandidates": layout_rows[:MAX_REPORTED_OFFSETS],
        "layoutCandidatesTruncated": len(layout_rows) > MAX_REPORTED_OFFSETS,
        "bestSupportGroupCount": best_support,
        "uniqueBestLayout": unique_best,
        "uniqueBestBaseBit": best_rows[0]["baseBit"] if unique_best else None,
        "exactLayoutCount": len(exact_rows),
        "exactMappedAgreement": len(exact_rows) == 1,
        "exactBaseBit": exact_rows[0]["baseBit"] if len(exact_rows) == 1 else None,
        "notes": [
            "EnemyBookIDs are caller-supplied independent evidence; this function never infers IDs from save offsets or group labels.",
            "A layout candidate fits absolute_bit = base_bit + EnemyBookID. Crossing byte boundaries is expected for a contiguous packed bitset.",
            "At least two mapped enemies must support the same base before a layout is called plausible; exact agreement requires every mapped enemy to have exactly one reproduced candidate at its predicted bit.",
            "A unique or exact layout is still correlation evidence only. Live read semantics, save format ownership and write safety remain unvalidated.",
        ],
    }
