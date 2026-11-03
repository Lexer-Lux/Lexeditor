"""Per-entry merge for FFNx exe-override .msd files (card/scan/draw text)."""
import pytest

from plugins.ff8 import executable_text, paths, runtime_layout, scan_text

DRAW = executable_text.BY_ID["exe_draw_point"]
DRAW_PATH = "direct/ff8/en/exe/draw_point.msd"
SCAN_PATH = "direct/ff8/en/exe/battle_scans.msd"


def _draw(values):
    values = list(values)
    assert len(values) == DRAW.count
    return executable_text.build_msd(values, DRAW)


def test_exe_entries_merge_per_entry():
    vanilla = _draw(f"line {index}" for index in range(DRAW.count))
    first, _ = executable_text.apply_edits(vanilla, DRAW, {0: "first wins here"})
    second, _ = executable_text.apply_edits(vanilla, DRAW, {1: "second wins here"})
    merged, conflicts, fallback = executable_text.merge(
        vanilla, [("first", first), ("second", second)], DRAW_PATH, DRAW)
    assert not fallback and not conflicts
    assert executable_text._values_from_bytes(merged, DRAW)[:2] == [
        "first wins here", "second wins here"]


def test_exe_collision_names_winner_and_unit():
    vanilla = _draw(f"line {index}" for index in range(DRAW.count))
    low, _ = executable_text.apply_edits(vanilla, DRAW, {4: "low text"})
    high, _ = executable_text.apply_edits(vanilla, DRAW, {4: "high text"})
    merged, conflicts, fallback = executable_text.merge(
        vanilla, [("low", low), ("high", high)], DRAW_PATH, DRAW)
    assert not fallback
    assert executable_text._values_from_bytes(merged, DRAW)[4] == "high text"
    assert conflicts == [{"unit": f"{DRAW_PATH}:entry:4", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_exe_trailing_data_falls_back_opaque():
    vanilla = _draw(f"line {index}" for index in range(DRAW.count))
    merged, conflicts, fallback = executable_text.merge(
        vanilla, [("bad", vanilla + b"extra")], DRAW_PATH, DRAW)
    assert merged is None and not conflicts and "not a supported" in fallback


def test_scan_entries_merge_per_entry():
    vanilla = scan_text.build_msd([f"scan {index}" for index in range(scan_text.SCAN_COUNT)])
    first_values = scan_text._values_from_bytes(vanilla)
    first_values[3] = "first scan"
    second_values = scan_text._values_from_bytes(vanilla)
    second_values[7] = "second scan"
    merged, conflicts, fallback = scan_text.merge(
        vanilla, [("first", scan_text.build_msd(first_values)),
                  ("second", scan_text.build_msd(second_values))], SCAN_PATH)
    assert not fallback and not conflicts
    assert scan_text._values_from_bytes(merged)[3] == "first scan"
    assert scan_text._values_from_bytes(merged)[7] == "second scan"


def test_scan_collision_names_winner_and_unit():
    vanilla = scan_text.build_msd([f"scan {index}" for index in range(scan_text.SCAN_COUNT)])
    low_values = scan_text._values_from_bytes(vanilla)
    low_values[9] = "low scan"
    high_values = scan_text._values_from_bytes(vanilla)
    high_values[9] = "high scan"
    merged, conflicts, fallback = scan_text.merge(
        vanilla, [("low", scan_text.build_msd(low_values)),
                  ("high", scan_text.build_msd(high_values))], SCAN_PATH)
    assert not fallback
    assert scan_text._values_from_bytes(merged)[9] == "high scan"
    assert conflicts == [{"unit": f"{SCAN_PATH}:entry:9", "winner": "high",
                          "claimants": ["low", "high"]}]


def test_read_msd_matches_bytes_reader(tmp_path):
    vanilla = _draw(f"line {index}" for index in range(DRAW.count))
    target = tmp_path / DRAW.filename
    target.write_bytes(vanilla)
    assert executable_text.read_msd(target, DRAW) == \
        executable_text._values_from_bytes(vanilla, DRAW)
    scan_raw = scan_text.build_msd(
        [f"scan {index}" for index in range(scan_text.SCAN_COUNT)])
    scan_target = tmp_path / "battle_scans.msd"
    scan_target.write_bytes(scan_raw)
    assert scan_text.read_msd(scan_target) == scan_text._values_from_bytes(scan_raw)


def test_missing_executable_falls_back_opaque(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "GAME_ROOT", tmp_path)
    payload, mode, conflicts = runtime_layout._compose_logical_payload(
        DRAW_PATH, [("low", b"low"), ("high", b"high")], None, None, None)
    assert (payload, mode, conflicts) == (b"high", "opaque winner", [])


def test_installed_executable_composes_semantically():
    try:
        vanilla = executable_text.extracted_msd(paths.GAME_ROOT / "FF8_EN.exe", DRAW)
    except (OSError, ValueError):
        pytest.skip("the supported FF8_EN.exe is not installed")
    low, _ = executable_text.apply_edits(vanilla, DRAW, {0: "Low override"})
    high, _ = executable_text.apply_edits(vanilla, DRAW, {1: "High override"})
    payload, mode, conflicts = runtime_layout._compose_logical_payload(
        DRAW_PATH, [("low", low), ("high", high)], None, None, None)
    assert mode == "semantic merge" and not conflicts
    values = executable_text._values_from_bytes(payload, DRAW)
    assert (values[0], values[1]) == ("Low override", "High override")
