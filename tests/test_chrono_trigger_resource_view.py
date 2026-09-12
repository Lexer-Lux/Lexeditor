from __future__ import annotations

from types import SimpleNamespace
import unittest

from games.chrono_trigger.resource_view import MAX_RESOURCE_BYTES, read_resource, resource_info


class _Store:
    def __init__(self, rows):
        self.rows = rows

    def read(self, path, source):
        if path not in self.rows:
            raise KeyError(path)
        return self.rows[path], "archive" if source == "vanilla" else "project"


class ResourceViewTests(unittest.TestCase):
    def test_utf8_text_preview(self):
        info = resource_info(_Store({"Localize/en/msg/test.txt": b"0000,Hello\n"}), "Localize/en/msg/test.txt")
        self.assertEqual(info["previewKind"], "text")
        self.assertEqual(info["preview"], "0000,Hello\n")
        self.assertEqual(info["contentType"], "text/plain")
        self.assertFalse(info["previewTruncated"])

    def test_image_is_marked_for_raw_preview(self):
        info = resource_info(_Store({"Game/gfx/test.png": b"\x89PNGfixture"}), "Game/gfx/test.png", "vanilla")
        self.assertEqual(info["previewKind"], "image")
        self.assertEqual(info["contentType"], "image/png")
        self.assertTrue(info["readOnly"])
        self.assertIsNone(info["preview"])

    def test_invalid_utf8_text_degrades_to_binary(self):
        info = resource_info(_Store({"Game/test.txt": b"\xff\xfe"}), "Game/test.txt")
        self.assertEqual(info["previewKind"], "binary")
        self.assertIsNotNone(info["decodeError"])

    def test_direct_read_enforces_decoded_size_limit(self):
        store = _Store({"Game/huge.dat": b"x" * (MAX_RESOURCE_BYTES + 1)})
        with self.assertRaises(RuntimeError):
            read_resource(store, "Game/huge.dat")

    def test_path_traversal_is_rejected_before_store_access(self):
        with self.assertRaises(ValueError):
            read_resource(_Store({}), "../outside.dat")


if __name__ == "__main__":
    unittest.main()
