from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from games.chrono_trigger.data import OverlayStore
from games.chrono_trigger.plugin import _build_smoke_archive
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


def _fixture(*, layer3: bool = True) -> FakeStore:
    # mapinfo: music, tileset L1/2, assembly, L3, palette, palette anim,
    # map index, chip anim, event script, unknown, scrolling.
    scene = bytearray(24)
    struct.pack_into("<H", scene, 2, 1)   # BGSetTable 1
    struct.pack_into("<H", scene, 4, 2)   # ChipTable 2
    struct.pack_into("<H", scene, 6, 9)   # dedicated L3 weather cg9
    struct.pack_into("<H", scene, 8, 3)   # palette 3
    struct.pack_into("<H", scene, 12, 4)  # MapTable 4

    # 16x16 L1/L2 and optionally 16x16 L3. All layers use tile 0.
    # One RLE property record with repeat 0 means 256 default properties.
    bits = 0x80 if layer3 else 0x00
    map_table = bytes((0x00, bits, 0x00, 0x00, 0x00, 0x00))
    map_table += bytes(256) + bytes(256)
    if layer3:
        map_table += bytes(256)
    map_table += b"\x80\x00\x00\x00"

    # Slot 0 uses cg5; all other static/animated slots are absent.
    bgset = bytes([5, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])

    # PC cg files skip a four-byte header, then CTViewer nibble-unpacks them.
    cg5 = b"CG00" + bytes([0x11]) * (128 * 64 // 2)
    # L3 is logically 2bpp, so use only values 0..3 in each nibble.
    cg9 = b"CG00" + bytes([0x22]) * (128 * 64 // 2)

    # PC assembly records: u16 chip/palette/flip + u8 priority per corner.
    chip_table = bytes(512 * 4 * 3)
    chip_table_l3 = bytes(256 * 4 * 3)

    # Two-byte header plus 256 BGR555 colors.
    # Palette index 1 is pure red; L3 pixel index 2 is pure green.
    palette = bytearray(2 + 256 * 2)
    struct.pack_into("<H", palette, 2 + 1 * 2, 0x001F)
    struct.pack_into("<H", palette, 2 + 2 * 2, 0x03E0)

    return FakeStore({
        "Game/field/Mapinfo/mapinfo_0.dat": bytes(scene),
        "Game/field/MapTable/MapTable_0004.dat": map_table,
        "Game/field/BGSetTable/bgsettable_1.dat": bgset,
        "Game/field/map_bin/cg5.bin": cg5,
        "Game/field/weather_bin/cg9.bin": cg9,
        "Game/field/ChipTable/ChipTable_0002.dat": chip_table,
        "Game/field/ChipTable/ChipTableBg3_0000.dat": chip_table_l3,
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
        self.assertEqual(meta["paletteGroupSize"], 16)
        self.assertFalse(meta["animatedChipsRendered"])

    def test_renders_pc_scene_layer_three_from_weather_and_scene_indexed_assembly(self):
        png, meta = render_scene_layer(_fixture(), 0, 3, "mine")
        width, height, pixels = _decode_png_rgba(png)
        self.assertEqual((width, height), (256, 256))
        self.assertEqual(pixels[:4], bytes((0, 255, 0, 255)))
        self.assertEqual(meta["tileset"], 9)
        self.assertEqual(meta["assembly"], 0)
        self.assertEqual(meta["assemblyPath"], "Game/field/ChipTable/ChipTableBg3_0000.dat")
        self.assertEqual(meta["graphicsPath"], "Game/field/weather_bin/cg9.bin")
        self.assertEqual(meta["paletteGroupSize"], 4)
        self.assertEqual(meta["logicalBitsPerPixel"], 2)
        self.assertEqual(meta["composition"], "isolated-layer")

    def test_renders_layer_three_through_real_arc1_overlay_store(self):
        fixture = _fixture()
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-l3-") as temp_name:
            root = Path(temp_name)
            archive = root / "resources.bin"
            _build_smoke_archive(archive, list(fixture.resources.items()))
            store = OverlayStore(archive, root / "project")
            png, meta = render_scene_layer(store, 0, 3, "mine")
            width, height, pixels = _decode_png_rgba(png)
            self.assertEqual((width, height), (256, 256))
            self.assertEqual(pixels[:4], bytes((0, 255, 0, 255)))
            self.assertEqual(meta["graphicsPath"], "Game/field/weather_bin/cg9.bin")

    def test_rejects_layer_three_when_map_does_not_enable_it(self):
        with self.assertRaisesRegex(ValueError, "does not enable layer 3"):
            render_scene_layer(_fixture(layer3=False), 0, 3, "mine")

    def test_rejects_unknown_layer(self):
        with self.assertRaisesRegex(ValueError, "layer 1, 2, or 3"):
            render_scene_layer(_fixture(), 0, 4, "mine")


if __name__ == "__main__":
    unittest.main()
