"""Each FF8 Data Map row keeps its own notes.

The FFNx.toml "missing" note was assigned outside its condition and replaced
every row's notes, so the whole Data Map read "FFNx.toml is missing".
"""
from plugins.ff8 import formats


def test_rows_keep_their_own_notes():
    rows = formats.data_map_rows()["rows"]
    missing = "FFNx.toml is missing"
    assert [row["filename"] for row in rows if missing in row.get("notes", "")] in ([], ["FFNx.toml"])
    kernel = next(row for row in rows if row["filename"] == "kernel.bin")
    assert kernel["notes"].startswith("Editable:")
