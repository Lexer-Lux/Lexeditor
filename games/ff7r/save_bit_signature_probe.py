"""Bit-level cross-enemy Assessed-state save research for FF7R (#424).

The byte-level controlled diff probe can identify offsets that recur across
Assessment experiments, including cases where different enemies toggle different
XOR masks in the same byte. This module goes one step further and turns those
stable, control-subtracted masks into explicit per-bit signatures.

This remains read-only research evidence. A unique bit signature does not prove
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
