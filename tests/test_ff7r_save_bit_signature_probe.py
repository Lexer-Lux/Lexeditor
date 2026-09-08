from games.ff7r.save_bit_signature_probe import analyze_controlled_bit_signatures
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
