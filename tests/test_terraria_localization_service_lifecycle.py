from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server


class TerrariaLocalizationServiceLifecycleTests(unittest.TestCase):
    def test_service_deletes_supported_leaf_under_stale_guard(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                localization = root / "Localization"
                localization.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                target = localization / "en-US.hjson"
                target.write_text(
                    "Mods: {\n"
                    "  ExampleMod: {\n"
                    "    Keep: Keep me\n"
                    "    Remove: Delete me\n"
                    "  }\n"
                    "}\n",
                    encoding="utf-8",
                )

                state = server.localization_file_state("Localization/en-US.hjson")
                result = server.save_localization(
                    state["path"],
                    {},
                    state["sha256"],
                    {},
                    ["Mods.ExampleMod.Remove"],
                )
                keys = {entry["key"] for entry in result["entries"]}
                self.assertIn("Mods.ExampleMod.Keep", keys)
                self.assertNotIn("Mods.ExampleMod.Remove", keys)
                self.assertNotIn("Remove:", target.read_text(encoding="utf-8"))

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_localization(
                        state["path"],
                        {},
                        state["sha256"],
                        {},
                        ["Mods.ExampleMod.Keep"],
                    )
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project

    def test_direct_localization_api_paths_reject_hidden_generated_trees(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                (root / "obj").mkdir(parents=True)
                (root / ".hidden").mkdir()
                (root / "obj" / "en-US.hjson").write_text("Key: Value\n", encoding="utf-8")
                (root / ".hidden" / "en-US.hjson").write_text("Key: Value\n", encoding="utf-8")
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)

                with self.assertRaisesRegex(ValueError, "ignored/generated"):
                    server.localization_file_state("obj/en-US.hjson")
                with self.assertRaisesRegex(ValueError, "ignored/generated"):
                    server.localization_file_state(".hidden/en-US.hjson")
                self.assertEqual(server.localization_index()["files"], [])
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
