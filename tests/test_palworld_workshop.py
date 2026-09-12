from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld import build as package_build
from games.palworld.workshop import (
    PackageNameCollisionError,
    WorkshopChangedError,
    WorkshopOwnershipError,
    WorkshopUnavailableError,
    deploy,
    remove,
    status,
    workshop_root,
)


class PalworldWorkshopDeploymentTests(unittest.TestCase):
    def make_game(self, root: Path) -> tuple[Path, Path]:
        game = root / "SteamLibrary" / "steamapps" / "common" / "Palworld"
        game.mkdir(parents=True)
        workshop = root / "SteamLibrary" / "steamapps" / "workshop" / "content" / "1623730"
        workshop.mkdir(parents=True)
        return game, workshop

    def make_project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir()
        payload = project / "PalSchema" / "Balance" / "raw"
        payload.mkdir(parents=True)
        (payload / "balance.json").write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
        info = {
            "ModName": "Local Test",
            "PackageName": "LocalTestPackage",
            "Version": "1",
            "DebugMode": True,
            "Author": "Lexer",
            "Dependencies": ["PalSchema"],
            "Tags": ["PalSchema"],
            "InstallRule": [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}],
        }
        (project / "Info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        package_build.build(project)
        return project

    def test_standard_steam_root_inference(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, workshop = self.make_game(root)
            self.assertEqual(workshop.resolve(), workshop_root(game))

    def test_local_deploy_uses_new_ten_digit_owned_folder_and_reverts(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, workshop = self.make_game(root)
            project = self.make_project(root)
            deployed = deploy(project, game_root=game)
            self.assertTrue(deployed["deployed"])
            self.assertTrue(deployed["owned"])
            self.assertTrue(deployed["current"])
            self.assertEqual(10, len(deployed["folder"]))
            self.assertTrue(deployed["folder"].isdigit())
            target = Path(deployed["targetPath"])
            self.assertEqual(workshop.resolve(), target.parent.resolve())
            self.assertTrue((target / "Info.json").is_file())
            self.assertTrue((target / "PalSchema" / "Balance" / "raw" / "balance.json").is_file())
            self.assertFalse((target / ".workshop.json").exists())

            removed = remove(project, game_root=game)
            self.assertFalse(removed["deployed"])
            self.assertFalse(removed["owned"])
            self.assertFalse(target.exists())

    def test_redeploy_updates_same_owned_folder_after_clean_rebuild(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop = self.make_game(root)
            project = self.make_project(root)
            first = deploy(project, game_root=game)
            first_target = Path(first["targetPath"])
            source = project / "PalSchema" / "Balance" / "raw" / "balance.json"
            source.write_text('{"DT_Test":{"Row":{"Value":2}}}\n', encoding="utf-8")
            package_build.build(project)
            stale = status(project, game_root=game)
            self.assertFalse(stale["current"])
            second = deploy(project, game_root=game)
            self.assertEqual(first["folder"], second["folder"])
            self.assertEqual(first_target, Path(second["targetPath"]))
            self.assertTrue(second["current"])
            self.assertIn('"Value":2', (first_target / "PalSchema" / "Balance" / "raw" / "balance.json").read_text("utf-8").replace(" ", ""))

    def test_duplicate_package_name_in_other_workshop_folder_blocks_deploy(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, workshop = self.make_game(root)
            project = self.make_project(root)
            subscribed = workshop / "1234567890"
            subscribed.mkdir()
            (subscribed / "Info.json").write_text(json.dumps({"PackageName": "LocalTestPackage"}), encoding="utf-8")
            with self.assertRaises(PackageNameCollisionError):
                deploy(project, game_root=game)
            self.assertTrue(subscribed.is_dir())
            self.assertFalse((project / "build" / ".lexeditor-palworld-local-workshop.json").exists())

    def test_external_local_deployment_change_blocks_update_and_removal(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop = self.make_game(root)
            project = self.make_project(root)
            deployed = deploy(project, game_root=game)
            target = Path(deployed["targetPath"])
            (target / "external.txt").write_text("do not delete", encoding="utf-8")
            with self.assertRaises(WorkshopChangedError):
                deploy(project, game_root=game)
            with self.assertRaises(WorkshopChangedError):
                remove(project, game_root=game)
            self.assertEqual("do not delete", (target / "external.txt").read_text("utf-8"))

    def test_missing_owned_folder_is_not_silently_recreated(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop = self.make_game(root)
            project = self.make_project(root)
            deployed = deploy(project, game_root=game)
            target = Path(deployed["targetPath"])
            for path in sorted(target.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            target.rmdir()
            with self.assertRaises(WorkshopOwnershipError):
                deploy(project, game_root=game)
            with self.assertRaises(WorkshopOwnershipError):
                remove(project, game_root=game)

    def test_deploy_requires_current_clean_build(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop = self.make_game(root)
            project = self.make_project(root)
            (project / "PalSchema" / "Balance" / "raw" / "balance.json").write_text('{"DT_Test":{"Row":{"Value":5}}}\n', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                deploy(project, game_root=game)

    def test_unavailable_nonsteam_root_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game = root / "Palworld"
            game.mkdir()
            project = self.make_project(root)
            self.assertIsNone(workshop_root(game))
            with self.assertRaises(WorkshopUnavailableError):
                deploy(project, game_root=game)


if __name__ == "__main__":
    unittest.main()
