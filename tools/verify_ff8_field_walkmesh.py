"""Verify exact FF8 field walkmesh parsing and mutation across the corpus."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import field_data, field_walkmesh  # noqa: E402
from games.ff8.fs_archive import FsArchive  # noqa: E402


def main() -> int:
    archive = FsArchive(field_data._prefix())
    groups = field_data._outer_groups(archive)
    files = triangles = 0
    sample = None
    for key, group in sorted(groups.items()):
        nested_fs = archive.extract(group["entries"][".fs"])
        nested_fi = archive.extract(group["entries"][".fi"])
        nested_fl = archive.extract(group["entries"][".fl"])
        entries = field_data._memory_entries(nested_fi, nested_fl)
        basename = f"{group['name']}.id".casefold()
        if not any(entry["basename"] == basename for entry in entries):
            continue
        raw = field_data._memory_extract(nested_fs, entries, basename)
        parsed = field_walkmesh.read(raw)
        rebuilt, changed = field_walkmesh.apply_edits(raw, [])
        assert rebuilt == raw and changed == 0
        files += 1
        triangles += parsed["triangleCount"]
        if sample is None and parsed["triangles"]:
            sample = (key, raw, parsed)
    assert files and triangles and sample is not None

    key, raw, parsed = sample
    vertex = parsed["triangles"][0]["vertices"][0]
    next_x = vertex["x"] + 1 if vertex["x"] < 32767 else vertex["x"] - 1
    mutated, changed = field_walkmesh.apply_edits(raw, [{
        "triangle": 0, "vertex": 0, "x": next_x,
    }])
    assert changed == 1 and len(mutated) == len(raw)
    differences = [index for index, pair in enumerate(zip(raw, mutated))
                   if pair[0] != pair[1]]
    assert differences and all(index in (4, 5) for index in differences)
    decoded = field_walkmesh.read(mutated)
    assert decoded["triangles"][0]["vertices"][0]["x"] == next_x
    assert decoded["triangles"][0]["vertices"][0]["reserved"] == vertex["reserved"]
    tailed = raw + b"\x34\x12"
    assert field_walkmesh.read(tailed)["trailingUnknown"] == 0x1234
    assert field_walkmesh.apply_edits(tailed, [
        {"triangle": 0, "vertex": 0, "x": next_x},
    ])[0][-2:] == b"\x34\x12"
    next_y = vertex["y"] + 1 if vertex["y"] < 32767 else vertex["y"] - 1
    y_mod, _ = field_walkmesh.apply_edits(raw, [{
        "triangle": 0, "vertex": 0, "y": next_y,
    }])
    merged, conflicts, fallback = field_walkmesh.merge(
        raw, [("x", mutated), ("y", y_mod)], f"{key}.id")
    assert merged is not None and not conflicts and not fallback
    merged_vertex = field_walkmesh.read(merged)["triangles"][0]["vertices"][0]
    assert merged_vertex["x"] == next_x and merged_vertex["y"] == next_y
    other_x = next_x + 1 if next_x < 32767 else next_x - 1
    x2, _ = field_walkmesh.apply_edits(raw, [{
        "triangle": 0, "vertex": 0, "x": other_x,
    }])
    collided, conflicts, fallback = field_walkmesh.merge(
        raw, [("x", mutated), ("higher", x2)], f"{key}.id")
    assert collided is not None and not fallback
    assert field_walkmesh.read(collided)["triangles"][0]["vertices"][0]["x"] == other_x
    assert conflicts == [{
        "unit": f"{key}.id:triangle:0:vertex:0:x",
        "winner": "higher", "claimants": ["x", "higher"],
    }]
    opaque = bytearray(raw)
    opaque[10] ^= 1  # The unresolved fourth vertex word must not be merged.
    assert field_walkmesh.merge(raw, [("opaque", bytes(opaque))], f"{key}.id")[0] is None

    rejected = 0
    for edit in (
            {"triangle": -1, "vertex": 0, "x": 0},
            {"triangle": 0, "vertex": 3, "x": 0},
            {"triangle": 0, "vertex": 0, "x": 32768},
            {"triangle": 0, "vertex": 0, "adjacent": parsed["triangleCount"]},
            {"triangle": 0, "vertex": 0, "reserved": 0},
            {"triangle": 0, "vertex": 0, "x": 0, "unexpected": 1},
            ):
        try:
            field_walkmesh.apply_edits(raw, [edit])
        except ValueError:
            rejected += 1
    assert rejected == 6

    print({"maps": len(groups), "walkmeshes": files, "triangles": triangles,
           "sample": key, "changedOffsets": differences, "rejected": rejected,
           "semanticMerge": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
