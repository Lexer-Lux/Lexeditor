"""Verify the world-to-field table: its layout, its writer and its preservation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import paths, wm2field  # noqa: E402


def rejected(raw: bytes, edits: list[dict], expected: str) -> None:
    try:
        wm2field.apply_edits(raw, edits)
    except ValueError as error:
        assert expected.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"wm2field.tbl writer accepted invalid {expected}")


def main() -> int:
    raw = wm2field.ensure_baseline().read_bytes()
    document = wm2field.parse(raw)
    assert document["count"] == wm2field.ENTRY_COUNT == 72
    assert document["entrySize"] == wm2field.ENTRY_SIZE == 24
    rows = document["rows"]
    # The field IDs are the small values the field archive uses, one per entry.
    ids = [row["fieldId"] for row in rows]
    assert all(0 < value < 1200 for value in ids), ids
    assert len(set(ids)) > 40, len(set(ids))
    # Coordinates are wider than a field ID, which is what tells the words apart.
    widest = max(abs(row["x"]) for row in rows)
    assert widest > 1200, widest
    # An untouched table is written back byte for byte.
    assert wm2field.apply_edits(raw, []) == raw

    # Entry 0 ships as (-1865, -1694, 247, 159); move every one of its fields.
    edited = wm2field.apply_edits(raw, [
        {"id": 0, "x": -1800, "y": -1700, "z": 250, "fieldId": 160},
        {"id": 3, "x": 1, "y": -1, "z": 65535, "fieldId": 1200},
    ])
    changed = [index for index, (left, right) in enumerate(zip(raw, edited)) if left != right]
    # Only the named fields move: four 2-byte values in each edited entry.
    # Entry 0's four fields keep their high bytes; entry 3's all change.
    assert changed == [0, 2, 4, 6, *range(3 * 24, 3 * 24 + 8)], changed
    reread = wm2field.parse(edited)["rows"]
    assert (rows[0]["x"], rows[0]["y"], rows[0]["z"], rows[0]["fieldId"]) == \
        (-1865, -1694, 247, 159)
    assert (reread[0]["x"], reread[0]["y"], reread[0]["z"], reread[0]["fieldId"]) == \
        (-1800, -1700, 250, 160)
    assert (reread[3]["x"], reread[3]["y"], reread[3]["z"], reread[3]["fieldId"]) == \
        (1, -1, 65535, 1200)
    # Everything the reader does not name stays: the pointer byte and the tail.
    assert all(reread[index]["pointer"] == rows[index]["pointer"] for index in range(72))
    assert edited[9:24] == raw[9:24]
    assert edited[3 * 24 + 9:3 * 24 + 24] == raw[3 * 24 + 9:3 * 24 + 24]

    rejected(raw, [{"id": 72, "x": 0, "y": 0, "z": 0, "fieldId": 1}], "no entry 72")
    rejected(raw, [{"id": 0, "x": 0, "y": 0, "z": 0, "fieldId": 1},
                   {"id": 0, "x": 1, "y": 0, "z": 0, "fieldId": 1}], "two edits")
    rejected(raw, [{"id": 0, "x": 40000, "y": 0, "z": 0, "fieldId": 1}], "must be -32768")
    rejected(raw, [{"id": 0, "x": 0, "y": 0, "z": -1, "fieldId": 1}], "must be 0 to 65535")
    rejected(raw, [{"id": 0, "x": 0, "y": 0, "z": 0, "fieldId": 99999}], "must be 0 to 65535")
    rejected(raw, [{"x": 0, "y": 0, "z": 0, "fieldId": 1}], "needs an id")
    rejected(raw, [{"id": 0, "x": "three", "y": 0, "z": 0, "fieldId": 1}], "whole number")
    try:
        wm2field.parse(raw[:-1])
    except ValueError as error:
        assert "expected" in str(error)
    else:
        raise AssertionError("a truncated wm2field.tbl was accepted")

    project = tempfile.TemporaryDirectory(prefix="lexeditor-wm2field-", ignore_cleanup_errors=True)
    previous_project, previous_direct = paths.PROJECT_ROOT, paths.DIRECT_ROOT
    try:
        paths.PROJECT_ROOT = Path(project.name)
        paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
        saved = wm2field.save([{"id": 5, "x": -272, "y": -543, "z": 8, "fieldId": 822}])
        assert saved["source"] == "current" and saved["rows"][5]["fieldId"] == 822
        written = paths.DIRECT_ROOT / wm2field.DIRECT_RELATIVE
        assert written.is_file()
        assert wm2field.parse(written.read_bytes())["rows"][6]["fieldId"] == rows[6]["fieldId"]
        assert wm2field.source_path("current") == written
        assert wm2field.source_path("vanilla") == wm2field.ensure_baseline()
        wm2field.save([{"id": 5, "x": -272, "y": -543, "z": 8, "fieldId": 900}])
        assert written.with_name("wm2field.tbl.bak").is_file()
    finally:
        paths.PROJECT_ROOT, paths.DIRECT_ROOT = previous_project, previous_direct
        project.cleanup()
    print(json.dumps({"entries": document["count"], "distinctFieldIds": len(set(ids)),
                      "widestCoordinate": widest, "changedOffsets": changed,
                      "rejections": 8, "saveReadBack": True}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
