from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.palettes import (
    decode_bgr555,
    encode_bgr555,
    load_palette,
    palette_path,
    save_palette_color,
)


class FakeStore:
    def __init__(self, resources: dict[str, bytes]):
        self.resources = dict(resources)
        self.writes: dict[str, bytes] = {}

    def read(self, path: str, source: str = "mine"):
        if source != "vanilla" and path in self.writes:
            return self.writes[path], "project"
        if path not in self.resources:
            raise KeyError(path)
        return self.resources[path], "archive"

    def write(self, path: str, data: bytes):
        self.writes[path] = bytes(data)
        return Path(path)


def _palette(*, high_bit_index: int | None = None, trailing: bytes = b"") -> bytes:
    raw = bytearray(b"PH" + bytes(512) + trailing)
    struct.pack_into("<H", raw, 2 + 1 * 2, 0x001F)  # red
    struct.pack_into("<H", raw, 2 + 2 * 2, 0x03E0)  # green
    struct.pack_into("<H", raw, 2 + 3 * 2, 0x7C00)  # blue
    if high_bit_index is not None:
        offset = 2 + high_bit_index * 2
        value = struct.unpack_from("<H", raw, offset)[0]
        struct.pack_into("<H", raw, offset, value | 0x8000)
    return bytes(raw)


class PaletteCodecTests(unittest.TestCase):
    def test_primary_bgr555_colors_decode_to_rgb(self):
        self.assertEqual(decode_bgr555(0x001F), (255, 0, 0))
        self.assertEqual(decode_bgr555(0x03E0), (0, 255, 0))
        self.assertEqual(decode_bgr555(0x7C00), (0, 0, 255))
        self.assertEqual(decode_bgr555(0x7FFF), (255, 255, 255))

    def test_rgb_encoding_quantizes_to_five_bits_per_component(self):
        raw = encode_bgr555(255, 128, 0)
        red, green, blue = decode_bgr555(raw)
        self.assertEqual(red, 255)
        self.assertLessEqual(abs(green - 128), 5)
        self.assertEqual(blue, 0)

    def test_rgb_encoding_validates_components(self):
        with self.assertRaisesRegex(ValueError, "Red must be between"):
            encode_bgr555(300, 0, 0)

    def test_palette_paths_are_explicit_by_domain(self):
        self.assertEqual(palette_path("scene", 12), "Game/field/palette_bin/plt12.bin")
        self.assertEqual(palette_path("world", 4), "Game/world/plt_bin/plt4.bin")
        with self.assertRaisesRegex(ValueError, "scene.*world"):
            palette_path("battle", 1)


class PaletteEditorTests(unittest.TestCase):
    def test_load_preserves_header_and_reports_trailing_bytes(self):
        path = palette_path("scene", 3)
        store = FakeStore({path: _palette(trailing=b"TAIL")})
        payload = load_palette(store, "scene", 3)
        self.assertEqual(payload["headerHex"], "50 48")
        self.assertEqual(payload["trailingBytes"], 4)
        self.assertEqual(payload["colors"][1]["hex"], "#FF0000")
        self.assertEqual(payload["colors"][2]["hex"], "#00FF00")
        self.assertEqual(payload["colors"][3]["hex"], "#0000FF")

    def test_rgb_write_changes_only_one_color_word(self):
        path = palette_path("scene", 3)
        original = _palette(trailing=b"TAIL")
        store = FakeStore({path: original})
        result = save_palette_color(
            store, "scene", 3, 1, sha256(original),
            {"red": 0, "green": 255, "blue": 255},
        )
        written = store.writes[path]
        self.assertEqual(len(written), len(original))
        self.assertEqual(written[:2], b"PH")
        self.assertEqual(written[-4:], b"TAIL")
        self.assertEqual(written[2 + 2 * 2:2 + 4 * 2], original[2 + 2 * 2:2 + 4 * 2])
        self.assertEqual(result["savedColor"]["hex"], "#00FFFF")

    def test_partial_rgb_write_uses_current_other_components(self):
        path = palette_path("scene", 3)
        original = _palette()
        store = FakeStore({path: original})
        result = save_palette_color(store, "scene", 3, 1, sha256(original), {"green": 255})
        saved = result["savedColor"]
        self.assertEqual((saved["red"], saved["green"], saved["blue"]), (255, 255, 0))

    def test_raw_write_preserves_existing_high_bit(self):
        path = palette_path("world", 4)
        original = _palette(high_bit_index=1)
        store = FakeStore({path: original})
        result = save_palette_color(store, "world", 4, 1, sha256(original), {"raw": 0x03E0})
        saved = result["savedColor"]
        self.assertTrue(saved["highBit"])
        self.assertEqual(saved["stored"], 0x83E0)
        self.assertEqual(saved["hex"], "#00FF00")

    def test_raw_and_rgb_in_same_patch_are_rejected(self):
        path = palette_path("scene", 1)
        original = _palette()
        store = FakeStore({path: original})
        with self.assertRaisesRegex(ValueError, "either raw BGR555 or RGB"):
            save_palette_color(store, "scene", 1, 0, sha256(original), {"raw": 1, "red": 2})
        self.assertEqual(store.writes, {})

    def test_stale_sha_is_rejected_before_write(self):
        path = palette_path("world", 1)
        store = FakeStore({path: _palette()})
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            save_palette_color(store, "world", 1, 0, "0" * 64, {"raw": 1})
        self.assertEqual(store.writes, {})

    def test_truncated_palette_is_rejected(self):
        path = palette_path("scene", 1)
        store = FakeStore({path: b"PH" + bytes(10)})
        with self.assertRaisesRegex(ValueError, "truncated"):
            load_palette(store, "scene", 1)

    def test_color_index_is_validated(self):
        path = palette_path("scene", 1)
        original = _palette()
        store = FakeStore({path: original})
        with self.assertRaisesRegex(ValueError, "between 0 and 255"):
            save_palette_color(store, "scene", 1, 256, sha256(original), {"raw": 0})


if __name__ == "__main__":
    unittest.main()
