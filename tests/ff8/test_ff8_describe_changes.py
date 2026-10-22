"""FF8 mod contents: loaded files plus fixed-record comparison.

The Mods tab asks the game's loader which files it reads (the Read
column) and which records a mod changes against vanilla. FF8 compares
its fixed-record data files through the merger specs; kernel,
archives and media stay file-level, under Files.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import fixed_data_merge
from plugins.ff8 import paths as ff8_paths
from plugins.ff8.mod_support import Ff8ModAdapter


def price_record(buy, sell=1):
    return struct.pack("<HBB", buy, sell, 0)


def test_diff_names_changed_fields_per_record():
    spec = fixed_data_merge.SPECS["direct/menu/price.bin"]
    vanilla = price_record(100) + price_record(200)
    mod = price_record(100) + price_record(4560)
    assert fixed_data_merge.diff(vanilla, mod, spec, "menu/price.bin") == [
        {"table": "menu/price.bin", "id": 1, "label": "Record 1",
         "fields": ["buy_price"]}]


def test_diff_treats_a_changed_flag_byte_as_one_field():
    spec = fixed_data_merge.SPECS["direct/menu/mitem.bin"]
    vanilla = bytes((1, 0b00000001, 0, 0))
    mod = bytes((1, 0b00000101, 0, 0))
    assert fixed_data_merge.diff(vanilla, mod, spec, "menu/mitem.bin") == [
        {"table": "menu/mitem.bin", "id": 0, "label": "Record 0",
         "fields": ["flags"]}]


def test_diff_rejects_a_resized_file():
    spec = fixed_data_merge.SPECS["direct/menu/price.bin"]
    try:
        fixed_data_merge.diff(price_record(100), price_record(100) + b"xx",
                              spec, "menu/price.bin")
    except ValueError as error:
        assert "fixed size" in str(error)
    else:  # pragma: no cover
        raise AssertionError("resized file diffed")


def write_mod(folder):
    (folder / "direct" / "menu").mkdir(parents=True)
    (folder / "direct" / "menu" / "price.bin").write_bytes(
        price_record(100) + price_record(4560))
    (folder / "hext").mkdir()
    (folder / "hext" / "fix.txt").write_text("[/ff8]\n")
    (folder / "hext" / "map.png").write_bytes(b"not deployed")
    (folder / "readme.txt").write_text("hi")
    (folder / "mod.json").write_text("{}")


def test_describe_changes_compares_and_marks_loaded_files(tmp_path, monkeypatch):
    baseline = tmp_path / "baseline"
    (baseline / "menu").mkdir(parents=True)
    (baseline / "menu" / "price.bin").write_bytes(
        price_record(100) + price_record(200))
    monkeypatch.setattr(ff8_paths, "BASELINE_ROOT", baseline)
    mod = tmp_path / "mod"
    write_mod(mod)
    reported = Ff8ModAdapter().describe_changes(mod, tmp_path / "game")
    assert reported["changes"] == [
        {"table": "menu/price.bin", "id": 1, "label": "Record 1",
         "fields": ["buy_price"]}]
    assert sorted(reported["loaded"]) == ["direct/menu/price.bin", "hext/fix.txt"]
    assert "fixed-record" in reported["note"]


def test_describe_changes_without_a_baseline_still_marks_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ff8_paths, "BASELINE_ROOT", tmp_path / "nowhere")
    mod = tmp_path / "mod"
    write_mod(mod)
    reported = Ff8ModAdapter().describe_changes(mod, tmp_path / "game")
    assert reported["changes"] == []
    assert sorted(reported["loaded"]) == ["direct/menu/price.bin", "hext/fix.txt"]
    assert "Extract" in reported["note"]
