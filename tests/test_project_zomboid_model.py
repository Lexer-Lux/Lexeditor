from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, model


SCRIPT = """module LexTest
{
    model FancyModel
    {
        cullFace = Back,
        invertX = false,
        postProcess = +TRIANGULATE;-FIND_INSTANCES,
        scale = 1.0,
        shader = vehicle,
        static = true,
        undoCoreScale = false,
        mesh = LexTest/FancyModel,
        texture = LexTest/FancyTexture,
        attachment Grip
        {
            offset = 0.0 0.0 0.0,
            rotate = 0.0 0.0 0.0,
        }
    }
}
"""


class ProjectZomboidModelTests(unittest.TestCase):
    def make_project(self, parent: Path, text: str = SCRIPT) -> tuple[Path, Path]:
        root = parent / "Model Mod"
        scripts = root / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        path = scripts / "models.txt"
        path.write_text(text, encoding="utf-8")
        return root, path

    def test_surgical_edit_preserves_attachment_and_unmodeled_paths(self):
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name))
            row = model.read(root)["rows"][0]
            before = path.read_text(encoding="utf-8")
            saved = model.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"scale": "1.25", "static": "false"},
            )
            after = path.read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["scale"], "1.25")
            self.assertEqual(saved["fields"]["static"], "false")
            self.assertTrue(saved["hasAttachments"])
            self.assertIn("mesh = LexTest/FancyModel,", after)
            self.assertIn("texture = LexTest/FancyTexture,", after)
            self.assertIn("attachment Grip", after)
            self.assertIn("offset = 0.0 0.0 0.0,", after)
            self.assertEqual(
                before.replace("scale = 1.0,", "scale = 1.25,").replace("static = true,", "static = false,"),
                after,
            )

    def test_missing_duplicate_and_stale_edits_fail_closed(self):
        missing = """module LexTest
{
    model MissingScale
    {
        shader = vehicle,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name), missing)
            row = model.read(root)["rows"][0]
            with self.assertRaises(core.ProjectZomboidError):
                model.save(root, row["path"], row["module"], row["id"], row["sha256"], {"scale": "2"})
            path.write_text(path.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
            with self.assertRaises(core.ProjectZomboidError):
                model.save(root, row["path"], row["module"], row["id"], row["sha256"], {"shader": "animalEffect"})

        duplicate = """module LexTest
{
    model Duplicate
    {
        shader = vehicle,
        shader = door,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), duplicate)
            row = model.read(root)["rows"][0]
            self.assertEqual(row["duplicateKeys"], ["shader"])
            with self.assertRaises(core.ProjectZomboidError):
                model.save(root, row["path"], row["module"], row["id"], row["sha256"], {"shader": "animalEffect"})

    def test_validation_uses_documented_types_and_cull_modes(self):
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name))
            row = model.read(root)["rows"][0]
            invalid = [
                ("cullFace", "Both"),
                ("invertX", "yes"),
                ("static", "1"),
                ("undoCoreScale", "no"),
                ("scale", "nan"),
                ("shader", "vehicle,door"),
            ]
            for key, value in invalid:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(core.ProjectZomboidError):
                        model.save(root, row["path"], row["module"], row["id"], row["sha256"], {key: value})

    def test_nested_vehicle_models_comments_and_strings_are_not_records(self):
        text = """module LexTest
{
    // model Commented { scale = 1, }
    item Note
    {
        DisplayCategory = \"model StringFake { scale = 1, }\",
    }
    vehicle Car
    {
        model Nested
        {
            scale = 1,
        }
    }
    model Real
    {
        scale = 1,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), text)
            result = model.read(root)
            self.assertEqual(result["errors"], [])
            self.assertEqual([(row["module"], row["id"]) for row in result["rows"]], [("LexTest", "Real")])


if __name__ == "__main__":
    unittest.main()
