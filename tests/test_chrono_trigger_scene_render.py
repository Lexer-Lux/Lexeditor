from __future__ import annotations

import struct
import unittest
import zlib

from games.chrono_trigger.scene_render import png_rgba, render_scene_layer


class FakeStore:
    def __init__(self, resources: dict[str, bytes]):
        self.resources = resources

    def read(self, path: str, source: str = "mine"):
        if path not in self.resources:
            raise KeyError(path)
        return self.resources[path], "archive"

    def exists(self, path: str, source: str = "mine") -> bool:
        return path in self.resources

    def scene_entries(self):
        return [(0, "Game/field/Mapinfo/mapinfo_0.dat")]


def _decode_png_rgba(png: bytes) -> tuple[int, int, bytes]:
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    pos = 8
    width = height = 0
    compressed = bytearray()
    while pos < len(png):
        length = struct.unpack_from(">I", png, pos)[0]
        kind = png[pos + 4:pos + 8]
        payload = png[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height = struct.unpack_from(">II", payload, 0)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = width * 4
    pixels = bytearray()
    for y in range(height):
        row = raw[y * (stride + 1):(y + 1) * (stride + 1)]
        if row[0] != 0:
            raise AssertionError("test decoder only supports PNG filter 0")
        pixels.extend(row[1:])
    return width, height, bytes(pixels)


def _fixture() -> FakeStore:
    # mapinfo: music, tileset L1/2, assembly, L3, palette, palette anim,
    # map index, chip anim, event script, unknown, scrolling.
    scene = bytearray(24)
    struct.pack_into("<H", scene, 2, 1)   # BGSetTable 1
    struct.pack_into("<H", scene, 4, 2)   # ChipTable 2
    struct.pack_into("<H", scene, 8, 3)   # palette 3
    struct.pack_into("<H", scene, 12, 4)  # MapTable 4

    # 16x16 L1, 16x16 L2, no L3; both layers use tile 0.  One RLE property
    # record with repeat 0 means 256 default properties.
    map_table = b"\x00\x00\x00\x00\x00\x00" + bytes(256) + bytes(256) + b"\x80\x00\x00\x00"

    # Slot 0 uses cg5; all other static/animated slots are absent.
    bgset = bytes([5, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

    # A standard 128x64 packed 4bpp sheet filled with palette index 1.
    cg5 = b"CG00" + bytes([0x11]) * (128 * 64 // 2)

    # 512 PC tiles × 4 corners × (u16 chip/palette/flip + u8 priority).
    # Zero means chip 0, palette block 0, no flip, no priority.
    chip_table = bytes(512 * 4 * 3)

    # Two-byte header plus 256 BGR555 colors. Palette index 1 is pure red.
    palette = bytearray(2 + 256 * 2)
    struct.pack_into("<H", palette, 2 + 1 * 2, 0x001F)

    return FakeStore({
        "Game/field/Mapinfo/mapinfo_0.dat": bytes(scene),
        "Game/field/MapTable/MapTable_0004.dat": map_table,
        "Game/field/BGSetTable/bgsettable_1.dat": bgset,
        "Game/field/map_bin/cg5.bin": cg5,
        "Game/field/ChipTable/ChipTable_0002.dat": chip_table,
        "Game/field/palette_bin/plt3.bin": bytes(palette),
    })


class SceneRenderTests(unittest.TestCase):
    def test_png_encoder_round_trips_one_pixel(self):
        png = png_rgba(1, 1, bytes((1, 2, 3, 4)))
        width, height, pixels = _decode_png_rgba(png)
        self.assertEqual((width, height), (1, 1))
        self.assertEqual(pixels, bytes((1, 2, 3, 4)))

    def test_renders_static_pc_scene_layer_with_bgr555_palette(self):
        png, meta = render_scene_layer(_fixture(), 0, 1, "mine")
        width, height, pixels = _decode_png_rgba(png)
        self.assertEqual((width, height), (256, 256))
        self.assertEqual(pixels[:4], bytes((255, 0, 0, 255)))
        self.assertEqual(meta["tileset"], 1)
        self.assertEqual(meta["assembly"], 2)
        self.assertEqual(meta["palette"], 3)
        self.assertFalse(meta["animatedChipsRendered"])

    def test_rejects_layer_three_until_its_separate_tileset_path_is_supported(self):
        with self.assertRaisesRegex(ValueError, "layer 1 or 2"):
            render_scene_layer(_fixture(), 0, 3, "mine")


if __name__ == "__main__":
    unittest.main()
