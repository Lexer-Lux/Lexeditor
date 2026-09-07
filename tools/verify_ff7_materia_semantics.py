"""FF7 Materia semantic UI metadata and binary mapping regressions."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import verify_ff7_datasets as fixtures
from games.ff7 import kernel as base
from games.ff7.datasets import Kernel


class MateriaSemanticTests(unittest.TestCase):
    def test_metadata_exposes_human_controls_not_storage_integers(self):
        materia = next(category for category in base.category_metadata() if category["id"] == "materia")
        fields = {field["key"]: field for field in materia["fields"]}
        self.assertEqual(fields["equipEffect"]["label"], "Stats while equipped")
        self.assertEqual(fields["equipEffect"]["dataType"], "enum")
        self.assertEqual(fields["statusFlags"]["label"], "Status effects")
        self.assertEqual(fields["statusFlags"]["dataType"], "flags")
        self.assertEqual(len(fields["statusFlags"]["flags"]), 24)
        self.assertIn({"value": 1 << 3, "label": "Poison"}, fields["statusFlags"]["flags"])
        self.assertEqual(fields["materiaType"]["label"], "Materia behavior")
        self.assertEqual(fields["materiaType"]["dataType"], "enum")
        self.assertIn({"value": 0x19, "label": "Magic"}, fields["materiaType"]["choices"])
        self.assertEqual(fields["element"]["dataType"], "enum")
        self.assertIn({"value": 0x02, "label": "Lightning"}, fields["element"]["choices"])
        for index in range(1, 7):
            field = fields[f"attribute{index}"]
            self.assertEqual(field["label"], f"Behavior parameter {index}")
            self.assertEqual(field["group"], "Advanced behavior data")

    def test_semantic_values_map_to_exact_existing_bytes(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "KERNEL.BIN"
            fixtures.write_kernel(path)
            kernel = Kernel(path)
            before = bytes(kernel.sections[8])
            rows = kernel.records("materia")
            row = rows[0]
            row["values"]["equipEffect"] = 0x06
            row["values"]["statusFlags"] = (1 << 3) | (1 << 7)
            row["values"]["element"] = 0x02
            row["values"]["materiaType"] = 0x19
            kernel.apply("materia", rows)
            expected = bytearray(before)
            expected[0x08] = 0x06
            expected[0x09:0x0C] = ((1 << 3) | (1 << 7)).to_bytes(3, "little")
            expected[0x0C] = 0x02
            expected[0x0D] = 0x19
            self.assertEqual(kernel.sections[8], expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
