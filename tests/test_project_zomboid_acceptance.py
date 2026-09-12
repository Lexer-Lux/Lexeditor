from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.project_zomboid import acceptance, core
from games.project_zomboid.plugin import PLUGIN


class ProjectZomboidAcceptanceTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[Path, Path, Path]:
        game = root / "ProjectZomboid"
        (game / "media" / "scripts" / "generated").mkdir(parents=True)
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

    def test_install_descriptor_and_preflight_share_build42_sentinel(self):
        self.assertIsNotNone(PLUGIN.installation)
        self.assertIn("media/scripts/generated", PLUGIN.installation.required_paths)

    def test_real_install_preflight_is_ready_for_manual_game_test(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))

            report = acceptance.inspect(game, project, user)

            self.assertTrue(report["preflightReady"])
            self.assertEqual(report["modName"], "Lexeditor Test")
            self.assertEqual(report["modId"], "LexeditorAcceptance")
            self.assertEqual(report["scriptInventory"]["recordCount"], 1)
            self.assertEqual(report["scriptInventory"]["counts"]["item"], 1)
            self.assertFalse(report["activationEvidence"]["enabledAnywhere"])
            self.assertIn("not that Project Zomboid loaded", report["acceptanceBoundary"])
            self.assertEqual(len(report["manualGameTest"]), 5)

    def test_build41_shape_without_generated_scripts_fails_build42_check(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            (game / "media" / "scripts" / "generated").rmdir()

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["build42-generated-scripts"]["ok"])
            self.assertTrue(checks["game-executable"]["ok"])
            self.assertTrue(checks["game-scripts"]["ok"])

    def test_activation_evidence_reads_default_and_save_mod_lists(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            (user / "mods" / "default.txt").write_text(
                "VERSION = 1,\n"
                "mods\n"
                "{\n"
                "mod = OtherMod,\n"
                "mod = LexeditorAcceptance,\n"
                "}\n"
                "maps\n"
                "{\n"
                "}\n",
                encoding="utf-8",
            )
            save = user / "Saves" / "Sandbox" / "AcceptanceWorld"
            save.mkdir(parents=True)
            (save / "mods.txt").write_text(
                "VERSION = 1,\n"
                "mods\n"
                "{\n"
                "mod = LexeditorAcceptance,\n"
                "}\n"
                "maps\n"
                "{\n"
                "}\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            evidence = report["activationEvidence"]

            self.assertTrue(report["preflightReady"])
            self.assertTrue(evidence["enabledAnywhere"])
            self.assertTrue(evidence["defaultList"]["enabled"])
            self.assertEqual(
                evidence["defaultList"]["modIds"],
                ["OtherMod", "LexeditorAcceptance"],
            )
            self.assertEqual(evidence["saveListsScanned"], 1)
            self.assertEqual(len(evidence["matchingSaves"]), 1)
            self.assertEqual(
                evidence["matchingSaves"][0]["path"],
                "Saves/Sandbox/AcceptanceWorld/mods.txt",
            )
            self.assertFalse(evidence["parseErrors"])
            self.assertIn("evidence only", evidence["boundary"])

    def test_malformed_activation_list_is_reported_but_not_a_preflight_failure(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            (user / "mods" / "default.txt").write_text(
                "VERSION = 1,\nnot_the_mods_block { }\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            evidence = report["activationEvidence"]

            self.assertTrue(report["preflightReady"])
            self.assertFalse(evidence["enabledAnywhere"])
            self.assertEqual(len(evidence["parseErrors"]), 1)
            self.assertIn("No mods", evidence["parseErrors"][0]["error"])

    def test_cli_emits_json_and_uses_exit_status_for_preflight_readiness(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            args = [
                "--game-root", str(game),
                "--project-root", str(project),
                "--user-root", str(user),
            ]

            output = io.StringIO()
            with redirect_stdout(output):
                result = acceptance.main(args)
            payload = json.loads(output.getvalue())
            self.assertEqual(result, 0)
            self.assertTrue(payload["preflightReady"])

            (game / "ProjectZomboid64.exe").unlink()
            output = io.StringIO()
            with redirect_stdout(output):
                result = acceptance.main(args)
            payload = json.loads(output.getvalue())
            self.assertEqual(result, 1)
            self.assertFalse(payload["preflightReady"])

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
            target = Path(core.deployment_state(project, user_root=user)["target"])
            (target / "42" / "media" / "scripts" / "items.txt").write_text(
                "// changed outside Lexeditor\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["owned-deployment"]["ok"])
            self.assertTrue(checks["deployment-target"]["ok"])

    def test_wrong_user_root_fails_target_and_ownership_checks(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))

            report = acceptance.inspect(game, project, user / "OtherProfile")
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["deployment-target"]["ok"])
            self.assertFalse(checks["owned-deployment"]["ok"])
            self.assertFalse(checks["deployed-mod-info"]["ok"])
            self.assertFalse(checks["deployed-script-parse"]["ok"])

    def test_tampered_external_deployment_target_is_not_read(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            game, project, user = self.make_fixture(base)
            fake = base / "LooksLikeAValidModButIsOutsideUserRoot"
            scripts = fake / "42" / "media" / "scripts"
            scripts.mkdir(parents=True)
            (fake / "42" / "mod.info").write_text(
                "name=Lexeditor Test\nid=LexeditorAcceptance\n",
                encoding="utf-8",
            )
            (scripts / "items.txt").write_text(
                "module LexAcceptance { item Fake { Weight = 9.0, } }\n",
                encoding="utf-8",
            )
            state_path = project / ".lexeditor" / "project-zomboid-deployment.json"
            state_path.write_text(
                json.dumps({
                    "schema": 1,
                    "target": str(fake.resolve()),
                    "files": {
                        "42/mod.info": core.sha256_file(fake / "42" / "mod.info"),
                        "42/media/scripts/items.txt": core.sha256_file(scripts / "items.txt"),
                    },
                }),
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertEqual(report["deploymentTarget"], "")
            self.assertFalse(checks["owned-deployment"]["ok"])
            self.assertFalse(checks["deployment-target"]["ok"])
            self.assertFalse(checks["deployed-mod-info"]["ok"])
            self.assertFalse(checks["mod-identity-match"]["ok"])
            self.assertFalse(checks["deployed-script-parse"]["ok"])
            self.assertEqual(report["scriptInventory"]["recordCount"], 0)

    def test_malformed_deployed_script_fails_parse_check(self):
        with tempfile.TemporaryDirectory() as name:
            game, project, user = self.make_fixture(Path(name))
            target = Path(core.deployment_state(project, user_root=user)["target"])
            script = target / "42" / "media" / "scripts" / "items.txt"
            script.write_text(
                "module Broken\n{\n item Widget\n {\n  Weight = 1.0,\n",
                encoding="utf-8",
            )

            report = acceptance.inspect(game, project, user)
            checks = {row["id"]: row for row in report["checks"]}

            self.assertFalse(report["preflightReady"])
            self.assertFalse(checks["owned-deployment"]["ok"])
            self.assertTrue(checks["deployment-target"]["ok"])
            self.assertFalse(checks["deployed-script-parse"]["ok"])
            self.assertTrue(report["scriptInventory"]["errors"])


if __name__ == "__main__":
    unittest.main()
