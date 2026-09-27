"""wm2field.tbl stores where the player arrives inside a field.

Each entry's X and Y lie inside walkmesh triangle Z of the field it names. The
World -> Field page draws that point on the field's picture and calls Z the
triangle (Lexer, 2026-09-27, asked for the entry's point and the field's
image; the page had called these values a world-map position).
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import field_data, field_walkmesh, wm2field  # noqa: E402


def inside(point, corners) -> bool:
    x, y = point

    def side(a, b):
        return (x - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (y - b[1])

    signs = [side(corners[0], corners[1]), side(corners[1], corners[2]), side(corners[2], corners[0])]
    return not (any(value < 0 for value in signs) and any(value > 0 for value in signs))


def main() -> int:
    rows = wm2field.parse(wm2field.ensure_baseline().read_bytes())["rows"]
    fields = {row["mapId"]: row["key"] for row in field_data.ensure_index()["rows"] if row["mapId"] is not None}
    checked, outside = 0, []
    for row in rows:
        key = fields.get(row["fieldId"])
        assert key, f"entry {row['id']} names field {row['fieldId']}, which the field list lacks"
        path = field_data._walkmesh_source_path(key, "vanilla")
        assert path, f"{key} has no walkmesh"
        triangles = field_walkmesh.read(path.read_bytes())["triangles"]
        assert row["z"] < len(triangles), (row, len(triangles))
        corners = [(vertex["x"], vertex["y"]) for vertex in triangles[row["z"]]["vertices"]]
        if not inside((row["x"], row["y"]), corners):
            outside.append((row["id"], key))
        checked += 1
    assert checked == 72, checked
    assert not outside, outside
    print(f"{checked} of 72 wm2field entries lie in their own walkmesh triangle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
