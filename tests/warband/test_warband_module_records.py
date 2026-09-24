from __future__ import annotations
from pathlib import Path
import tempfile
import unittest

from plugins.warband.module_records import SCHEMAS, dataset_data, save_dataset


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
    "module_party_templates.py": 'party_templates=[("bandits","Bandits",icon_gray_knight,0,fac_outlaws,bandit_personality,[(trp_bandit,3,7)])]\n',
    "module_parties.py": 'parties=[("town","Town",pf_is_static,0,pt_none,fac_neutral,0,ai_bhvr_hold,0,(1.5,2.5),[],90)]\n',
    "module_map_icons.py": 'map_icons=[("player",0,"player",0.15,snd_footstep,0.1,0.2,0)]\n',
    "module_scenes.py": 'scenes=[("arena",sf_generate,"none","none",(-10,-20),(10,20),-1.0,"0x0",[],[],"outer_terrain_plain")]\n',
    "module_scene_props.py": 'scene_props=[("door",spr_use_time(1),"door_mesh","bo_door",[(ti_on_scene_prop_use,[])])]\n',
    "module_mission_templates.py": 'mission_templates=[("battle",mtf_battle_mode,-1,"Battle",[],[])]\n',
    "module_game_menus.py": 'game_menus=[("camp",0,"Camp","none",[],[("leave",[],"Leave",[])])]\n',
    "module_presentations.py": 'presentations=[("sheet",0,mesh_load_window,[])]\n',
    "module_tableau_materials.py": 'tableaus=[("shield",0,"sample",512,256,-128,0,128,256,[])]\n',
    "module_skins.py": 'skins=[("man",0,"body","calf","hand","head",face_keys,["hair"],[],["hair_tex"],[],[],[],"skel_human",1.0)]\n',
    "module_particle_systems.py": 'particle_systems=[("dust",psf_billboard_3d,"dust",5,2.0,10,0.05,10.0,39.0,(0.2,0.5),(1,0),(0,1),(1,1),(0,0.9),(1,0.9),(0,0.78),(1,0.78),(0,2),(1,3.5),(0.2,0.3,0.2),(0,0,3.9),0.5,130,0.5)]\n',
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

    def test_particle_vectors_preserve_tuple_shape_and_optional_fields(self):
        particles = dataset_data(self.root, "particle-systems")
        row = particles["rows"][0]
        self.assertEqual(row["fields"]["emitBox"], [0.2, 0.3, 0.2])
        self.assertEqual(row["fields"]["emitVelocity"], [0, 0, 3.9])
        save_dataset(self.root, "particle-systems", particles["sha256"], [{
            "recordIndex": 0, "originalId": "dust",
            "fields": {"emitBox": [1, 2, 3], "rotationSpeed": 90},
        }])
        text = (self.root / "module_particle_systems.py").read_text()
        self.assertIn("(1, 2, 3)", text)
        reread = dataset_data(self.root, "particle-systems")
        self.assertEqual(reread["rows"][0]["fields"]["emitBox"], [1, 2, 3])
        self.assertEqual(reread["rows"][0]["fields"]["rotationSpeed"], 90)

        scene = dataset_data(self.root, "scenes")
        self.assertEqual(scene["rows"][0]["fields"]["outerTerrain"], "outer_terrain_plain")
        party = dataset_data(self.root, "parties")
        self.assertEqual(party["rows"][0]["fields"]["coordinates"], [1.5, 2.5])
        self.assertEqual(party["rows"][0]["fields"]["direction"], 90)
        icon = dataset_data(self.root, "map-icons")
        self.assertEqual(icon["rows"][0]["fields"]["mesh"], "player")
        self.assertNotIn("offsetX", icon["rows"][0]["fields"])

    def test_helper_generated_records_are_source_only(self):
        # Real Module Systems such as Persistent World use helpers like psys(...).
        # Never treat the helper call argument list as a literal Module System record.
        path = self.root / "module_particle_systems.py"
        path.write_text("""particle_systems=[psys("rain",flags,"mesh",number=500.0,life=0.5,damping=0.3,gravity=1,turbulence_size=10,turbulence_strength=0,alpha=[(1,1),(1,1)],red=[(1,1),(1,1)],green=[(1,1),(1,1)],blue=[(1,1),(1,1)],scale=[(1,1),(1,1)],emit_box=(1,1,1),emit_velocity=(0,0,-10),emit_direction_randomness=0,rotation_speed=0,rotation_damping=.5)]\n""")
        data = dataset_data(self.root, "particle-systems")
        self.assertEqual(len(data["rows"]), 1)
        self.assertIn("helper/wrapper", data["rows"][0]["problem"])
        self.assertTrue(data["rows"][0]["id"].startswith("record@"))
        with self.assertRaisesRegex(ValueError, "source repair"):
            save_dataset(self.root, "particle-systems", data["sha256"], [{
                "recordIndex": 0, "originalId": data["rows"][0]["id"], "fields": {"particleLife": 2},
            }])
        self.assertIn("number=500.0", path.read_text())

    def test_older_particle_shape_is_source_only(self):
        path = self.root / "module_particle_systems.py"
        original = 'particle_systems=[("legacy",0,"mesh",5,2.0,0.1,0.0,1.0,0.5,(0,1),(1,0),(0,1),(1,1),(0,1),(1,1),(0,1),(1,1),(0,1),(1,1),(1,1,1),(0,0,1),0.2)]\n'
        path.write_text(original)
        data = dataset_data(self.root, "particle-systems")
        self.assertEqual(len(data["rows"]), 1)
        self.assertIn("Expected 24 fields; found 22", data["rows"][0]["problem"])
        with self.assertRaisesRegex(ValueError, "source repair"):
            save_dataset(self.root, "particle-systems", data["sha256"], [{
                "recordIndex": 0, "originalId": data["rows"][0]["id"],
                "fields": {"particleLife": 3},
            }])
        self.assertEqual(path.read_text(), original)

    def test_noop_save_does_not_create_backup(self):
        data = dataset_data(self.root, "strings")
        result = save_dataset(self.root, "strings", data["sha256"], [])
        self.assertEqual(result["saved"], 0)
        self.assertFalse((self.root / "module_strings.py.lexeditor.bak").exists())


if __name__ == "__main__":
    unittest.main()
