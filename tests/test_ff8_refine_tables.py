"""Refine validation and byte preservation without a proprietary game fixture."""
import unittest
from unittest.mock import patch

from games.ff8 import refine_tables as refine


class RefineSaveTests(unittest.TestCase):
    def setUp(self):
        self.table = refine.Table("sample", "Sample", 4, 24, 28, 32, "item", "item",
                                  (refine.Group("group", "Group", "Sample", 2),))
        self.raw = (b"HEAD" + bytes([0, 0, 1, 0xAC, 0xBD, 2, 3, 4,
                                     2, 0, 5, 0xDE, 0xEF, 6, 7, 8]) + b"\0" * 8 +
                    refine.encode("A") + b"\0" + refine.encode("B") + b"\0" * 29 + b"TAIL")
        self.lookup = patch.object(refine, "BY_KEY", {"sample": self.table})
        self.lookup.start()
        self.addCleanup(self.lookup.stop)

    def test_wrong_value_types_cannot_silently_change_a_recipe(self):
        for field in ("id", "inputId", "outputId", "inputQuantity", "outputQuantity"):
            for value in (0.5, True, "1", None, []):
                edit = {"table": "sample", "id": 0, field: value}
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    refine.apply_edits(self.raw, [edit])
        for value in (None, {}, 12, True):
            with self.subTest(text=value), self.assertRaises(ValueError):
                refine.apply_edits(self.raw, [{"table": "sample", "id": 0, "text": value}])

    def test_numeric_save_changes_only_the_requested_byte(self):
        rebuilt, count = refine.apply_edits(self.raw, [
            {"table": "sample", "id": 1, "inputQuantity": 255}])
        expected = bytearray(self.raw)
        expected[4 + 8 + 6] = 255
        self.assertEqual(rebuilt, bytes(expected))
        self.assertEqual(count, 1)
        self.assertEqual(refine.apply_edits(rebuilt, [
            {"table": "sample", "id": 1, "inputQuantity": 255}]), (rebuilt, 0))

    def test_text_growth_relinks_following_recipe_and_preserves_unknown_bytes(self):
        rebuilt, count = refine.apply_edits(self.raw, [
            {"table": "sample", "id": 0, "text": "Long recipe"}])
        rows = refine._table_rows(rebuilt, self.table)
        self.assertEqual([row["text"] for row in rows], ["Long recipe", "B"])
        self.assertEqual(rows[1]["textOffset"], len(refine.encode("Long recipe")) + 1)
        self.assertEqual([row["unknown"] for row in rows], [0xBDAC, 0xEFDE])
        self.assertEqual(rebuilt[:4], b"HEAD")
        self.assertEqual(rebuilt[-4:], b"TAIL")
        self.assertEqual(len(rebuilt), len(self.raw))
        self.assertEqual(count, 1)

    def test_invalid_batch_and_overflow_are_rejected(self):
        for edits in ([None], [{}], [{"table": [], "id": 0}],
                      [{"table": "sample", "id": 0, "text": "X" * 100}],
                      [{"table": "sample", "id": 0, "outputQuantity": 256}]):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                refine.apply_edits(self.raw, edits)


if __name__ == "__main__":
    unittest.main()
