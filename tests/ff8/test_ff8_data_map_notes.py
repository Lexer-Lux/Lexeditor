"""Each FF8 Data Map row keeps its own notes.

The FFNx.toml "missing" note was assigned outside its condition and replaced
every row's notes, so the whole Data Map read "FFNx.toml is missing".
"""
from pathlib import Path

from plugins.ff8 import formats


def test_rows_keep_their_own_notes():
    rows = formats.data_map_rows()["rows"]
    missing = "FFNx.toml is missing"
    assert [row["filename"] for row in rows if missing in row.get("notes", "")] in ([], ["FFNx.toml"])
    kernel = next(row for row in rows if row["filename"] == "kernel.bin")
    assert kernel["notes"].startswith("Editable:")


def test_archive_row_describes_headless_extract_and_repack():
    rows = formats.data_map_rows()["rows"]
    archives = next(row for row in rows
                    if row["filename"] == "ff8/*.fs + .fi + .fl archives")
    assert "not built" not in archives["notes"]
    assert "extracted/" in archives["notes"] and "repacked/" in archives["notes"]
    # The generic browser page stays removed by design: no editor target.
    assert archives["targets"] == [] and archives["openable"] is False


def test_vram_palette_animation_stays_wont_do():
    # Issue 933: vestigial in the retail build per the pinned FF8UE source,
    # so no Data Map row may ask for an editor here.
    rows = formats.data_map_rows()["rows"]
    for row in rows:
        notes = row.get("notes", "").casefold()
        assert "palette animation" not in notes and "vram" not in notes
    vendor = (Path(formats.__file__).resolve().parent / "vendor" / "ff8ue"
              / "monsterdata.py")
    words = " ".join(vendor.read_text(encoding="utf-8").split())
    assert "vestigial in the retail PC build" in words
