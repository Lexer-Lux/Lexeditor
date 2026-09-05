"""Prove strict FF8 field-background round trips, edits, and rendering."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import field_background, field_data  # noqa: E402
from games.ff8.fs_archive import FsArchive  # noqa: E402


def _pair(archive: FsArchive, group: dict) -> tuple[bytes, bytes] | None:
    nested_fs = archive.extract(group["entries"][".fs"])
    nested_fi = archive.extract(group["entries"][".fi"])
    nested_fl = archive.extract(group["entries"][".fl"])
    entries = field_data._memory_entries(nested_fi, nested_fl)
    names = {entry["basename"] for entry in entries}
    map_name = f"{group['name']}.map".casefold()
    mim_name = f"{group['name']}.mim".casefold()
    if map_name not in names and mim_name not in names:
        return None
    assert map_name in names and mim_name in names, "background MAP/MIM pair is incomplete"
    return (field_data._memory_extract(nested_fs, entries, map_name),
            field_data._memory_extract(nested_fs, entries, mim_name))


def _different(value: int, low: int, high: int) -> int:
    return value + 1 if value < high else value - 1


def main() -> int:
    archive = FsArchive(field_data._prefix())
    groups = field_data._outer_groups(archive)
    variants = Counter()
    tile_total = 0
    samples: dict[str, tuple[str, bytes, bytes, dict]] = {}
    missing = 0
    for index, (key, group) in enumerate(sorted(groups.items())):
        pair = _pair(archive, group)
        if pair is None:
            missing += 1
            continue
        map_data, mim_data = pair
        parsed = field_background.read(map_data, mim_data)
        rebuilt, changed = field_background.apply_edits(map_data, mim_data, [])
        assert rebuilt == map_data and changed == 0
        assert parsed["tileCount"] == len(parsed["tiles"])
        variants[parsed["variant"]] += 1
        tile_total += parsed["tileCount"]
        if parsed["tiles"]:
            samples.setdefault(parsed["variant"], (key, map_data, mim_data, parsed))
        if index and index % 100 == 0:
            print(f"checked {index}/{len(groups)} field maps", flush=True)
    assert sum(variants.values()) + missing == len(groups)
    assert samples and tile_total

    tested_fields = set()
    for variant, (key, original, mim, parsed) in samples.items():
        tile = parsed["tiles"][0]
        fields = {
            "x": (-32768, 32767), "y": (-32768, 32767), "z": (0, 65535),
            "sourceX": (0, 255), "sourceY": (0, 255), "texture": (0, 15),
            "palette": (0, 15), "blend": (0, 3), "depth": (0, 3),
        }
        if variant != "old-short":
            fields.update({"parameter": (0, 255), "state": (0, 255)})
        if variant == "new":
            fields.update({"layer": (0, 255), "blendType": (0, 4)})
        for field, (low, high) in fields.items():
            value = _different(tile[field], low, high)
            mutated, changed = field_background.apply_edits(
                original, mim, [{"tile": 0, field: value}]
            )
            assert changed == 1 and len(mutated) == len(original)
            after = field_background.read(mutated, mim)
            assert after["variant"] == variant and after["tiles"][0][field] == value
            tested_fields.add(field)
        toggled, changed = field_background.apply_edits(
            original, mim, [{"tile": 0, "draw": not tile["draw"]}]
        )
        assert changed == 1
        assert field_background.read(toggled, mim)["tiles"][0]["draw"] != tile["draw"]
        tested_fields.add("draw")

        # Packed and terminator data that is outside exposed fields survives edits.
        opaque = bytearray(original)
        texture_word_offset = 6 if variant == "new" else 10
        palette_word_offset = 8 if variant == "new" else 12
        texture_word = struct.unpack_from("<H", opaque, texture_word_offset)[0]
        palette_word = struct.unpack_from("<H", opaque, palette_word_offset)[0]
        struct.pack_into("<H", opaque, texture_word_offset, texture_word ^ 0x8000)
        struct.pack_into("<H", opaque, palette_word_offset, palette_word ^ 0x0001)
        terminator_unknown = len(opaque) - parsed["tileSize"] + 2
        opaque[terminator_unknown] ^= 0x5A
        x_value = _different(tile["x"], -32768, 32767)
        preserved, _ = field_background.apply_edits(
            bytes(opaque), mim, [{"tile": 0, "x": x_value}]
        )
        assert struct.unpack_from("<H", preserved, texture_word_offset)[0] & 0x8000 == \
            struct.unpack_from("<H", opaque, texture_word_offset)[0] & 0x8000
        assert struct.unpack_from("<H", preserved, palette_word_offset)[0] & 1 == \
            struct.unpack_from("<H", opaque, palette_word_offset)[0] & 1
        assert preserved[terminator_unknown] == opaque[terminator_unknown]

    assert {"x", "y", "z", "sourceX", "sourceY", "texture", "palette", "blend",
            "draw", "depth"}.issubset(tested_fields)

    # Independent tile fields merge. A later claimant wins a real collision.
    key, original, mim, parsed = next(iter(samples.values()))
    tile = parsed["tiles"][0]
    x1 = _different(tile["x"], -32768, 32767)
    y1 = _different(tile["y"], -32768, 32767)
    x_mod, _ = field_background.apply_edits(original, mim, [{"tile": 0, "x": x1}])
    y_mod, _ = field_background.apply_edits(original, mim, [{"tile": 0, "y": y1}])
    merged, conflicts, fallback = field_background.merge(
        original, mim, [("x-mod", x_mod), ("y-mod", y_mod)], f"{key}.map"
    )
    assert merged is not None and not conflicts and not fallback
    merged_tile = field_background.read(merged, mim)["tiles"][0]
    assert merged_tile["x"] == x1 and merged_tile["y"] == y1
    x2 = _different(x1, -32768, 32767)
    if x2 == tile["x"]:
        x2 = _different(x2, -32768, 32767)
    x2_mod, _ = field_background.apply_edits(original, mim, [{"tile": 0, "x": x2}])
    collided, conflicts, fallback = field_background.merge(
        original, mim, [("x-mod", x_mod), ("higher", x2_mod)], f"{key}.map"
    )
    assert collided is not None and not fallback
    assert field_background.read(collided, mim)["tiles"][0]["x"] == x2
    assert conflicts == [{
        "unit": f"{key}.map:tile:0:x", "winner": "higher",
        "claimants": ["x-mod", "higher"],
    }]
    unknown_mod = bytearray(original)
    sample_texture_word_offset = 6 if parsed["variant"] == "new" else 10
    unknown_mod[sample_texture_word_offset + 1] ^= 0x80
    assert field_background.merge(
        original, mim, [("opaque", bytes(unknown_mod))], f"{key}.map"
    )[0] is None

    # Render one installed map per storage variant and retain a visual artifact.
    rendered = {}
    output_dir = ROOT / "worklog/issues/rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    for variant, (sample_key, sample_map, sample_mim, sample_parsed) in samples.items():
        image = field_background.render(sample_map, sample_mim)
        assert image.width > 16 and image.height > 16
        assert image.getbbox() is not None
        rendered[variant] = image.size
        if not (output_dir / "goal-ff8-field-background.png").exists():
            image.save(output_dir / "goal-ff8-field-background.png")
        highlighted = field_background.render(
            sample_map, sample_mim, highlight_tile=0
        )
        assert any(pixel == (255, 0, 0) for pixel in highlighted.get_flattened_data())
        png = field_background.render_png(sample_map, sample_mim)
        assert png.startswith(b"\x89PNG\r\n\x1a\n")

    rejected = 0
    sample_key, sample_map, sample_mim, sample_parsed = next(iter(samples.values()))
    for edits in (
        [{"tile": -1, "x": 0}],
        [{"tile": sample_parsed["tileCount"], "x": 0}],
        [{"tile": 0, "texture": 16}],
        [{"tile": 0, "x": 32768}],
        [{"tile": 0, "draw": 1}],
        [{"tile": 0, "unknown": 1}],
        [{"tile": 0}],
        [{"tile": 0, "x": 1}, {"tile": 0, "x": 2}],
    ):
        try:
            field_background.apply_edits(sample_map, sample_mim, edits)
        except ValueError:
            rejected += 1
    assert rejected == 8
    for bad_map, bad_mim in (
        (sample_map[:-1], sample_mim),
        (sample_map, sample_mim[:-1]),
        (b"\xff\x7f" + b"\0" * 14 + sample_map, sample_mim),
    ):
        try:
            field_background.read(bad_map, bad_mim)
        except ValueError:
            rejected += 1
    assert rejected == 11

    print({
        "maps": len(groups), "backgrounds": sum(variants.values()), "missing": missing,
        "variants": dict(variants), "tiles": tile_total,
        "editedFields": sorted(tested_fields), "rejected": rejected,
        "semanticMerge": True, "renders": rendered,
        "artifact": str(output_dir / "goal-ff8-field-background.png"),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
