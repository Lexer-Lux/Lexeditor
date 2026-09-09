from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from games.palworld import build as package_build
from games.palworld.workshop import (
    WorkshopChangedError,
    WorkshopOwnershipError,
    deploy,
    remove,
    status,
)


class PalworldWorkshopSafetyTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        game = root / "SteamLibrary" / "steamapps" / "common" / "Palworld"
        game.mkdir(parents=True)
        workshop = root / "SteamLibrary" / "steamapps" / "workshop" / "content" / "1623730"
        workshop.mkdir(parents=True)
        project = root / "project"
        project.mkdir()
        payload = project / "PalSchema" / "Balance" / "raw"
        payload.mkdir(parents=True)
        (payload / "balance.json").write_text('{"DT_Test":{"Row":{"Value":1}}}\n', encoding="utf-8")
        (project / "Info.json").write_text(json.dumps({
            "ModName": "Safety Fixture",
            "PackageName": "SafetyFixture",
            "Version": "1",
            "DebugMode": True,
            "Author": "Lexer",
            "Dependencies": ["PalSchema"],
            "Tags": ["PalSchema"],
            "InstallRule": [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}],
        }, indent=2) + "\n", encoding="utf-8")
        package_build.build(project)
        return game, workshop, project

    def test_owned_folder_symlink_is_never_followed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop, project = self.fixture(root)
            deployed = deploy(project, game_root=game)
            target = Path(deployed["targetPath"])
            outside = root / "outside"
            outside.mkdir()
            marker = outside / "keep.txt"
            marker.write_text("do not touch", encoding="utf-8")
            shutil.rmtree(target)
            try:
                os.symlink(outside, target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable on this runner")

            state = status(project, game_root=game)
            self.assertTrue(state["owned"])
            self.assertTrue(state["linkedTarget"])
            self.assertTrue(state["externallyChanged"])
            with self.assertRaises(WorkshopChangedError):
                deploy(project, game_root=game)
            with self.assertRaises(WorkshopChangedError):
                remove(project, game_root=game)
            self.assertEqual("do not touch", marker.read_text("utf-8"))
            self.assertTrue(target.is_symlink())

    def test_tampered_manifest_root_is_not_trusted_for_removal_or_update(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop, project = self.fixture(root)
            deployed = deploy(project, game_root=game)
            original_target = Path(deployed["targetPath"])
            manifest_path = project / "build" / ".lexeditor-palworld-local-workshop.json"
            manifest = json.loads(manifest_path.read_text("utf-8"))
            attacker_root = root / "unrelated-root"
            attacker_root.mkdir()
            attacker_target = attacker_root / manifest["folder"]
            attacker_target.mkdir()
            attacker_marker = attacker_target / "keep.txt"
            attacker_marker.write_text("do not touch", encoding="utf-8")
            manifest["workshopRoot"] = str(attacker_root)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            state = status(project, game_root=game)
            self.assertTrue(state["rootMismatch"])
            self.assertFalse(state["deployed"])
            with self.assertRaises(WorkshopOwnershipError):
                deploy(project, game_root=game)
            with self.assertRaises(WorkshopOwnershipError):
                remove(project, game_root=game)
            self.assertTrue(original_target.is_dir())
            self.assertEqual("do not touch", attacker_marker.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
