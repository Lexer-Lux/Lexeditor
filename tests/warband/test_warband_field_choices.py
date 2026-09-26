"""The finite sets a Warband field offers come from the project itself."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plugins.warband import module_records, server


HEADER_ITEMS = """\
itp_type_horse = 0
itp_type_one_handed_wpn = 1
itp_type_shield = 6
itp_merchandise = 0x00000002
itp_civilian = 0x00000010
itp_unique = 0x00000020
imodbits_sword_low = 0x00000001
imodbits_sword_med = 0x00000002
imodbits_sword = imodbits_sword_low|imodbits_sword_med
def weight(x): return x
def spd_rtng(x): return x
"""

HEADER_SKILLS = "sf_looping = 0x00000001\nsf_inactive = 0x00000002\n"

ITEMS = ('items=[["fixture", "Fixture", [("fixture_sword", 0)], '
         'itp_type_one_handed_wpn|itp_merchandise, itc_longsword, 120, '
         'weight(1.5)|spd_rtng(97), imodbits_sword],]\n')

MESHES = 'meshes=[("panel",render_order_plus_1,"panel_mesh",0,0,0,0,0,0,1,1,1)]\n'

SKILLS = 'skills=[("power_strike","Power Strike",sf_looping,10,"Hit harder.")]\n'

SCENES = 'scenes=[("arena",sf_generate,"panel","none",(-10,-20),(10,20),-1.0,"0x0",[],[],"outer_terrain_plain")]\n'


class FieldChoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "header_items.py").write_text(HEADER_ITEMS, encoding="utf-8")
        (self.root / "header_skills.py").write_text(HEADER_SKILLS, encoding="utf-8")
        (self.root / "module_items.py").write_text(ITEMS, encoding="utf-8")
        (self.root / "module_meshes.py").write_text(MESHES, encoding="utf-8")
        (self.root / "module_skills.py").write_text(SKILLS, encoding="utf-8")
        (self.root / "module_scenes.py").write_text(SCENES, encoding="utf-8")

    def test_header_constants_reduce_the_documented_expressions(self):
        symbols = module_records.header_constants(self.root)
        self.assertEqual(symbols["itp_type_one_handed_wpn"], 1)
        self.assertEqual(symbols["itp_civilian"], 16)
        self.assertEqual(symbols["imodbits_sword"], 3)
        self.assertEqual(module_records.header_constants(self.root / "missing"), {})

    def test_item_choices_name_types_flags_bits_stats_and_meshes(self):
        with patch.object(server, "MODULE_SYSTEM", self.root):
            rows = server.item_data()["rows"]
            choices = server.item_choices(rows)
        self.assertEqual([entry["name"] for entry in choices["types"]],
                         ["horse", "one_handed_wpn", "shield"])
        self.assertEqual([entry["name"] for entry in choices["flags"]],
                         ["itp_merchandise", "itp_civilian", "itp_unique"])
        # The bits the header names come first with their values; a name the
        # header does not value (a ready-made combination such as
        # imodbits_sword, or a project that keeps the names elsewhere) is still
        # offered, as text, because the project's own records use it.
        self.assertEqual([entry["name"] for entry in choices["modifierBits"]],
                         ["imodbits_sword_low", "imodbits_sword_med", "imodbits_sword"])
        named = {entry["name"]: entry["value"] for entry in choices["modifierBits"]}
        self.assertEqual(named["imodbits_sword_low"], 1)
        self.assertIsNone(named["imodbits_sword"])
        self.assertEqual(choices["stats"], ["spd_rtng", "weight"])
        self.assertEqual([entry["name"] for entry in choices["meshes"]],
                         ["fixture_sword", "panel", "panel_mesh"])
        panel = [entry for entry in choices["meshes"] if entry["name"] == "panel_mesh"][0]
        self.assertEqual(panel["recordIndex"], 0)

    def test_module_dataset_offers_flags_and_mesh_records(self):
        data = module_records.dataset_data(self.root, "skills")
        flags = data["choices"]["flags"]
        self.assertEqual([entry["name"] for entry in flags["flags"]], ["sf_looping", "sf_inactive"])
        scenes = module_records.dataset_data(self.root, "scenes")
        mesh = scenes["choices"]["mesh"]
        self.assertEqual(mesh["kind"], "mesh")
        self.assertIn("panel_mesh", [entry["name"] for entry in mesh["meshes"]])
        self.assertEqual(mesh["meshes"][0]["recordIndex"], 0)

    def test_a_compiled_project_without_headers_offers_no_sets(self):
        bare = Path(self.temp.name) / "compiled"
        bare.mkdir()
        (bare / "module_skills.py").write_text(SKILLS, encoding="utf-8")
        (bare / "module_meshes.py").write_text(MESHES, encoding="utf-8")
        (bare / "module_scenes.py").write_text(SCENES, encoding="utf-8")
        self.assertEqual(module_records.header_constants(bare), {})
        self.assertEqual(module_records.dataset_data(bare, "skills")["choices"], {})
        # The mesh list is the project's own record list, not a header.
        self.assertIn("mesh", module_records.dataset_data(bare, "scenes")["choices"])


if __name__ == "__main__":
    unittest.main()
