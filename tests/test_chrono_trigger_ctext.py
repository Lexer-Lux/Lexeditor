from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from games.chrono_trigger.ctext_manager import (
    CONFIG_BACKUP,
    DEPLOY_MANIFEST,
    deactivate_project,
    deploy_project,
    status,
    undeploy_project,
)


def _ctext_install(root: Path, config: dict | None = None) -> Path:
    game = root / "game"
    game.mkdir()
    (game / "ctext.dll").write_bytes(b"fixture")
    (game / "sqlite3.dll").write_bytes(b"fixture")
    payload = config if config is not None else {
        "mods": {"enabled": False, "load_order": ["ExistingMod"]},
        "other": {"preserved": True},
    }
    (game / "ctext.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return game


def _project(root: Path, name: str = "MyChronoMod") -> Path:
    project = root / name
    (project / "Game/field").mkdir(parents=True)
    (project / "Localize/en/msg").mkdir(parents=True)
    (project / "Game/field/example.dat").write_bytes(b"one")
    (project / "Localize/en/msg/item.txt").write_text("0000,Tonic\n", encoding="utf-8")
    return project


class CTExtDeploymentTests(unittest.TestCase):
    def test_status_requires_documented_config_shape(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root, {"mods": {"enabled": True, "load_order": "wrong"}})
            info = status(game, _project(root))
            self.assertTrue(info["installed"])
            self.assertFalse(info["configValid"])
            self.assertIn("load_order", info["configError"])

    def test_deploy_mirrors_project_backs_up_config_and_activates_mod(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            result = deploy_project(game, project)
            destination = game / "mods" / project.name
            self.assertTrue(result["deployed"])
            self.assertTrue(result["active"])
            self.assertEqual(result["copiedFiles"], 2)
            self.assertEqual((destination / "Game/field/example.dat").read_bytes(), b"one")
            self.assertEqual((destination / "Localize/en/msg/item.txt").read_text(encoding="utf-8"), "0000,Tonic\n")
            self.assertTrue((destination / DEPLOY_MANIFEST).is_file())
            self.assertTrue((game / CONFIG_BACKUP).is_file())
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertTrue(config["mods"]["enabled"])
            self.assertEqual(config["mods"]["load_order"], ["ExistingMod", project.name])
            self.assertEqual(config["other"], {"preserved": True})

    def test_redeploy_removes_only_previous_lexeditor_owned_files(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            deploy_project(game, project)
            destination = game / "mods" / project.name
            unrelated = destination / "manual-note.txt"
            unrelated.write_text("keep", encoding="utf-8")
            (project / "Game/field/example.dat").unlink()
            (project / "Game/field/new.dat").write_bytes(b"two")
            second = deploy_project(game, project)
            self.assertFalse((destination / "Game/field/example.dat").exists())
            self.assertEqual((destination / "Game/field/new.dat").read_bytes(), b"two")
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")
            self.assertTrue(second["active"])

    def test_refuses_to_overwrite_non_lexeditor_mod_folder(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            collision = game / "mods" / project.name
            collision.mkdir(parents=True)
            (collision / "someone-elses-file.dat").write_bytes(b"leave me")
            with self.assertRaises(RuntimeError):
                deploy_project(game, project)
            self.assertEqual((collision / "someone-elses-file.dat").read_bytes(), b"leave me")

    def test_refuses_deploy_without_runtime_or_valid_config(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            (game / "ctext.dll").unlink()
            with self.assertRaises(RuntimeError):
                deploy_project(game, project)

    def test_project_already_inside_mods_only_updates_load_order(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(game / "mods", "DirectMod")
            result = deploy_project(game, project)
            self.assertEqual(result["copiedFiles"], 0)
            self.assertTrue(result["active"])
            self.assertTrue(result["directProject"])
            self.assertFalse((project / DEPLOY_MANIFEST).exists())
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertIn("DirectMod", config["mods"]["load_order"])

    def test_deactivate_only_removes_selected_project_from_load_order(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            deploy_project(game, project)
            destination = game / "mods" / project.name
            result = deactivate_project(game, project)
            self.assertFalse(result["active"])
            self.assertTrue(result["deployed"])
            self.assertTrue((destination / "Game/field/example.dat").is_file())
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertTrue(config["mods"]["enabled"])
            self.assertEqual(config["mods"]["load_order"], ["ExistingMod"])

    def test_undeploy_removes_manifest_files_but_preserves_manual_files(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            deploy_project(game, project)
            destination = game / "mods" / project.name
            manual = destination / "manual-note.txt"
            manual.write_text("keep", encoding="utf-8")
            result = undeploy_project(game, project)
            self.assertFalse(result["active"])
            self.assertEqual(result["removedFiles"], 2)
            self.assertFalse((destination / DEPLOY_MANIFEST).exists())
            self.assertFalse((destination / "Game/field/example.dat").exists())
            self.assertEqual(manual.read_text(encoding="utf-8"), "keep")
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertEqual(config["mods"]["load_order"], ["ExistingMod"])

    def test_undeploy_direct_mod_project_never_deletes_source(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(game / "mods", "DirectMod")
            deploy_project(game, project)
            result = undeploy_project(game, project)
            self.assertFalse(result["active"])
            self.assertTrue(result["directProjectPreserved"])
            self.assertTrue((project / "Game/field/example.dat").is_file())
            self.assertTrue((project / "Localize/en/msg/item.txt").is_file())

    def test_wrong_owner_manifest_blocks_undeploy_before_config_change(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-ctext-") as temp_name:
            root = Path(temp_name)
            game = _ctext_install(root)
            project = _project(root)
            destination = game / "mods" / project.name
            destination.mkdir(parents=True)
            (destination / DEPLOY_MANIFEST).write_text(json.dumps({
                "format": 1,
                "source": str(root / "DifferentProject"),
                "files": ["owned.dat"],
            }), encoding="utf-8")
            config = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            config["mods"]["enabled"] = True
            config["mods"]["load_order"].append(project.name)
            (game / "ctext.json").write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                undeploy_project(game, project)
            after = json.loads((game / "ctext.json").read_text(encoding="utf-8"))
            self.assertIn(project.name, after["mods"]["load_order"])


if __name__ == "__main__":
    unittest.main()
