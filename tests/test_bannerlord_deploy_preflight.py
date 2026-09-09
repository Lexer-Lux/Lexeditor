from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.deploy_data import sync_project_assets


def write_project(root: Path) -> Path:
    project = root / "project"
    (project / "GUI").mkdir(parents=True)
    (project / "SubModule.xml").write_text(
        '<Module><Name value="Safe Module"/><Id value="SafeModule"/></Module>',
        encoding="utf-8",
    )
    return project


def write_game(root: Path) -> Path:
    game = root / "game"
    executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    (game / "Modules").mkdir()
    return game


def write_existing_module(game: Path) -> Path:
    target = game / "Modules" / "SafeModule"
    target.mkdir()
    (target / "SubModule.xml").write_text(
        '<Module><Name value="Safe Module"/><Id value="SafeModule"/></Module>',
        encoding="utf-8",
    )
    return target


class BannerlordDeployPreflightTests(unittest.TestCase):
    def test_later_destination_collision_cannot_partially_overwrite_earlier_asset(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = write_project(root)
            game = write_game(root)
            target = write_existing_module(game)

            (project / "GUI" / "a.txt").write_text("new-a", encoding="utf-8")
            (project / "GUI" / "z.txt").write_text("new-z", encoding="utf-8")
            (target / "GUI").mkdir()
            destination_a = target / "GUI" / "a.txt"
            destination_a.write_text("old-a", encoding="utf-8")
            (target / "GUI" / "z.txt").mkdir()

            with self.assertRaisesRegex(ValueError, "destination is not a file"):
                sync_project_assets(project, game)

            self.assertEqual(destination_a.read_text(encoding="utf-8"), "old-a")
            self.assertFalse(destination_a.with_name("a.txt.lexeditor.bak").exists())
            self.assertFalse(destination_a.with_name("a.txt.lexeditor.tmp").exists())

    def test_later_helper_directory_cannot_partially_overwrite_earlier_asset(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = write_project(root)
            game = write_game(root)
            target = write_existing_module(game)

            (project / "GUI" / "a.txt").write_text("new-a", encoding="utf-8")
            (project / "GUI" / "z.txt").write_text("new-z", encoding="utf-8")
            (target / "GUI").mkdir()
            destination_a = target / "GUI" / "a.txt"
            destination_z = target / "GUI" / "z.txt"
            destination_a.write_text("old-a", encoding="utf-8")
            destination_z.write_text("old-z", encoding="utf-8")
            destination_z.with_name("z.txt.lexeditor.bak").mkdir()

            with self.assertRaisesRegex(ValueError, "write helper path is a directory"):
                sync_project_assets(project, game)

            self.assertEqual(destination_a.read_text(encoding="utf-8"), "old-a")
            self.assertEqual(destination_z.read_text(encoding="utf-8"), "old-z")
            self.assertFalse(destination_a.with_name("a.txt.lexeditor.bak").exists())
            self.assertFalse(destination_a.with_name("a.txt.lexeditor.tmp").exists())

    def test_source_escape_is_rejected_before_new_module_folder_is_created(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = write_project(root)
            game = write_game(root)
            source = project / "GUI" / "a.txt"
            source.write_text("new-a", encoding="utf-8")
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")

            real_resolve = Path.resolve
            project_resolved = real_resolve(project)
            source_logical = project_resolved / "GUI" / "a.txt"
            outside_resolved = real_resolve(outside)

            def fake_resolve(path, *args, **kwargs):
                if Path(path) == source_logical:
                    return outside_resolved
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=fake_resolve):
                with self.assertRaisesRegex(ValueError, "source escaped project root"):
                    sync_project_assets(project, game)

            self.assertFalse((game / "Modules" / "SafeModule").exists())
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside")


if __name__ == "__main__":
    unittest.main()
