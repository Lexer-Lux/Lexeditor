from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server


class TerrariaLocalModStateTests(unittest.TestCase):
    def test_reads_native_enabled_json_and_local_package(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_save_root = server.TMODLOADER_SAVE_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                save_root = Path(directory)
                project = save_root / "ModSources" / "ExampleMod"
                project.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)
                server.TMODLOADER_SAVE_ROOT = save_root

                mods = save_root / "Mods"
                mods.mkdir()
                artifact = mods / "ExampleMod.tmod"
                artifact.write_bytes(b"TMOD")
                enabled = mods / "enabled.json"
                enabled.write_text(json.dumps(["OtherMod", "ExampleMod"], indent=2), encoding="utf-8")

                state = server.local_mod_state()
                self.assertEqual(Path(state["expectedArtifact"]), artifact.resolve())
                self.assertTrue(state["artifactExists"])
                self.assertTrue(state["enabledStateExists"])
                self.assertTrue(state["enabledStateValid"])
                self.assertTrue(state["enabled"])
                self.assertEqual(state["enabledStateError"], "")

                enabled.unlink()
                state = server.local_mod_state()
                self.assertFalse(state["enabledStateExists"])
                self.assertTrue(state["enabledStateValid"])
                self.assertFalse(state["enabled"])
        finally:
            server.TMODLOADER_SAVE_ROOT = previous_save_root
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project

    def test_malformed_enabled_json_is_reported_without_crashing_status(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        previous_save_root = server.TMODLOADER_SAVE_ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                save_root = Path(directory)
                project = save_root / "ModSources" / "ExampleMod"
                project.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(project)
                server.TMODLOADER_SAVE_ROOT = save_root

                mods = save_root / "Mods"
                mods.mkdir()
                enabled = mods / "enabled.json"
                enabled.write_text('{"ExampleMod": true}', encoding="utf-8")

                state = server.local_mod_state()
                self.assertTrue(state["enabledStateExists"])
                self.assertFalse(state["enabledStateValid"])
                self.assertFalse(state["enabled"])
                self.assertIn("JSON array", state["enabledStateError"])

                status = server.build_status(platform_name="posix")
                self.assertFalse(status["available"])
                self.assertFalse(status["enabledStateValid"])
                self.assertIn("Windows only", status["reason"])
        finally:
            server.TMODLOADER_SAVE_ROOT = previous_save_root
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
