from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.palworld import build as package_build
from games.palworld.workshop import LoaderRefreshError, WorkshopOwnershipError, deploy


class PalworldWorkshopLoaderSemanticsTests(unittest.TestCase):
    def fixture(self, root: Path, *, debug_mode: bool = False) -> tuple[Path, Path, Path]:
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
            "ModName": "Loader Semantics",
            "PackageName": "LoaderSemantics",
            "Version": "1",
            "DebugMode": debug_mode,
            "Author": "Lexer",
            "Dependencies": ["PalSchema"],
            "Tags": ["PalSchema"],
            "InstallRule": [{"Type": "PalSchema", "Targets": ["./PalSchema/"]}],
        }, indent=2) + "\n", encoding="utf-8")
        package_build.build(project)
        return game, workshop, project

    def test_changed_local_package_requires_version_change_when_debug_is_off(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop, project = self.fixture(root, debug_mode=False)
            first = deploy(project, game_root=game)
            target = Path(first["targetPath"])
            before = (target / "PalSchema" / "Balance" / "raw" / "balance.json").read_bytes()

            source = project / "PalSchema" / "Balance" / "raw" / "balance.json"
            source.write_text('{"DT_Test":{"Row":{"Value":2}}}\n', encoding="utf-8")
            package_build.build(project)
            with self.assertRaises(LoaderRefreshError):
                deploy(project, game_root=game)
            self.assertEqual(before, (target / "PalSchema" / "Balance" / "raw" / "balance.json").read_bytes())

            info_path = project / "Info.json"
            info = json.loads(info_path.read_text("utf-8"))
            info["Version"] = "2"
            info_path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
            package_build.build(project)
            updated = deploy(project, game_root=game)
            self.assertTrue(updated["current"])
            self.assertEqual("2", updated["deployedVersion"])
            self.assertIn('"Value":2', (target / "PalSchema" / "Balance" / "raw" / "balance.json").read_text("utf-8").replace(" ", ""))

    def test_debug_mode_allows_same_version_local_refresh(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop, project = self.fixture(root, debug_mode=True)
            first = deploy(project, game_root=game)
            source = project / "PalSchema" / "Balance" / "raw" / "balance.json"
            source.write_text('{"DT_Test":{"Row":{"Value":3}}}\n', encoding="utf-8")
            package_build.build(project)
            updated = deploy(project, game_root=game)
            self.assertEqual(first["folder"], updated["folder"])
            self.assertTrue(updated["current"])
            self.assertTrue(updated["deployedDebugMode"])

    def test_package_name_change_requires_new_local_identity(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            game, _workshop, project = self.fixture(root, debug_mode=True)
            deployed = deploy(project, game_root=game)
            target = Path(deployed["targetPath"])
            info_path = project / "Info.json"
            info = json.loads(info_path.read_text("utf-8"))
            info["PackageName"] = "DifferentIdentity"
            info_path.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
            package_build.build(project)
            with self.assertRaises(WorkshopOwnershipError):
                deploy(project, game_root=game)
            self.assertTrue(target.is_dir())
            self.assertEqual("LoaderSemantics", json.loads((target / "Info.json").read_text("utf-8"))["PackageName"])


if __name__ == "__main__":
    unittest.main()
