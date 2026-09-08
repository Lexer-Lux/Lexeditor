from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.warband import server


SOURCE = """from header_items import *
items = [
  ["sword", "Old Sword", [("sword_mesh", 0)],
   itp_type_one_handed_wpn|itp_merchandise,
   itc_longsword, 120,
   weight(1.5)|spd_rtng(97)|weapon_length(90), imodbits_sword],
  ["boots", "Old Boots", [("boot_mesh", 0)], itp_type_foot_armor,
   0, 75, weight(1.0)|leg_armor(12), imodbits_cloth],
]
"""


class WarbandItemEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.mkdir(exist_ok=True)
        self.path = self.root / "module_items.py"; self.path.write_text(SOURCE, encoding="utf-8")
        patcher = patch.object(server, "MODULE_SYSTEM", self.root); patcher.start(); self.addCleanup(patcher.stop)

    def test_multiline_records_expose_actual_fields(self):
        rows = server.item_rows()
        self.assertEqual([row["id"] for row in rows], ["sword", "boots"])
        sword = rows[0]
        self.assertEqual(sword["type"], "one_handed_wpn")
        self.assertEqual(sword["weight"], "1.5")
        self.assertEqual(sword["inventoryMesh"], "sword_mesh")
        self.assertEqual(sword["fields"]["capabilities"], "itc_longsword")
        self.assertIn("weapon_length(90)", sword["fields"]["stats"])
        self.assertEqual(sword["fieldOrder"][:8], ["id","name","meshes","flags","capabilities","value","stats","modifierBits"])

    def test_structured_save_changes_only_requested_fields_and_makes_backup(self):
        original = self.path.read_bytes()
        result = server.save_item_edits([{
            "recordIndex": 0, "originalId": "sword", "fields": {
                "name": "New Sword", "value": "250",
                "flags": "itp_type_two_handed_wpn|itp_merchandise",
                "stats": "weight(2.25)|spd_rtng(91)|weapon_length(115)",
            }
        }])
        self.assertEqual(result["saved"], 1)
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        rows = server.item_rows(); sword, boots = rows
        self.assertEqual(sword["name"], "New Sword")
        self.assertEqual(sword["value"], "250")
        self.assertEqual(sword["type"], "two_handed_wpn")
        self.assertEqual(sword["weight"], "2.25")
        self.assertEqual(boots["name"], "Old Boots")
        self.assertIn('itp_type_foot_armor', boots["fields"]["flags"])

    def test_stale_record_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "changed from wrong"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "wrong", "fields": {"value": "1"}}])

    def test_invalid_expression_and_duplicate_id_are_rejected_without_write(self):
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"stats": "weight(1), bad"}}])
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "duplicate item IDs"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"id": "boots"}}])
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
