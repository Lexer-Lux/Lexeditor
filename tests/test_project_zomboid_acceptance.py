from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.project_zomboid import acceptance, core


class ProjectZomboidAcceptanceTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        game = root / "ProjectZomboid"
        (game / "media" / "scripts").mkdir(parents=True)
        (game / "ProjectZomboid64.exe").write_bytes(b"MZ")

        project = root / "Lexeditor Test Mod"
        (project / "common" / "media").mkdir(parents=True)
        scripts = project / "42" / "media" / "scripts"
        scripts.mkdir(parents=True)
        (project / "42" / "mod.info").write_text(
            "name=Lexeditor Test\nid=LexeditorAcceptance\n",
            encoding="utf-8",
        )
        (scripts / "items.txt").write_text(
            "module LexAcceptance\n"
            "{\n"
            " item Widget\n"
            " {\n"
            "  ItemType = base:normal,\n"
            "  Weight = 1.0,\n"
            " }\n"
            "}\n",
            encoding="utf-8",
        )

        user = root / "Zomboid"
        with patch.dict(
            os.environ,
            {"LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT": str(user)},
        ):
            deployed = core.deploy(project)
        self.assertTrue(deployed["owned"])
        return game, project, user

    def test_real_install_preflight_is_ready_for_manual_game_test(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))

            report = acceptance.inspect(game, project, user)

            self.assertTrue(report["preflightReady"])
            self.assertEqual(report["modName"], "Lexeditor Test")
            self.assertEqual(report["modId"], "LexeditorAcceptance")
            self.assertEqual(report["scriptInventory"]["recordCount"], 1)
            self.assertEqual(report["scriptInventory"]["counts"]["item"], 1)
            self.assertIn("does not", report["acceptanceBoundary"])
            self.assertEqual(len(report["manualGameTest"]), 5)

    def test_missing_game_executable_fails_without_faking_deployment_failure(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            (game / "ProjectZomboid64.exe").unlink()

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["game-executable"]["ok"])
            self.assertTrue(checks["owned-deployment"]["ok"])
            self.assertTrue(checks["mod-identity-match"]["ok"])
            self.assertTrue(checks["deployed-script-parse"]["ok"])

    def test_external_deployment_change_fails_owned_check(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            target = Path(core.deployment_state(project)["target"])
            (target / "42" / "media" / "scripts" / "items.txt").write_text(
                "// changed outside Lexeditor\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["owned-deployment"]["ok"])

    def test_wrong_user_root_fails_target_check(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))

            report = acceptance.inspect(game, project, user / "OtherProfile")
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["deployment-target"]["ok"])
            self.assertTrue(checks["owned-deployment"]["ok"])

    def test_malformed_deployed_script_fails_parse_check(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            target = Path(core.deployment_state(project)["target"])
            script = target / "42" / "media" / "scripts" / "items.txt"
            script.write_text(
                "module Broken\n{\n item Widget\n {\n  Weight = 1.0,\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["owned-deployment"]["ok"])
            self.assertFalse(checks["deployed-script-parse"]["ok"])
            self.assertTrue(report["scriptInventory"]["errors"])


if __name__ == "__main__":
    unittest.main()
