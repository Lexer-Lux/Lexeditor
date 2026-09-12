from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, mannequin


SCRIPT = """module LexTest
{
    mannequin StoreDisplay
    {
        animSet = mannequin,
        animState = female,
        female = true,
        model = FemaleBody,
        outfit = Casual,
        pose = pose01,
        texture = FemaleBody01,
        FutureField = KeepMe,
    }
}
"""


class ProjectZomboidMannequinTests(unittest.TestCase):
    def make_project(self, parent: Path, text: str = SCRIPT) -> tuple[Path, Path]:
        root = parent / "Mannequin Mod"
        scripts = root / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        path = scripts / "mannequins.txt"
        path.write_text(text, encoding="utf-8")
        return root, path

    def test_surgical_edit_preserves_model_reference_and_unknown_data(self):
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name))
            row = mannequin.read(root)["rows"][0]
            before = path.read_text(encoding="utf-8")
            saved = mannequin.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"female": "false", "pose": "pose03", "outfit": ""},
            )
            after = path.read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["female"], "false")
            self.assertEqual(saved["fields"]["pose"], "pose03")
            self.assertEqual(saved["fields"]["outfit"], "")
            self.assertEqual(saved["modelReference"], "FemaleBody")
            self.assertIn("model = FemaleBody,", after)
            self.assertIn("FutureField = KeepMe,", after)
            self.assertEqual(
                before.replace("female = true,", "female = false,")
                .replace("outfit = Casual,", "outfit = ,")
                .replace("pose = pose01,", "pose = pose03,"),
                after,
            )

    def test_missing_duplicate_and_stale_edits_fail_closed(self):
        missing = """module LexTest
{
    mannequin MissingPose
    {
        animSet = mannequin,
        female = true,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name), missing)
            row = mannequin.read(root)["rows"][0]
            with self.assertRaises(core.ProjectZomboidError):
                mannequin.save(root, row["path"], row["module"], row["id"], row["sha256"], {"pose": "pose01"})
            path.write_text(path.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
            with self.assertRaises(core.ProjectZomboidError):
                mannequin.save(root, row["path"], row["module"], row["id"], row["sha256"], {"female": "false"})

        duplicate = """module LexTest
{
    mannequin Duplicate
    {
        female = true,
        female = false,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), duplicate)
            row = mannequin.read(root)["rows"][0]
            self.assertEqual(row["duplicateKeys"], ["female"])
            with self.assertRaises(core.ProjectZomboidError):
                mannequin.save(root, row["path"], row["module"], row["id"], row["sha256"], {"female": "true"})

    def test_validation_uses_documented_types_and_empty_outfit_rule(self):
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name))
            row = mannequin.read(root)["rows"][0]
            invalid = [
                ("female", "yes"),
                ("animSet", ""),
                ("animState", ""),
                ("pose", ""),
                ("texture", ""),
                ("pose", "pose01,pose02"),
            ]
            for key, value in invalid:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(core.ProjectZomboidError):
                        mannequin.save(root, row["path"], row["module"], row["id"], row["sha256"], {key: value})

    def test_comments_strings_and_nested_mannequins_are_not_records(self):
        text = """module LexTest
{
    // mannequin Commented { female = true, }
    item Note
    {
        DisplayCategory = \"mannequin StringFake { female = true, }\",
        component Nested
        {
            mannequin Fake { female = true, }
        }
    }
    mannequin Real
    {
        female = true,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), text)
            result = mannequin.read(root)
            self.assertEqual(result["errors"], [])
            self.assertEqual([(row["module"], row["id"]) for row in result["rows"]], [("LexTest", "Real")])


if __name__ == "__main__":
    unittest.main()
