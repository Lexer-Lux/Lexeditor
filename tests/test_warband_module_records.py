from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from games.warband.module_records import SCHEMAS, dataset_data, save_dataset


FIXTURES = {
    "module_skills.py": '''# keep header
skills = [
 ("power_strike","Power Strike",sf_base_att_str,10,"Hit harder."), # keep skill comment
]
''',
    "module_quests.py": 'quests=[("hunt","Hunt",qf_random_quest,"Find them.")]\n',
    "module_strings.py": 'strings=[("hello","Hello"),("bye","Bye")]\n',
    "module_info_pages.py": 'info_pages=[("rules","Rules","Read this.")]\n',
    "module_music.py": 'tracks=[("travel","travel.ogg",mtf_sit_travel,mtf_sit_travel)]\n',
    "module_sounds.py": 'sounds=[("click",0,["click.ogg",["alt.ogg",sf_vol_8]])]\n',
    "module_meshes.py": 'meshes=[("panel",render_order_plus_1,"panel_mesh",0,0,0,0,0,0,1,1,1)]\n',
    "module_factions.py": 'factions=[("kingdom","Kingdom",0,0.9,[("outlaws",-0.5)],[],0xFF00FF)]\n',
    "module_postfx.py": 'postfx_params=[("default",0,3,[1,2,3,4],[5,6,7,8],[9,10,11,12])]\n',
}


class ModuleRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name, content in FIXTURES.items():
            (self.root / name).write_text(content, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_every_declared_schema_parses_real_identity(self):
        for dataset in SCHEMAS:
            with self.subTest(dataset=dataset):
                data = dataset_data(self.root, dataset)
                self.assertTrue(data["available"])
                self.assertTrue(data["rows"])
                self.assertFalse(data["rows"][0]["id"].startswith("record@"))
                self.assertNotIn("problem", data["rows"][0])

    def test_string_roundtrip_changes_only_selected_field(self):
        path = self.root / "module_strings.py"
        data = dataset_data(self.root, "strings")
        result = save_dataset(self.root, "strings", data["sha256"], [{
            "recordIndex": 0, "originalId": "hello", "fields": {"value": "Edited café"},
        }])
        after = path.read_text(encoding="utf-8")
        self.assertEqual(result["saved"], 1)
        self.assertIn('"Edited café"', after)
        self.assertIn('("bye","Bye")', after)
        self.assertTrue((self.root / "module_strings.py.lexeditor.bak").is_file())
        self.assertIn('("hello","Hello")', (self.root / "module_strings.py.lexeditor.bak").read_text())
        self.assertEqual(dataset_data(self.root, "strings")["rows"][0]["fields"]["value"], "Edited café")

    def test_skill_number_is_bounded_and_comment_is_preserved(self):
        path = self.root / "module_skills.py"
        data = dataset_data(self.root, "skills")
        result = save_dataset(self.root, "skills", data["sha256"], [{
            "recordIndex": 0, "originalId": "power_strike", "fields": {"maxLevel": 12},
        }])
        self.assertEqual(result["saved"], 1)
        text = path.read_text(encoding="utf-8")
        self.assertIn('sf_base_att_str,12,"Hit harder.")', text)
        self.assertIn("# keep skill comment", text)
        data = dataset_data(self.root, "skills")
        with self.assertRaisesRegex(ValueError, "at least"):
            save_dataset(self.root, "skills", data["sha256"], [{
                "recordIndex": 0, "originalId": "power_strike", "fields": {"maxLevel": -1},
            }])

    def test_postfx_vector_and_tonemap_roundtrip(self):
        data = dataset_data(self.root, "postfx")
        save_dataset(self.root, "postfx", data["sha256"], [{
            "recordIndex": 0, "originalId": "default",
            "fields": {"tonemap": 2, "params1": [1.5, 2, 3, 4]},
        }])
        reread = dataset_data(self.root, "postfx")
        self.assertEqual(reread["rows"][0]["fields"]["tonemap"], 2)
        self.assertEqual(reread["rows"][0]["fields"]["params1"], [1.5, 2, 3, 4])
        with self.assertRaisesRegex(ValueError, "at most"):
            save_dataset(self.root, "postfx", reread["sha256"], [{
                "recordIndex": 0, "originalId": "default", "fields": {"tonemap": 4},
            }])

    def test_optional_faction_color_is_preserved(self):
        path = self.root / "module_factions.py"
        data = dataset_data(self.root, "factions")
        save_dataset(self.root, "factions", data["sha256"], [{
            "recordIndex": 0, "originalId": "kingdom", "fields": {"name": "New Kingdom"},
        }])
        text = path.read_text(encoding="utf-8")
        self.assertIn("0xFF00FF", text)
        self.assertIn('[("outlaws",-0.5)]', text)

    def test_stale_hash_and_identity_changes_are_rejected(self):
        data = dataset_data(self.root, "strings")
        path = self.root / "module_strings.py"
        path.write_text(path.read_text() + "# concurrent\n")
        with self.assertRaisesRegex(ValueError, "changed; reload"):
            save_dataset(self.root, "strings", data["sha256"], [])
        data = dataset_data(self.root, "strings")
        with self.assertRaisesRegex(ValueError, "identity changed"):
            save_dataset(self.root, "strings", data["sha256"], [{
                "recordIndex": 0, "originalId": "wrong", "fields": {"value": "No"},
            }])

    def test_duplicate_ids_block_structured_save(self):
        path = self.root / "module_strings.py"
        path.write_text('strings=[("dup","One"),("dup","Two")]\n')
        data = dataset_data(self.root, "strings")
        self.assertTrue(all("Duplicate ID" in row.get("problem", "") for row in data["rows"]))
        with self.assertRaisesRegex(ValueError, "source repair"):
            save_dataset(self.root, "strings", data["sha256"], [{
                "recordIndex": 0, "originalId": "dup", "fields": {"value": "No"},
            }])

    def test_noop_save_does_not_create_backup(self):
        data = dataset_data(self.root, "strings")
        result = save_dataset(self.root, "strings", data["sha256"], [])
        self.assertEqual(result["saved"], 0)
        self.assertFalse((self.root / "module_strings.py.lexeditor.bak").exists())


if __name__ == "__main__":
    unittest.main()
