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


def test_cli_builder_rejects_control_without_assess_experiment(tmp_path):
    noop = _write_pair(tmp_path, "noop", {70: 0x80})

    try:
        MODULE.build_report(control_specs=[("noop", *noop)])
    except ValueError as error:
        assert "--control" in str(error)
    else:
        raise AssertionError("expected --control mode ValueError")
