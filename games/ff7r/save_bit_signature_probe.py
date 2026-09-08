"""Bit-level cross-enemy Assessed-state save research for FF7R (#424).

Repeated controlled diffs can produce per-bit candidates after no-op subtraction.
A second, held-out set can now be analyzed independently and compared against the
discovery set so recurrence in the training runs is not mistaken for validation.

This remains read-only research evidence. A repeated bit signature does not prove
EnemyBook indexing, save serialization semantics, or that writing the bit is safe.
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
