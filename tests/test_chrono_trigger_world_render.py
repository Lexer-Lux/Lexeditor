from __future__ import annotations

import struct
import unittest
import zlib

from games.chrono_trigger.world_render import render_world_layer
from games.chrono_trigger.worlds import WORLD_HEADER_OFFSET, WORLD_HEADER_SIZE


class FakeStore:
    def __init__(self, resources: dict[str, bytes]):
        self.resources = resources

    def read(self, path: str, source: str = "mine"):
        if path not in self.resources:
            raise KeyError(path)
        return self.resources[path], "archive"


def _png_size_and_first_pixel(png: bytes) -> tuple[int, int, bytes]:
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("not a PNG")
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
    return width, height, raw[1:5]


def _fixture() -> FakeStore:
    bank = bytearray(WORLD_HEADER_OFFSET + 8 * WORLD_HEADER_SIZE + 16)
    start = WORLD_HEADER_OFFSET
    bank[start + 0] = 5
    for index in range(1, 8):
        bank[start + index] = 0x80
    bank[start + 10] = 3  # palette
    bank[start + 16] = 2  # L1/2 assembly
    bank[start + 17] = 4  # map

    map_data = bytes(96 * 64 * 2)
    cg = b"CG00" + bytes([0x11]) * (128 * 64 // 2)
    assembly = bytes(512 * 4 * 2)
    palette = bytearray(2 + 256 * 2)
    struct.pack_into("<H", palette, 2 + 2, 0x001F)  # color index 1 = red
    return FakeStore({
        "Game/common/bankc6.bin": bytes(bank),
        "Game/world/Map/Map_0004.dat": map_data,
        "Game/world/map_bin/cg5.bin": cg,
        "Game/world/Chip/Chip_0002.dat": assembly,
        "Game/world/plt_bin/plt3.bin": bytes(palette),
    })


class WorldRenderTests(unittest.TestCase):
    def test_renders_world_layer_from_header_selected_resources(self):
        png, meta = render_world_layer(_fixture(), 0, 1, "mine")
        width, height, first = _png_size_and_first_pixel(png)
        self.assertEqual((width, height), (1536, 1024))
        self.assertEqual(first, bytes((255, 0, 0, 255)))
        self.assertEqual(meta["map"], 4)
        self.assertEqual(meta["palette"], 3)
        self.assertEqual(meta["assembly"], 2)
        self.assertEqual(meta["chipsets"][0], 5)

    def test_layer_two_uses_upper_tile_bank(self):
        _png, meta = render_world_layer(_fixture(), 0, 2, "mine")
        self.assertEqual(meta["layer"], 2)
        self.assertEqual(meta["tileWidth"], 96)

    def test_rejects_unsupported_world_layer(self):
        with self.assertRaisesRegex(ValueError, "layer 1 or 2"):
            render_world_layer(_fixture(), 0, 3, "mine")


if __name__ == "__main__":
    unittest.main()
