"""Focused FF7 Accessories regressions for real in-game description text."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from verify_ff7_semantic_surface import SemanticSurfaceTests

import verify_ff7_datasets as fixtures
from games.ff7 import kernel as base
from games.ff7.datasets import Kernel, load_datasets, save_datasets
from games.ff7.format_codec import pack_strings


class AccessoryDescriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / "game"
        self.project = self.root / "project"
        self.source = self.game / fixtures.PATHS[0]

        sections = fixtures.fixture_sections()
        category = base.CATEGORIES["accessories"]
        self.description_index = category.text_description_section - 1
        descriptions = [f"Help{index}" for index in range(fixtures.COUNTS["accessories"])]
        # Keep one raw two-byte game control in the table. Editing another
        # description must preserve this exact semantic byte sequence.
        descriptions[1] = "Keeps \\xF8\\x02 bytes"
        sections[self.description_index] = bytearray(pack_strings(descriptions))
        fixtures.write_kernel(self.source, sections)
        self.original_sections = Kernel(self.source).sections
        self.original_source = self.source.read_bytes()

    def test_accessory_description_is_real_editable_kernel_text(self):
        data = load_datasets(self.game, self.project)
        metadata = {row["id"]: row for row in data["categories"]}
        self.assertTrue(metadata["accessories"]["descriptionEditable"])
        self.assertNotIn("descriptionEditable", metadata["characters"])
        self.assertEqual(data["records"]["accessories"][0]["description"], "Help0")
        self.assertEqual(data["records"]["accessories"][1]["description"], "Keeps \\xF8\\x02 bytes")

        data["records"]["accessories"][0]["description"] = "Actually editable"
        saved = save_datasets(self.game, self.project, data)
        restored = Kernel(Path(saved["path"]))
        rows = restored.records("accessories")
        self.assertEqual(rows[0]["description"], "Actually editable")
        self.assertEqual(rows[1]["description"], "Keeps \\xF8\\x02 bytes")
        self.assertEqual(self.source.read_bytes(), self.original_source)

        for index, (before, after) in enumerate(zip(self.original_sections, restored.sections)):
            if index == self.description_index:
                self.assertNotEqual(after, before)
            else:
                self.assertEqual(after, before, f"unrelated KERNEL section {index + 1} changed")

    def test_invalid_accessory_text_is_transactional(self):
        data = load_datasets(self.game, self.project)
        data["records"]["accessories"][0]["description"] = "Invalid 💥"
        with self.assertRaisesRegex(ValueError, "not in the English FF7 encoding"):
            save_datasets(self.game, self.project, data)
        self.assertFalse(self.project.exists())
        self.assertEqual(self.source.read_bytes(), self.original_source)


from verify_ff7_materia_semantics import MateriaSemanticTests

if __name__ == "__main__":
    unittest.main(verbosity=2)
