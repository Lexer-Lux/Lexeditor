from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.project_zomboid import core


class ProjectZomboidDeploymentTests(unittest.TestCase):
    def make_project(self, base: Path) -> Path:
        root = base / "AuthoringMod"
        scripts = root / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (root / "42" / "mod.info").write_text("name=Authoring Mod\nid=AuthoringMod\n", encoding="utf-8")
        (scripts / "item.txt").write_text("module Test { item A { ItemType = base:normal, Weight = 1, } }\n", encoding="utf-8")
        return root

    def test_unowned_existing_folder_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = self.make_project(base)
            user = base / "Zomboid"
            target = user / "mods" / root.name
            target.mkdir(parents=True)
            marker = target / "foreign.txt"
            marker.write_text("mine", encoding="utf-8")
            with patch.dict(os.environ, {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user)}):
                with self.assertRaisesRegex(core.ProjectZomboidError, "unowned or changed externally"):
                    core.deploy(root)
            self.assertEqual(marker.read_text(encoding="utf-8"), "mine")

    def test_owned_deployment_can_redeploy_and_cleanly_remove(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = self.make_project(base)
            user = base / "Zomboid"
            with patch.dict(os.environ, {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user)}):
                first = core.deploy(root)
                self.assertTrue(first["owned"])
                source = root / "42" / "media" / "scripts" / "item.txt"
                source.write_text(source.read_text(encoding="utf-8").replace("Weight = 1", "Weight = 2"), encoding="utf-8")
                second = core.deploy(root)
                self.assertTrue(second["owned"])
                target = Path(second["target"])
                self.assertIn("Weight = 2", (target / "42" / "media" / "scripts" / "item.txt").read_text(encoding="utf-8"))
                removed = core.undeploy(root)
                self.assertFalse(removed["deployed"])
                self.assertFalse(target.exists())

    def test_added_external_file_blocks_redeploy_and_removal(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = self.make_project(base)
            user = base / "Zomboid"
            with patch.dict(os.environ, {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user)}):
                state = core.deploy(root)
                target = Path(state["target"])
                (target / "external-addon.txt").write_text("do not delete", encoding="utf-8")
                observed = core.deployment_state(root)
                self.assertTrue(observed["externalChanges"])
                self.assertFalse(observed["owned"])
                with self.assertRaisesRegex(core.ProjectZomboidError, "changed externally"):
                    core.undeploy(root)
                self.assertTrue((target / "external-addon.txt").is_file())

    def test_project_symlink_is_refused_when_supported(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            root = self.make_project(base)
            external = base / "outside.txt"
            external.write_text("outside", encoding="utf-8")
            link = root / "42" / "media" / "linked.txt"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable on this runner")
            user = base / "Zomboid"
            with patch.dict(os.environ, {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user)}):
                with self.assertRaisesRegex(core.ProjectZomboidError, "refuses links"):
                    core.deploy(root)


if __name__ == "__main__":
    unittest.main()
