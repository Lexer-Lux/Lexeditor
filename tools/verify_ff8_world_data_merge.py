"""Verify semantic low-to-high composition of proved FF8 world assets."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import (formats, paths, runtime_layout, world_data_merge,
                       world_map, world_textures)  # noqa: E402


def changed(raw: bytes, offset: int, size: int = 1, delta: int = 1) -> bytes:
    result = bytearray(raw)
    value = int.from_bytes(result[offset:offset + size], "little")
    result[offset:offset + size] = ((value + delta) % (1 << (size * 8))).to_bytes(size, "little")
    return bytes(result)


def main() -> int:
    wmset = world_map.ensure_baseline().read_bytes()
    pointers = world_map._pointers(wmset)
    region_offset = pointers[1]
    helper_offset = pointers[0] + 4
    region_mod = changed(wmset, region_offset)
    helper_mod = changed(wmset, helper_offset + 1)
    draw_offset = pointers[world_map.DRAW_SECTION] + world_map.DRAW_HEADER_SIZE
    draw_mod = changed(wmset, draw_offset)
    merged, conflicts, fallback = world_data_merge.merge(
        wmset, [("regions", region_mod), ("helpers", helper_mod), ("draw", draw_mod)],
        "wmset", "direct/world/dat/wmsetus.obj")
    assert merged is not None and not conflicts and not fallback
    assert merged[region_offset] == region_mod[region_offset]
    assert merged[helper_offset + 1] == helper_mod[helper_offset + 1]
    assert merged[draw_offset] == draw_mod[draw_offset]
    collision_mod = changed(wmset, region_offset, delta=2)
    collided, conflicts, fallback = world_data_merge.merge(
        wmset, [("one", region_mod), ("two", collision_mod)],
        "wmset", "direct/world/dat/wmsetus.obj")
    assert collided is not None and collided[region_offset] == collision_mod[region_offset]
    assert conflicts == [{"unit": "direct/world/dat/wmsetus.obj:region:0:regionId",
                           "winner": "two", "claimants": ["one", "two"]}]
    opaque = changed(wmset, pointers[0])
    unsupported, _, fallback = world_data_merge.merge(
        wmset, [("one", region_mod), ("opaque", opaque)],
        "wmset", "direct/world/dat/wmsetus.obj")
    assert unsupported is None and "outside proved" in fallback

    rail = world_map.ensure_rail_baseline().read_bytes()
    first_x = world_map.RAIL_HEADER_SIZE
    first_y = first_x + 4
    x_mod, y_mod = changed(rail, first_x, 4), changed(rail, first_y, 4)
    merged, conflicts, fallback = world_data_merge.merge(
        rail, [("x", x_mod), ("y", y_mod)], "rail", "direct/world/dat/rail.obj")
    assert merged is not None and not conflicts and not fallback
    assert merged[first_x:first_x + 4] == x_mod[first_x:first_x + 4]
    assert merged[first_y:first_y + 4] == y_mod[first_y:first_y + 4]
    rail_opaque = changed(rail, first_x + 12, 4)
    assert world_data_merge.merge(
        rail, [("opaque", rail_opaque)], "rail", "direct/world/dat/rail.obj")[0] is None

    textures = world_textures.ensure_baseline().read_bytes()
    layout = world_textures._tim_layout(textures[:world_textures.SLOT_SIZE])
    pixel0 = 8 + layout["paletteSize"] + 12
    pixel1 = world_textures.SLOT_SIZE + pixel0
    texture0, texture1 = changed(textures, pixel0), changed(textures, pixel1)
    merged, conflicts, fallback = world_data_merge.merge(
        textures, [("texture-0", texture0), ("texture-1", texture1)],
        "textures", "direct/world/dat/texl.obj")
    assert merged is not None and not conflicts and not fallback
    assert merged[pixel0] == texture0[pixel0] and merged[pixel1] == texture1[pixel1]
    tail = layout["used"]
    texture_opaque = changed(textures, tail)
    unsupported, _, fallback = world_data_merge.merge(
        textures, [("opaque", texture_opaque)], "textures", "direct/world/dat/texl.obj")
    assert unsupported is None and "outside proved" in fallback

    logical_path = "direct/world/dat/wmsetus.obj"
    live_merged, mode, live_conflicts = runtime_layout._compose_logical_payload(
        logical_path, [("regions", region_mod), ("helpers", helper_mod)],
        paths.BASELINE_ROOT, formats.SECTIONS, None)
    assert live_merged is not None and mode == "semantic merge" and not live_conflicts
    assert live_merged[region_offset] == region_mod[region_offset]
    assert live_merged[helper_offset + 1] == helper_mod[helper_offset + 1]

    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-world-merge-") as name:
        root = Path(name)
        first, second, active = root / "first", root / "second", root / "active"
        for mod, mod_id, payload, order in (
                (first, "regions", region_mod, 0),
                (second, "helpers", helper_mod, 1)):
            target = mod / logical_path
            target.parent.mkdir(parents=True)
            target.write_bytes(payload)
            (mod / runtime_layout.MOD_FILE).write_text(json.dumps({
                "id": mod_id, "name": mod_id, "enabled": True, "order": order,
            }), encoding="utf-8")
        rows = runtime_layout.catalog(first, root)
        runtime = runtime_layout.compose(
            first, active, rows, paths.BASELINE_ROOT, formats.SECTIONS)
        output = (active / logical_path).read_bytes()
        assert output[region_offset] == region_mod[region_offset]
        assert output[helper_offset + 1] == helper_mod[helper_offset + 1]
        conflict = next(row for row in runtime["conflicts"]
                        if row["path"] == logical_path)
        assert conflict["winner"] == "semantic merge"
        assert "semanticFallback" not in conflict

        (second / logical_path).write_bytes(opaque)
        fallback_runtime = runtime_layout.compose(
            first, active, rows, paths.BASELINE_ROOT, formats.SECTIONS)
        assert (active / logical_path).read_bytes() == opaque
        conflict = next(row for row in fallback_runtime["conflicts"]
                        if row["path"] == logical_path)
        assert conflict["winner"] == "helpers"
        assert "outside proved" in conflict["semanticFallback"]

    print({"wmsetUnits": True, "railUnits": True, "textureSlots": 20,
           "conflicts": True, "opaqueFallback": True,
           "runtimeComposition": True, "liveVariantComposition": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
