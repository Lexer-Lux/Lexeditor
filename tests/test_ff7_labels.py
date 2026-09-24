"""FF7 editor language: Perms, lock-to-one-side help, DMG/Heal Formula."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from plugins.ff7 import semantics  # noqa: E402


class FF7LabelTests(unittest.TestCase):
    def test_restrictions_are_perms(self):
        for category in ("items", "weapons", "armor", "accessories"):
            field = semantics.metadata_for(category, "restrictions")
            self.assertEqual(field["label"], "Perms", category)
            self.assertEqual(field["group"], "Perms", category)
            self.assertEqual(
                [flag["label"] for flag in field["flags"]],
                ["Sellable", "Usable in battle", "Usable in menu", "Throwable"],
                category,
            )
            self.assertIn("sold", field["help"])
            self.assertIn("thrown", field["help"])


if __name__ == "__main__":
    unittest.main()
