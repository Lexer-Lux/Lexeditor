import importlib.util
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "ff7r_assess_save_diff.py"
SPEC = importlib.util.spec_from_file_location("ff7r_assess_save_diff", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write_pair(root: Path, stem: str, offset: int, mask: int):
    before = bytearray(64)
    after = bytearray(before)
    after[offset] ^= mask
    before_path = root / f"{stem}-before.sav"
    after_path = root / f"{stem}-after.sav"
    before_path.write_bytes(before)
    after_path.write_bytes(after)
    return str(before_path), str(after_path)


def test_cli_builder_reports_repeated_single_experiment(tmp_path):
    before1, after1 = _write_pair(tmp_path, "one", 10, 1)
    before2, after2 = _write_pair(tmp_path, "two", 10, 1)

    report = MODULE.build_report(pair_specs=[
        ("run-1", before1, after1),
        ("run-2", before2, after2),
    ])

    assert report["mode"] == "repeated-single-experiment"
    assert report["analysis"]["stableChangedOffsets"] == [10]


def test_cli_builder_groups_repeated_experiments_by_enemy(tmp_path):
    a1 = _write_pair(tmp_path, "a1", 10, 1)
    a2 = _write_pair(tmp_path, "a2", 10, 1)
    b1 = _write_pair(tmp_path, "b1", 20, 4)
    b2 = _write_pair(tmp_path, "b2", 20, 4)

    report = MODULE.build_report(group_specs=[
        ("enemy-a", *a1),
        ("enemy-a", *a2),
        ("enemy-b", *b1),
        ("enemy-b", *b2),
    ])

    assert report["mode"] == "cross-enemy-experiments"
    assert report["analysis"]["discriminatingStableOffsets"] == [10, 20]


def test_cli_builder_enemy_indices_correlate_reproduced_bits(tmp_path):
    a1 = _write_pair(tmp_path, "a1", 12, 0x01)
    a2 = _write_pair(tmp_path, "a2", 12, 0x01)
    b1 = _write_pair(tmp_path, "b1", 12, 0x02)
    b2 = _write_pair(tmp_path, "b2", 12, 0x02)
    c1 = _write_pair(tmp_path, "c1", 50, 0x20)
    c2 = _write_pair(tmp_path, "c2", 50, 0x20)

    report = MODULE.build_report(
        group_specs=[
            ("enemy-a", *a1),
            ("enemy-a", *a2),
            ("enemy-b", *b1),
            ("enemy-b", *b2),
        ],
        control_specs=[
            ("noop-1", *c1),
            ("noop-2", *c2),
        ],
        enemy_index_specs=[
            ("enemy-a", "0"),
            ("enemy-b", "0x1"),
        ],
        bit_signatures=True,
    )

    assert report["mode"] == "cross-enemy-bit-signatures-with-noop-control"
    layout = report["analysis"]["indexedBitsetLayout"]
    assert layout["enemyBookIds"] == {"enemy-a": 0, "enemy-b": 1}
    assert layout["exactMappedAgreement"] is True
    assert layout["exactBaseBit"] == 96
    assert layout["implementationReady"] is False


def test_cli_builder_rejects_enemy_indices_without_bit_signatures(tmp_path):
    a1 = _write_pair(tmp_path, "a1", 12, 0x01)
    a2 = _write_pair(tmp_path, "a2", 12, 0x01)
    c1 = _write_pair(tmp_path, "c1", 50, 0x20)
    c2 = _write_pair(tmp_path, "c2", 50, 0x20)

    try:
        MODULE.build_report(
            group_specs=[("enemy-a", *a1), ("enemy-a", *a2)],
            control_specs=[("noop-1", *c1), ("noop-2", *c2)],
            enemy_index_specs=[("enemy-a", "0")],
        )
    except ValueError as error:
        assert "--enemy-index requires --bit-signatures" in str(error)
    else:
        raise AssertionError("expected --enemy-index validation error")


def test_cli_builder_rejects_mixed_or_empty_modes(tmp_path):
    before, after = _write_pair(tmp_path, "one", 10, 1)

    try:
        MODULE.build_report(
            pair_specs=[("run", before, after)],
            group_specs=[("enemy", before, after)],
        )
    except ValueError as error:
        assert "either --pair or --group" in str(error)
    else:
        raise AssertionError("expected mixed-mode ValueError")

    try:
        MODULE.build_report()
    except ValueError as error:
        assert "at least one" in str(error)
    else:
        raise AssertionError("expected empty-mode ValueError")


def test_cli_main_writes_json_report(tmp_path):
    before, after = _write_pair(tmp_path, "one", 12, 2)
    output = tmp_path / "report.json"

    result = MODULE.main([
        "--pair", "run", before, after,
        "--output", str(output),
    ])

    assert result == 0
    text = output.read_text(encoding="utf-8")
    assert '"mode": "repeated-single-experiment"' in text
    assert '"stableChangedOffsets"' in text
