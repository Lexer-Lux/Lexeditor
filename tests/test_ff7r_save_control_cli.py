import importlib.util
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "ff7r_assess_save_diff.py"
SPEC = importlib.util.spec_from_file_location("ff7r_assess_save_diff_control", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write_pair(root: Path, stem: str, changes: dict[int, int]):
    before = bytearray(96)
    after = bytearray(before)
    for offset, value in changes.items():
        after[offset] = value
    before_path = root / f"{stem}-before.sav"
    after_path = root / f"{stem}-after.sav"
    before_path.write_bytes(before)
    after_path.write_bytes(after)
    return str(before_path), str(after_path)


def test_cli_builder_subtracts_noop_control_from_repeated_assess_pairs(tmp_path):
    assess1 = _write_pair(tmp_path, "assess1", {10: 1, 70: 0x80, 80: 1})
    assess2 = _write_pair(tmp_path, "assess2", {10: 1, 70: 0x80, 81: 2})
    noop1 = _write_pair(tmp_path, "noop1", {70: 0x80, 82: 3})
    noop2 = _write_pair(tmp_path, "noop2", {70: 0x80, 83: 4})

    report = MODULE.build_report(
        pair_specs=[("assess-1", *assess1), ("assess-2", *assess2)],
        control_specs=[("noop-1", *noop1), ("noop-2", *noop2)],
    )

    assert report["mode"] == "repeated-single-experiment-with-noop-control"
    assert report["analysis"]["controlOverlapOffsets"] == [70]
    assert report["analysis"]["candidateOffsets"] == [10]


def test_cli_builder_subtracts_noop_control_from_cross_enemy_groups(tmp_path):
    a1 = _write_pair(tmp_path, "a1", {10: 1, 70: 0x80, 80: 1})
    a2 = _write_pair(tmp_path, "a2", {10: 1, 70: 0x80, 81: 2})
    b1 = _write_pair(tmp_path, "b1", {20: 4, 70: 0x80, 82: 3})
    b2 = _write_pair(tmp_path, "b2", {20: 4, 70: 0x80, 83: 4})
    noop1 = _write_pair(tmp_path, "noop1", {70: 0x80, 84: 5})
    noop2 = _write_pair(tmp_path, "noop2", {70: 0x80, 85: 6})

    report = MODULE.build_report(
        group_specs=[
            ("enemy-a", *a1), ("enemy-a", *a2),
            ("enemy-b", *b1), ("enemy-b", *b2),
        ],
        control_specs=[("noop-1", *noop1), ("noop-2", *noop2)],
    )

    assert report["mode"] == "cross-enemy-experiments-with-noop-control"
    assert report["analysis"]["controlStableOffsets"] == [70]
    assert report["analysis"]["discriminatingCandidateOffsets"] == [10, 20]


def test_cli_builder_can_emit_control_subtracted_bit_signatures(tmp_path):
    a1 = _write_pair(tmp_path, "a1", {12: 0x05, 80: 1})
    a2 = _write_pair(tmp_path, "a2", {12: 0x05, 81: 2})
    b1 = _write_pair(tmp_path, "b1", {12: 0x06, 82: 3})
    b2 = _write_pair(tmp_path, "b2", {12: 0x06, 83: 4})
    noop1 = _write_pair(tmp_path, "noop1", {12: 0x04, 84: 5})
    noop2 = _write_pair(tmp_path, "noop2", {12: 0x04, 85: 6})

    report = MODULE.build_report(
        group_specs=[
            ("enemy-a", *a1), ("enemy-a", *a2),
            ("enemy-b", *b1), ("enemy-b", *b2),
        ],
        control_specs=[("noop-1", *noop1), ("noop-2", *noop2)],
        bit_signatures=True,
    )

    assert report["mode"] == "cross-enemy-bit-signatures-with-noop-control"
    assert report["analysis"]["implementationReady"] is False
    assert report["analysis"]["candidateOffsets"] == [12]
    assert report["analysis"]["packedFlagByteCandidates"] == [{
        "offset": 12,
        "groupBits": {"enemy-a": 0, "enemy-b": 1},
        "groupMasks": {"enemy-a": 0x01, "enemy-b": 0x02},
        "rawGroupMasks": {"enemy-a": 0x05, "enemy-b": 0x06},
        "controlXorMask": 0x04,
    }]


def test_cli_builder_can_validate_bit_signatures_against_held_out_runs(tmp_path):
    a1 = _write_pair(tmp_path, "a1", {12: 0x05, 80: 1})
    a2 = _write_pair(tmp_path, "a2", {12: 0x05, 81: 2})
    b1 = _write_pair(tmp_path, "b1", {12: 0x06, 82: 3})
    b2 = _write_pair(tmp_path, "b2", {12: 0x06, 83: 4})
    ha1 = _write_pair(tmp_path, "ha1", {12: 0x05, 86: 7})
    ha2 = _write_pair(tmp_path, "ha2", {12: 0x05, 87: 8})
    hb1 = _write_pair(tmp_path, "hb1", {12: 0x06, 88: 9})
    hb2 = _write_pair(tmp_path, "hb2", {12: 0x06, 89: 10})
    noop1 = _write_pair(tmp_path, "noop1", {12: 0x04, 84: 5})
    noop2 = _write_pair(tmp_path, "noop2", {12: 0x04, 85: 6})

    report = MODULE.build_report(
        group_specs=[
            ("enemy-a", *a1), ("enemy-a", *a2),
            ("enemy-b", *b1), ("enemy-b", *b2),
        ],
        holdout_group_specs=[
            ("enemy-a", *ha1), ("enemy-a", *ha2),
            ("enemy-b", *hb1), ("enemy-b", *hb2),
        ],
        control_specs=[("noop-1", *noop1), ("noop-2", *noop2)],
        bit_signatures=True,
    )

    assert report["mode"] == "cross-enemy-bit-signatures-with-holdout-validation"
    analysis = report["analysis"]
    assert analysis["confirmedCandidateCount"] == 2
    assert analysis["allDiscoveryCandidatesConfirmed"] is True
    assert analysis["exactHoldoutAgreement"] is True
    assert analysis["implementationReady"] is False


def test_cli_builder_holdout_reports_changed_candidate_instead_of_promoting_it(tmp_path):
    a1 = _write_pair(tmp_path, "a1", {12: 0x01})
    a2 = _write_pair(tmp_path, "a2", {12: 0x01})
    ha1 = _write_pair(tmp_path, "ha1", {12: 0x04})
    ha2 = _write_pair(tmp_path, "ha2", {12: 0x04})
    noop1 = _write_pair(tmp_path, "noop1", {70: 0x80})
    noop2 = _write_pair(tmp_path, "noop2", {70: 0x80})

    report = MODULE.build_report(
        group_specs=[("enemy-a", *a1), ("enemy-a", *a2)],
        holdout_group_specs=[("enemy-a", *ha1), ("enemy-a", *ha2)],
        control_specs=[("noop-1", *noop1), ("noop-2", *noop2)],
        bit_signatures=True,
    )

    analysis = report["analysis"]
    assert analysis["confirmedCandidateCount"] == 0
    assert analysis["missingCandidateCount"] == 1
    assert analysis["unexpectedCandidateCount"] == 1
    assert analysis["exactHoldoutAgreement"] is False


def test_cli_builder_rejects_holdout_without_full_validation_mode(tmp_path):
    discovery = _write_pair(tmp_path, "discovery", {12: 1})
    holdout = _write_pair(tmp_path, "holdout", {12: 1})
    control = _write_pair(tmp_path, "control", {70: 0x80})

    invalid_cases = [
        {
            "group_specs": [("enemy-a", *discovery)],
            "holdout_group_specs": [("enemy-a", *holdout)],
            "bit_signatures": True,
        },
        {
            "group_specs": [("enemy-a", *discovery)],
            "holdout_group_specs": [("enemy-a", *holdout)],
            "control_specs": [("noop", *control)],
        },
    ]
    for kwargs in invalid_cases:
        try:
            MODULE.build_report(**kwargs)
        except ValueError as error:
            assert "--holdout-group" in str(error)
        else:
            raise AssertionError("expected --holdout-group mode ValueError")


def test_cli_builder_rejects_bit_signatures_without_grouped_controls(tmp_path):
    assess = _write_pair(tmp_path, "assess", {10: 1})

    try:
        MODULE.build_report(
            pair_specs=[("assess", *assess)],
            bit_signatures=True,
        )
    except ValueError as error:
        assert "--bit-signatures" in str(error)
    else:
        raise AssertionError("expected --bit-signatures mode ValueError")


def test_cli_builder_rejects_control_without_assess_experiment(tmp_path):
    noop = _write_pair(tmp_path, "noop", {70: 0x80})

    try:
        MODULE.build_report(control_specs=[("noop", *noop)])
    except ValueError as error:
        assert "--control" in str(error)
    else:
        raise AssertionError("expected --control mode ValueError")
