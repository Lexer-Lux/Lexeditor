from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server


class TerrariaStructuredContentServiceTests(unittest.TestCase):
    def test_selected_project_create_catalog_open_save_and_stale_guard(self):
        previous = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                root.mkdir()
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                created = server.create_structured_content_file(
                    "npc", "CaveBug", {"lifeMax": 300, "damage": 21}, "Cave Bug", ""
                )
                self.assertEqual(created["kind"], "npc")
                self.assertEqual(created["path"], "Content/NPCs/CaveBug.cs")
                catalog = server.structured_content_catalog()
                self.assertEqual(catalog["files"][0]["path"], created["path"])
                self.assertIn("npc", {schema["kind"] for schema in catalog["schemas"]})
                opened = server.structured_content_file(created["path"])
                values = dict(opened["values"])
                values["lifeMax"] = 999
                saved = server.save_structured_content_file(opened["path"], values, opened["sha256"])
                self.assertEqual(saved["values"]["lifeMax"], 999)
                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_structured_content_file(opened["path"], values, opened["sha256"])
        finally:
            if previous is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous

    def test_invalid_kind_and_path_fail_closed(self):
        previous = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                root.mkdir()
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                with self.assertRaisesRegex(ValueError, "Unsupported structured content kind"):
                    server.create_structured_content_file("bossWizard", "Thing", {}, "", "")
                with self.assertRaisesRegex(ValueError, "Invalid C# source path"):
                    server.structured_content_file("../Outside.cs")
        finally:
            if previous is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous


if __name__ == "__main__":
    unittest.main()
