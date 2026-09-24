"""The Field tab's walkmesh overlay aligns with the background preview.

Deling draws tile (x, y) at canvas pixel (bounds.left + x, bounds.top + y).
The overlay adds the geometry origin to its centred camera-projected points,
so geometry must match the preview canvas exactly, including under tile edits.
"""
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.ff8 import field_background, field_data


def _tile(x, y):
    return struct.pack("<hhHHHBBBBBB", x, y, 0, 0x10, 0, 0, 0, 0, 1, 255, 0)


def _map(*tiles):
    body = b"".join(_tile(*tile) for tile in tiles)
    return body + struct.pack("<hhHHHBBBBBB", 0x7FFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


class BackgroundGeometryTests(unittest.TestCase):
    def _paths(self, root, raw):
        map_path = root / "mapa.map"
        mim_path = root / "mapa.mim"
        map_path.write_bytes(raw)
        mim_path.write_bytes(bytes(field_background.NEW_MIM_SIZE))
        return map_path, mim_path

    def test_geometry_matches_preview_canvas(self):
        raw = _map((-32, -16), (320, 224))
        with tempfile.TemporaryDirectory() as name:
            paths = self._paths(Path(name), raw)
            with patch.object(field_data, "_background_source_paths",
                              return_value=paths):
                geometry = field_data.background_geometry("grp/mapa")
                preview = field_data.background_png("grp/mapa")
        self.assertEqual(
            geometry, {"left": 32, "top": 16, "width": 368, "height": 256})
        from PIL import Image
        from io import BytesIO
        self.assertEqual(Image.open(BytesIO(preview)).size, (368, 256))

    def test_geometry_follows_tile_edits(self):
        raw = _map((-32, -16), (320, 224))
        with tempfile.TemporaryDirectory() as name:
            paths = self._paths(Path(name), raw)
            with patch.object(field_data, "_background_source_paths",
                              return_value=paths):
                geometry = field_data.background_geometry(
                    "grp/mapa", "current", [{"tile": 1, "x": 400}])
        self.assertEqual(
            geometry, {"left": 32, "top": 16, "width": 448, "height": 256})

    def test_missing_background_and_bad_edits_raise(self):
        with patch.object(field_data, "_background_source_paths",
                          return_value=(None, None)):
            with self.assertRaisesRegex(ValueError, "has no background"):
                field_data.background_geometry("grp/mapa")
        raw = _map((0, 0))
        with tempfile.TemporaryDirectory() as name:
            paths = self._paths(Path(name), raw)
            with patch.object(field_data, "_background_source_paths",
                              return_value=paths):
                with self.assertRaisesRegex(ValueError, "must be an object"):
                    field_data.background_geometry("grp/mapa", "current", [7])


if __name__ == "__main__":
    unittest.main()
