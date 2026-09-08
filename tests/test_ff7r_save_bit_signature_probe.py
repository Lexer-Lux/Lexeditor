from games.ff7r.save_bit_signature_probe import (
    analyze_controlled_bit_signatures,
    assess_indexed_bitset_layout,
    validate_controlled_bit_signatures,
)
from games.ff7r.save_diff_probe import SavePair


def _pair(*changes: tuple[int, int], label: str = "") -> SavePair:
    before = bytearray(96)
    after = bytearray(before)
    for offset, value in changes:
        after[offset] = value
    return SavePair(bytes(before), bytes(after), label)


def _pair_from(before_values: dict[int, int], after_values: dict[int, int], *, label: str = "") -> SavePair:
    before = bytearray(96)
    after = bytearray(96)
    for offset, value in before_values.items():
        before[offset] = value
        after[offset] = value
    for offset, value in after_values.items():
        after[offset] = value
    return SavePair(bytes(before), bytes(after), label)


def test_control_bits_are_removed_before_distinct_enemy_bit_signatures_are_ranked():
    groups = {
        "enemy-a": [
            _pair((12, 0x05), (80, 1), label="a1"),
            _pair((12, 0x05), (81, 2), label="a2"),
        ],
        "enemy-b": [
            _pair((12, 0x06), (82, 3), label="b1"),
            _pair((12, 0x06), (83, 4), label="b2"),
        ],
    }
    controls = [
        _pair((12, 0x04), (84, 5), label="noop1"),
        _pair((12, 0x04), (85, 6), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    assert result["implementationReady"] is False
    assert result["candidateOffsets"] == [12]
    assert result["unresolvedOffsets"] == []
    assert result["packedFlagByteCandidateCount"] == 1
    assert result["packedFlagByteCandidates"] == [{
        "offset": 12,
        "groupBits": {"enemy-a": 0, "enemy-b": 1},
        "groupMasks": {"enemy-a": 0x01, "enemy-b": 0x02},
        "rawGroupMasks": {"enemy-a": 0x05, "enemy-b": 0x06},
        "controlXorMask": 0x04,
    }]
    assert result["exclusiveSingleBitFlagCandidates"] == [
        {
            "group": "enemy-a",
            "offset": 12,
            "bit": 0,
            "mask": 0x01,
            "rawMask": 0x05,
            "controlXorMask": 0x04,
        },
        {
            "group": "enemy-b",
            "offset": 12,
            "bit": 1,
            "mask": 0x02,
            "rawMask": 0x06,
            "controlXorMask": 0x04,
        },
    ]


def test_different_control_start_value_blocks_bit_signature_promotion():
    groups = {
        "enemy-a": [
            _pair_from({12: 0x00}, {12: 0x01}, label="a1"),
            _pair_from({12: 0x00}, {12: 0x01}, label="a2"),
        ],
        "enemy-b": [
            _pair((20, 0x04), label="b1"),
            _pair((20, 0x04), label="b2"),
        ],
    }
    controls = [
        _pair_from({12: 0x02}, {12: 0x03}, label="noop1"),
        _pair_from({12: 0x02}, {12: 0x03}, label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    assert result["unresolvedOffsets"] == [12]
    assert result["candidateOffsets"] == [20]
    assert result["packedFlagByteCandidateCount"] == 0
    assert result["exclusiveSingleBitFlagCandidates"] == [{
        "group": "enemy-b",
        "offset": 20,
        "bit": 2,
        "mask": 0x04,
        "rawMask": 0x04,
        "controlXorMask": None,
    }]


def test_shared_byte_with_multibit_enemy_mask_is_not_called_packed_flag_byte():
    groups = {
        "enemy-a": [
            _pair((12, 0x03), label="a1"),
            _pair((12, 0x03), label="a2"),
        ],
        "enemy-b": [
            _pair((12, 0x04), label="b1"),
            _pair((12, 0x04), label="b2"),
        ],
    }
    controls = [
        _pair((70, 0x80), label="noop1"),
        _pair((70, 0x80), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)
    signature = result["offsetSignatures"][0]

    assert signature["offset"] == 12
    assert signature["allActiveMasksSingleBit"] is False
    assert signature["distinctActiveMasks"] is True
    assert signature["packedDistinctSingleBitCandidate"] is False
    assert result["packedFlagByteCandidateCount"] == 0
    assert result["exclusiveSingleBitFlagCandidates"] == [{
        "group": "enemy-b",
        "offset": 12,
        "bit": 2,
        "mask": 0x04,
        "rawMask": 0x04,
        "controlXorMask": None,
    }]


def test_control_fully_explained_byte_drops_out_of_bit_candidates():
    groups = {
        "enemy-a": [
            _pair((12, 0x04), label="a1"),
            _pair((12, 0x04), label="a2"),
        ],
        "enemy-b": [
            _pair((20, 0x02), label="b1"),
            _pair((20, 0x02), label="b2"),
        ],
    }
    controls = [
        _pair((12, 0x04), label="noop1"),
        _pair((12, 0x04), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    assert result["candidateOffsets"] == [20]
    assert all(row["offset"] != 12 for row in result["offsetSignatures"])
    assert result["exclusiveSingleBitFlagCandidates"] == [{
        "group": "enemy-b",
        "offset": 20,
        "bit": 1,
        "mask": 0x02,
        "rawMask": 0x02,
        "controlXorMask": None,
    }]
    assert result["implementationReady"] is False


def test_holdout_validation_confirms_same_control_subtracted_enemy_bits():
    discovery = {
        "enemy-a": [_pair((12, 0x05), (80, 1)), _pair((12, 0x05), (81, 2))],
        "enemy-b": [_pair((12, 0x06), (82, 3)), _pair((12, 0x06), (83, 4))],
    }
    holdout = {
        "enemy-a": [_pair((12, 0x05), (86, 7)), _pair((12, 0x05), (87, 8))],
        "enemy-b": [_pair((12, 0x06), (88, 9)), _pair((12, 0x06), (89, 10))],
    }
    controls = [_pair((12, 0x04), (84, 5)), _pair((12, 0x04), (85, 6))]

    result = validate_controlled_bit_signatures(discovery, controls, holdout)

    assert result["discoveryCandidateCount"] == 2
    assert result["holdoutCandidateCount"] == 2
    assert result["confirmedCandidates"] == [
        {"group": "enemy-a", "offset": 12, "bit": 0, "mask": 0x01},
        {"group": "enemy-b", "offset": 12, "bit": 1, "mask": 0x02},
    ]
    assert result["missingCandidates"] == []
    assert result["unexpectedCandidates"] == []
    assert result["missingHoldoutGroups"] == []
    assert result["allDiscoveryCandidatesConfirmed"] is True
    assert result["exactHoldoutAgreement"] is True
    assert result["implementationReady"] is False


def test_holdout_validation_exposes_missing_changed_and_unexpected_bits():
    discovery = {
        "enemy-a": [_pair((12, 0x01)), _pair((12, 0x01))],
        "enemy-b": [_pair((12, 0x02)), _pair((12, 0x02))],
    }
    holdout = {
        "enemy-a": [_pair((12, 0x04)), _pair((12, 0x04))],
        "enemy-b": [_pair((12, 0x02)), _pair((12, 0x02))],
    }
    controls = [_pair((70, 0x80)), _pair((70, 0x80))]

    result = validate_controlled_bit_signatures(discovery, controls, holdout)

    assert result["confirmedCandidates"] == [
        {"group": "enemy-b", "offset": 12, "bit": 1, "mask": 0x02},
    ]
    assert result["missingCandidates"] == [
        {"group": "enemy-a", "offset": 12, "bit": 0, "mask": 0x01},
    ]
    assert result["unexpectedCandidates"] == [
        {"group": "enemy-a", "offset": 12, "bit": 2, "mask": 0x04},
    ]
    assert result["allDiscoveryCandidatesConfirmed"] is False
    assert result["exactHoldoutAgreement"] is False


def test_holdout_validation_requires_group_coverage_for_full_confirmation():
    discovery = {
        "enemy-a": [_pair((12, 0x01)), _pair((12, 0x01))],
        "enemy-b": [_pair((12, 0x02)), _pair((12, 0x02))],
    }
    holdout = {
        "enemy-a": [_pair((12, 0x01)), _pair((12, 0x01))],
    }
    controls = [_pair((70, 0x80)), _pair((70, 0x80))]

    result = validate_controlled_bit_signatures(discovery, controls, holdout)

    assert result["missingHoldoutGroups"] == ["enemy-b"]
    assert result["allDiscoveryCandidatesConfirmed"] is False
    assert result["exactHoldoutAgreement"] is False


def test_enemybook_indices_detect_contiguous_bitset_across_byte_boundary():
    groups = {
        "enemy-a": [_pair((12, 0x40)), _pair((12, 0x40))],
        "enemy-b": [_pair((12, 0x80)), _pair((12, 0x80))],
        "enemy-c": [_pair((13, 0x01)), _pair((13, 0x01))],
    }
    controls = [_pair((70, 0x20)), _pair((70, 0x20))]
    bit_analysis = analyze_controlled_bit_signatures(groups, controls)

    result = assess_indexed_bitset_layout(
        bit_analysis,
        {"enemy-a": 6, "enemy-b": 7, "enemy-c": 8},
    )

    assert result["candidateSource"] == "discovery"
    assert result["mappedGroupCount"] == 3
    assert result["bestSupportGroupCount"] == 3
    assert result["uniqueBestLayout"] is True
    assert result["uniqueBestBaseBit"] == 96
    assert result["exactMappedAgreement"] is True
    assert result["exactBaseBit"] == 96
    layout = result["layoutCandidates"][0]
    assert layout["baseByteOffset"] == 12
    assert layout["baseBitInByte"] == 0
    assert layout["supportingGroups"] == ["enemy-a", "enemy-b", "enemy-c"]
    assert layout["predictedLocations"]["enemy-c"] == {
        "enemyBookId": 8,
        "absoluteBit": 104,
        "offset": 13,
        "bit": 0,
        "mask": 0x01,
    }
    assert result["implementationReady"] is False


def test_enemybook_index_mismatch_does_not_promote_single_group_coincidences():
    groups = {
        "enemy-a": [_pair((12, 0x01)), _pair((12, 0x01))],
        "enemy-b": [_pair((12, 0x02)), _pair((12, 0x02))],
    }
    controls = [_pair((70, 0x20)), _pair((70, 0x20))]
    bit_analysis = analyze_controlled_bit_signatures(groups, controls)

    result = assess_indexed_bitset_layout(
        bit_analysis,
        {"enemy-a": 0, "enemy-b": 2},
    )

    assert result["bestSupportGroupCount"] == 1
    assert result["uniqueBestLayout"] is False
    assert result["uniqueBestBaseBit"] is None
    assert result["exactMappedAgreement"] is False
    assert all(
        row["plausibleContiguousBitsetCandidate"] is False
        for row in result["layoutCandidates"]
    )


def test_indexed_layout_uses_only_holdout_confirmed_candidates_when_available():
    validation = {
        "confirmedCandidates": [
            {"group": "enemy-a", "offset": 20, "bit": 2, "mask": 0x04},
            {"group": "enemy-b", "offset": 20, "bit": 3, "mask": 0x08},
        ],
        "discovery": {
            "exclusiveSingleBitFlagCandidates": [
                {"group": "enemy-a", "offset": 1, "bit": 0, "mask": 0x01},
            ],
        },
    }

    result = assess_indexed_bitset_layout(
        validation,
        {"enemy-a": 2, "enemy-b": 3},
    )

    assert result["candidateSource"] == "holdout-confirmed"
    assert result["exactMappedAgreement"] is True
    assert result["exactBaseBit"] == 160


def test_indexed_layout_rejects_duplicate_enemybook_ids():
    analysis = {"exclusiveSingleBitFlagCandidates": []}
    try:
        assess_indexed_bitset_layout(analysis, {"enemy-a": 3, "enemy-b": 3})
    except ValueError as error:
        assert "assigned to both" in str(error)
    else:
        raise AssertionError("expected duplicate EnemyBookID ValueError")
