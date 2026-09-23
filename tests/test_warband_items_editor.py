from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plugins.warband import server


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

DUPLICATE_SOURCE = """items = [
  ["same", "First", [("first_mesh", 0)], itp_type_goods, 0, 10, weight(1), 0],
  ["same", "Second", [("second_mesh", 0)], itp_type_goods, 0, 20, weight(2), 0],
]
"""


class WarbandItemEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.mkdir(exist_ok=True)
        self.path = self.root / "module_items.py"; self.path.write_text(SOURCE, encoding="utf-8")
        patcher = patch.object(server, "MODULE_SYSTEM", self.root); patcher.start(); self.addCleanup(patcher.stop)

    def test_multiline_records_expose_actual_fields_and_source_hash(self):
        data = server.item_data();rows=data["rows"]
        self.assertTrue(data["sha256"])
        self.assertEqual([row["id"] for row in rows], ["sword", "boots"])
        sword = rows[0]
        self.assertEqual(sword["type"], "one_handed_wpn")
        self.assertEqual(sword["weight"], "1.5")
        self.assertEqual(sword["inventoryMesh"], "sword_mesh")
        self.assertEqual(sword["fields"]["capabilities"], "itc_longsword")
        self.assertIn("weapon_length(90)", sword["fields"]["stats"])
        self.assertEqual(sword["fieldOrder"][:8], ["id","name","meshes","flags","capabilities","value","stats","modifierBits"])

    def test_structured_save_changes_only_requested_fields_and_makes_backup(self):
        original = self.path.read_bytes();data=server.item_data()
        result = server.save_item_edits([{
            "recordIndex": 0, "originalId": "sword", "fields": {
                "name": "New café Sword", "value": "250",
                "flags": "itp_type_two_handed_wpn|itp_merchandise",
                "stats": "weight(2.25)|spd_rtng(91)|weapon_length(115)",
            }
        }],data["sha256"])
        self.assertEqual(result["saved"], 1)
        self.assertTrue(result["sha256"])
        self.assertEqual(Path(result["backup"]).read_bytes(), original)
        rows = server.item_rows(); sword, boots = rows
        self.assertEqual(sword["name"], "New café Sword")
        self.assertTrue(self.path.read_text(encoding="utf-8").startswith("# coding: utf-8\n"))
        self.assertEqual(sword["value"], "250")
        self.assertEqual(sword["type"], "two_handed_wpn")
        self.assertEqual(sword["weight"], "2.25")
        self.assertEqual(boots["name"], "Old Boots")
        self.assertIn('itp_type_foot_armor', boots["fields"]["flags"])

    def test_stale_record_identity_is_rejected(self):
        data=server.item_data()
        with self.assertRaisesRegex(ValueError, "changed from wrong"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "wrong", "fields": {"value": "1"}}],data["sha256"])

    def test_stale_source_hash_is_rejected_without_write(self):
        data=server.item_data()
        self.path.write_text(self.path.read_text()+"# concurrent\n")
        concurrent=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,"changed; reload"):
            server.save_item_edits([{"recordIndex":0,"originalId":"sword","fields":{"value":"1"}}],data["sha256"])
        self.assertEqual(self.path.read_bytes(),concurrent)

    def test_invalid_expression_and_fixed_id_are_rejected_without_write(self):
        data=server.item_data();original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"stats": "weight(1), bad"}}],data["sha256"])
        self.assertEqual(self.path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "IDs are fixed"):
            server.save_item_edits([{"recordIndex": 0, "originalId": "sword", "fields": {"id": "boots"}}],data["sha256"])
        self.assertEqual(self.path.read_bytes(), original)

    def test_preexisting_duplicate_ids_preserve_identity_and_edit_by_record_index(self):
        self.path.write_text(DUPLICATE_SOURCE)
        before=self.path.read_bytes();data=server.item_data()
        self.assertEqual([row["id"] for row in data["rows"]],["same","same"])
        result=server.save_item_edits([{
            "recordIndex":1,"originalId":"same","fields":{"name":"Edited second","value":"25"}
        }],data["sha256"])
        self.assertEqual(result["saved"],1)
        rows=server.item_rows()
        self.assertEqual([(row["id"],row["name"],row["value"]) for row in rows],
                         [("same","First","10"),("same","Edited second","25")])
        self.assertEqual(Path(result["backup"]).read_bytes(),before)

    def test_noop_save_does_not_create_backup(self):
        data=server.item_data()
        result=server.save_item_edits([],data["sha256"])
        self.assertEqual(result["saved"],0)
        self.assertFalse((self.root/"module_items.py.lexeditor.bak").exists())


if __name__ == "__main__":
    unittest.main()
