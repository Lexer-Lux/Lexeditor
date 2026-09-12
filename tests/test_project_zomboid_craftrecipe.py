from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, craftrecipe


class ProjectZomboidCraftRecipeTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        project = root / "mod"
        scripts = project / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (project / "42" / "mod.info").write_text("name=Test\nid=Test\n", encoding="utf-8")
        (scripts / "craft.txt").write_text(
            '''module Base\n{\n'''
            '''  craftRecipe SawLogs\n  {\n'''
            '''    AllowBatchCraft = true,\n'''
            '''    CanWalk = false,\n'''
            '''    category = Carpentry,\n'''
            '''    Icon = Item_Plank,\n'''
            '''    ResearchSkillLevel = -1,\n'''
            '''    Tags = InHandCraft;CanBeDoneFromFloor,\n'''
            '''    Time = 230,\n'''
            '''    timedAction = SawLogs,\n'''
            '''    FutureField = KeepMe,\n'''
            '''    inputs\n    {\n      item 1 [Base.Log],\n    }\n'''
            '''    outputs\n    {\n      item 3 Base.Plank,\n    }\n'''
            '''  }\n}\n''', encoding="utf-8")
        return project

    def test_surgical_edit_preserves_nested_inputs_outputs_and_property_casing(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = craftrecipe.read(root)["rows"][0]
            self.assertEqual(row["fields"]["time"], "230")
            self.assertEqual(row["fields"]["tags"], "InHandCraft;CanBeDoneFromFloor")
            saved = craftrecipe.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"AllowBatchCraft": "false", "time": "120", "tags": "InHandCraft;CanBeDoneInDark"},
            )
            text = (root / row["path"]).read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["AllowBatchCraft"], "false")
            self.assertEqual(saved["fields"]["time"], "120")
            self.assertEqual(saved["fields"]["tags"], "InHandCraft;CanBeDoneInDark")
            self.assertTrue(saved["hasInputs"])
            self.assertTrue(saved["hasOutputs"])
            self.assertIn("    Time = 120,", text)
            self.assertIn("    Tags = InHandCraft;CanBeDoneInDark,", text)
            self.assertIn("item 1 [Base.Log]", text)
            self.assertIn("item 3 Base.Plank", text)
            self.assertIn("FutureField = KeepMe,", text)

    def test_case_only_duplicate_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "craft.txt"
            script.write_text(
                script.read_text(encoding="utf-8").replace("    Time = 230,\n", "    Time = 230,\n    time = 50,\n"),
                encoding="utf-8",
            )
            row = craftrecipe.read(root)["rows"][0]
            self.assertIn("time", row["duplicateKeys"])
            with self.assertRaisesRegex(core.ProjectZomboidError, "duplicated craftRecipe properties: time"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"time": "120"})

    def test_unknown_current_boolean_value_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "craft.txt"
            script.write_text(
                script.read_text(encoding="utf-8").replace("AllowBatchCraft = true", "AllowBatchCraft = future"),
                encoding="utf-8",
            )
            row = craftrecipe.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "AllowBatchCraft=future"):
                craftrecipe.save(
                    root, row["path"], row["module"], row["id"], row["sha256"],
                    {"AllowBatchCraft": "true", "time": "120"},
                )
            self.assertIn("AllowBatchCraft = future", script.read_text(encoding="utf-8"))

    def test_typed_validation(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            row = craftrecipe.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "true or false"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"CanWalk": "yes"})
            with self.assertRaisesRegex(core.ProjectZomboidError, "integer"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"time": "2.5"})
            with self.assertRaisesRegex(core.ProjectZomboidError, "tags cannot be empty"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"tags": ""})

    def test_missing_fields_and_stale_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            root = self.make_project(Path(name))
            script = root / "42" / "media" / "scripts" / "craft.txt"
            script.write_text(script.read_text(encoding="utf-8").replace("    Icon = Item_Plank,\n", ""), encoding="utf-8")
            row = craftrecipe.read(root)["rows"][0]
            with self.assertRaisesRegex(core.ProjectZomboidError, "missing: Icon"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"Icon": "Other"})
            script.write_text(script.read_text(encoding="utf-8") + "// external\n", encoding="utf-8")
            with self.assertRaisesRegex(core.ProjectZomboidError, "changed outside Lexeditor"):
                craftrecipe.save(root, row["path"], row["module"], row["id"], row["sha256"], {"time": "50"})


if __name__ == "__main__":
    unittest.main()
