from games.ff7r.save_control_probe import (
    analyze_controlled_experiment_groups,
    analyze_controlled_save_pairs,
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


def test_noop_control_subtracts_repeatable_save_noise_from_assess_candidates():
    experiment = [
        _pair((10, 0x01), (70, 0x80), (80, 1), label="assess-1"),
        _pair((10, 0x01), (70, 0x80), (81, 2), label="assess-2"),
        _pair((10, 0x01), (70, 0x80), (82, 3), label="assess-3"),
    ]
    controls = [
        _pair((70, 0x80), (83, 4), label="noop-1"),
        _pair((70, 0x80), (84, 5), label="noop-2"),
        _pair((70, 0x80), (85, 6), label="noop-3"),
    ]

    result = analyze_controlled_save_pairs(experiment, controls)

    assert result["experimentStableByteCount"] == 2
    assert result["controlStableByteCount"] == 1
    assert result["controlOverlapOffsets"] == [70]
    assert result["fullyExplainedControlOffsets"] == [70]
    assert result["candidateOffsets"] == [10]
    assert result["candidateRuns"] == [{"start": 10, "end": 11, "length": 1}]
    assert result["singleBitCandidateCount"] == 1
    assert result["singleBitCandidates"][0]["xorMask"] == 0x01
    assert result["baseline"]["byteIdentical"] is True


def test_control_subtraction_keeps_same_offset_when_noop_transition_is_not_stable():
    experiment = [
        _pair((12, 0x04), label="assess-1"),
        _pair((12, 0x04), label="assess-2"),
    ]
    controls = [
        _pair((12, 0x20), label="noop-1"),
        _pair((13, 0x20), label="noop-2"),
    ]

    result = analyze_controlled_save_pairs(experiment, controls)

    assert result["controlStableByteCount"] == 0
    assert result["candidateOffsets"] == [12]


def test_control_subtraction_preserves_unexplained_bits_in_same_byte():
    experiment = [
        _pair((12, 0x05), label="assess-1"),
        _pair((12, 0x05), label="assess-2"),
    ]
    controls = [
        _pair((12, 0x04), label="noop-1"),
        _pair((12, 0x04), label="noop-2"),
    ]

    result = analyze_controlled_save_pairs(experiment, controls)

    assert result["candidateOffsets"] == [12]
    assert result["fullyExplainedControlOffsets"] == []
    assert result["residualBitCandidates"] == [{
        "offset": 12,
        "status": "residual",
        "reason": "compatible-stable-xor",
        "experimentXorMask": 0x05,
        "controlXorMask": 0x04,
        "residualXorMask": 0x01,
        "singleBitResidual": True,
        "beforeValue": 0,
    }]
    assert result["singleBitResidualCandidateCount"] == 1


def test_control_overlap_with_different_before_value_is_ambiguous_not_subtracted():
    experiment = [
        _pair_from({12: 0x00}, {12: 0x01}, label="assess-1"),
        _pair_from({12: 0x00}, {12: 0x01}, label="assess-2"),
    ]
    controls = [
        _pair_from({12: 0x02}, {12: 0x03}, label="noop-1"),
        _pair_from({12: 0x02}, {12: 0x03}, label="noop-2"),
    ]

    result = analyze_controlled_save_pairs(experiment, controls)

    assert result["candidateOffsets"] == [12]
    assert result["fullyExplainedControlOffsets"] == []
    assert result["ambiguousControlOverlap"] == [{
        "offset": 12,
        "status": "ambiguous",
        "reason": "different-before-value",
    }]


def test_control_report_flags_nonidentical_pre_run_baselines_without_hiding_results():
    experiment = [_pair((10, 1), label="assess")]
    control_before = bytearray(96)
    control_before[5] = 9
    control_after = bytearray(control_before)
    control_after[70] = 0x80
    controls = [SavePair(bytes(control_before), bytes(control_after), "noop")]

    result = analyze_controlled_save_pairs(experiment, controls)

    assert result["baseline"]["byteIdentical"] is False
    assert result["baseline"]["mismatchedSamples"] == [1]
    assert result["candidateOffsets"] == [10]


def test_control_analysis_requires_both_experiment_and_noop_pairs():
    pair = _pair((10, 1))
    for experiments, controls, text in (
        ([], [pair], "Assess"),
        ([pair], [], "no-op"),
    ):
        try:
            analyze_controlled_save_pairs(experiments, controls)
        except ValueError as error:
            assert text in str(error)
        else:
            raise AssertionError("expected ValueError")


def test_cross_enemy_controls_remove_shared_noop_noise_before_discrimination():
    groups = {
        "enemy-a": [
            _pair((10, 0x01), (70, 0x80), (80, 1), label="a1"),
            _pair((10, 0x01), (70, 0x80), (81, 2), label="a2"),
        ],
        "enemy-b": [
            _pair((20, 0x04), (70, 0x80), (82, 3), label="b1"),
            _pair((20, 0x04), (70, 0x80), (83, 4), label="b2"),
        ],
    }
    controls = [
        _pair((70, 0x80), (84, 5), label="noop1"),
        _pair((70, 0x80), (85, 6), label="noop2"),
    ]

    result = analyze_controlled_experiment_groups(groups, controls)

    assert result["controlStableOffsets"] == [70]
    assert result["sharedCandidateOffsets"] == []
    assert result["discriminatingCandidateOffsets"] == [10, 20]
    rows = {row["name"]: row for row in result["groups"]}
    assert rows["enemy-a"]["exclusiveCandidateOffsets"] == [10]
    assert rows["enemy-b"]["exclusiveCandidateOffsets"] == [20]
    assert rows["enemy-a"]["fullyExplainedControlOffsets"] == [70]
    assert rows["enemy-b"]["fullyExplainedControlOffsets"] == [70]


def test_cross_enemy_control_keeps_different_xor_bitset_lead_when_noop_does_not_touch_byte():
    groups = {
        "enemy-a": [
            _pair((12, 0x01), (70, 0x80), (80, 1)),
            _pair((12, 0x01), (70, 0x80), (81, 2)),
        ],
        "enemy-b": [
            _pair((12, 0x04), (70, 0x80), (82, 3)),
            _pair((12, 0x04), (70, 0x80), (83, 4)),
        ],
    }
    controls = [
        _pair((70, 0x80), (84, 5)),
        _pair((70, 0x80), (85, 6)),
    ]

    result = analyze_controlled_experiment_groups(groups, controls)

    assert result["sharedCandidateOffsets"] == [12]
    assert result["sameOffsetDifferentXorCandidates"] == [{
        "offset": 12,
        "groupXorMasks": {"enemy-a": 0x01, "enemy-b": 0x04},
        "rawGroupXorMasks": {"enemy-a": 0x01, "enemy-b": 0x04},
        "controlXorMask": None,
        "controlCollisionAmbiguous": False,
        "singleBitMasks": True,
    }]


def test_cross_enemy_control_subtracts_shared_bits_but_keeps_residual_bitset_lead():
    groups = {
        "enemy-a": [
            _pair((12, 0x05), (80, 1)),
            _pair((12, 0x05), (81, 2)),
        ],
        "enemy-b": [
            _pair((12, 0x06), (82, 3)),
            _pair((12, 0x06), (83, 4)),
        ],
    }
    controls = [
        _pair((12, 0x04), (84, 5)),
        _pair((12, 0x04), (85, 6)),
    ]

    result = analyze_controlled_experiment_groups(groups, controls)

    assert result["sharedCandidateOffsets"] == [12]
    assert result["sameOffsetDifferentXorCandidates"] == [{
        "offset": 12,
        "groupXorMasks": {"enemy-a": 0x01, "enemy-b": 0x02},
        "rawGroupXorMasks": {"enemy-a": 0x05, "enemy-b": 0x06},
        "controlXorMask": 0x04,
        "controlCollisionAmbiguous": False,
        "singleBitMasks": True,
    }]
    rows = {row["name"]: row for row in result["groups"]}
    assert rows["enemy-a"]["residualBitCandidates"][0]["residualXorMask"] == 0x01
    assert rows["enemy-b"]["residualBitCandidates"][0]["residualXorMask"] == 0x02


from games.ff7r.save_bit_signature_probe import analyze_controlled_bit_signatures


def test_bit_signatures_map_distinct_enemy_bits_inside_one_shared_byte():
    groups = {
        "enemy-a": [
            _pair((12, 0x01), (70, 0x80), label="a1"),
            _pair((12, 0x01), (70, 0x80), label="a2"),
        ],
        "enemy-b": [
            _pair((12, 0x04), (70, 0x80), label="b1"),
            _pair((12, 0x04), (70, 0x80), label="b2"),
        ],
        "enemy-c": [
            _pair((20, 0x02), (70, 0x80), label="c1"),
            _pair((20, 0x02), (70, 0x80), label="c2"),
        ],
    }
    controls = [
        _pair((70, 0x80), label="noop1"),
        _pair((70, 0x80), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    assert result["candidateOffsets"] == [12, 20]
    assert result["packedFlagByteCandidates"] == [{
        "offset": 12,
        "groupBits": {"enemy-a": 0, "enemy-b": 2},
        "groupMasks": {"enemy-a": 0x01, "enemy-b": 0x04},
        "rawGroupMasks": {"enemy-a": 0x01, "enemy-b": 0x04},
        "controlXorMask": None,
    }]
    assert result["exclusiveSingleBitFlagCandidates"] == [
        {
            "group": "enemy-a",
            "offset": 12,
            "bit": 0,
            "mask": 0x01,
            "rawMask": 0x01,
            "controlXorMask": None,
        },
        {
            "group": "enemy-b",
            "offset": 12,
            "bit": 2,
            "mask": 0x04,
            "rawMask": 0x04,
            "controlXorMask": None,
        },
        {
            "group": "enemy-c",
            "offset": 20,
            "bit": 1,
            "mask": 0x02,
            "rawMask": 0x02,
            "controlXorMask": None,
        },
    ]
    assert result["implementationReady"] is False


def test_bit_signatures_subtract_stable_noop_bits_before_mapping_enemy_bits():
    groups = {
        "enemy-a": [
            _pair((12, 0x05), label="a1"),
            _pair((12, 0x05), label="a2"),
        ],
        "enemy-b": [
            _pair((12, 0x06), label="b1"),
            _pair((12, 0x06), label="b2"),
        ],
    }
    controls = [
        _pair((12, 0x04), label="noop1"),
        _pair((12, 0x04), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    assert result["packedFlagByteCandidates"] == [{
        "offset": 12,
        "groupBits": {"enemy-a": 0, "enemy-b": 1},
        "groupMasks": {"enemy-a": 0x01, "enemy-b": 0x02},
        "rawGroupMasks": {"enemy-a": 0x05, "enemy-b": 0x06},
        "controlXorMask": 0x04,
    }]
    assert [row["mask"] for row in result["exclusiveSingleBitFlagCandidates"]] == [0x01, 0x02]


def test_bit_signatures_do_not_false-promote_when_one_group_has_unstable_mask():
    groups = {
        "enemy-a": [
            _pair((12, 0x01), label="a1"),
            _pair((12, 0x01), label="a2"),
        ],
        "enemy-b": [
            _pair((12, 0x02), label="b1"),
            _pair((12, 0x04), label="b2"),
        ],
    }
    controls = [
        _pair((70, 0x80), label="noop1"),
        _pair((70, 0x80), label="noop2"),
    ]

    result = analyze_controlled_bit_signatures(groups, controls)

    row = next(row for row in result["offsetSignatures"] if row["offset"] == 12)
    assert row["groupMasks"] == {"enemy-a": 0x01}
    assert row["unresolvedGroups"] == {"enemy-b": "unstable-xor-mask"}
    assert row["packedDistinctSingleBitCandidate"] is False
    assert result["exclusiveSingleBitFlagCandidates"] == []
    assert result["unresolvedOffsets"] == [12]
