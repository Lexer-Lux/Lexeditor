from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.project_zomboid import core, sound


SCRIPT = """module LexTest
{
    sound TestSound
    {
        category = Item,
        is3D = true,
        loop = false,
        master = Primary,
        maxInstancesPerEmitter = 2,
        clip
        {
            file = media/sound/test.ogg,
            distanceMin = 10,
            distanceMax = 100,
            volume = 0.75,
        }
    }
}
"""


class ProjectZomboidSoundTests(unittest.TestCase):
    def make_project(self, parent: Path, text: str = SCRIPT) -> tuple[Path, Path]:
        root = parent / "Sound Mod"
        scripts = root / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        path = scripts / "sounds.txt"
        path.write_text(text, encoding="utf-8")
        return root, path

    def test_surgical_edit_preserves_clip_block(self):
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name))
            row = sound.read(root)["rows"][0]
            before = path.read_text(encoding="utf-8")
            saved = sound.save(
                root, row["path"], row["module"], row["id"], row["sha256"],
                {"loop": "true", "maxInstancesPerEmitter": "4"},
            )
            after = path.read_text(encoding="utf-8")
            self.assertEqual(saved["fields"]["loop"], "true")
            self.assertEqual(saved["fields"]["maxInstancesPerEmitter"], "4")
            self.assertTrue(saved["hasClips"])
            self.assertIn("file = media/sound/test.ogg,", after)
            self.assertIn("distanceMax = 100,", after)
            self.assertEqual(
                before.replace("loop = false,", "loop = true,").replace(
                    "maxInstancesPerEmitter = 2,", "maxInstancesPerEmitter = 4,"),
                after,
            )

    def test_missing_duplicate_and_stale_edits_fail_closed(self):
        missing = """module LexTest
{
    sound MissingMaster
    {
        category = Item,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, path = self.make_project(Path(name), missing)
            row = sound.read(root)["rows"][0]
            with self.assertRaises(core.ProjectZomboidError):
                sound.save(root, row["path"], row["module"], row["id"], row["sha256"], {"master": "Music"})
            path.write_text(path.read_text(encoding="utf-8") + "// changed\n", encoding="utf-8")
            with self.assertRaises(core.ProjectZomboidError):
                sound.save(root, row["path"], row["module"], row["id"], row["sha256"], {"category": "Ambient"})

        duplicate = """module LexTest
{
    sound Duplicate
    {
        category = Item,
        category = Ambient,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), duplicate)
            row = sound.read(root)["rows"][0]
            self.assertEqual(row["duplicateKeys"], ["category"])
            with self.assertRaises(core.ProjectZomboidError):
                sound.save(root, row["path"], row["module"], row["id"], row["sha256"], {"category": "Music"})

    def test_validation_is_typed_and_bounded_to_documented_master_values(self):
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name))
            row = sound.read(root)["rows"][0]
            invalid = [
                ("is3D", "yes"),
                ("loop", "1"),
                ("master", "Effects"),
                ("maxInstancesPerEmitter", "1.5"),
                ("category", "Item,Ambient"),
            ]
            for key, value in invalid:
                with self.subTest(key=key, value=value):
                    with self.assertRaises(core.ProjectZomboidError):
                        sound.save(root, row["path"], row["module"], row["id"], row["sha256"], {key: value})

    def test_nested_commented_and_string_sound_text_do_not_create_records(self):
        text = """module LexTest
{
    // sound Commented { category = Item, }
    item Container
    {
        DisplayCategory = \"sound StringFake { category = Item, }\",
        component Nested
        {
            sound Fake { category = Item, }
        }
    }
    sound Real
    {
        category = Item,
        is3D = true,
        loop = false,
        master = Primary,
        maxInstancesPerEmitter = 1,
    }
}
"""
        with tempfile.TemporaryDirectory() as name:
            root, _path = self.make_project(Path(name), text)
            result = sound.read(root)
            self.assertEqual(result["errors"], [])
            self.assertEqual([(row["module"], row["id"]) for row in result["rows"]], [("LexTest", "Real")])


if __name__ == "__main__":
    unittest.main()
