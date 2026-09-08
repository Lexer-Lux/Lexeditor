from games.ff7r.save_control_probe import analyze_controlled_save_pairs
from games.ff7r.save_diff_probe import SavePair


def _pair(*changes: tuple[int, int], label: str = "") -> SavePair:
    before = bytearray(96)
    after = bytearray(before)
    for offset, value in changes:
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
