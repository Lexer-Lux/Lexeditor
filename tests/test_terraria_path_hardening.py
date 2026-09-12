from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria import server
from games.terraria.source_text import source_file_state


class TerrariaPathHardeningTests(unittest.TestCase):
    def test_direct_source_access_rejects_hidden_and_generated_trees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in (".git", ".private", "obj", "bin", ".vs"):
                target = root / folder / "Hidden.cs"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("class Hidden {}\n", encoding="utf-8")
                with self.subTest(folder=folder):
                    with self.assertRaisesRegex(ValueError, "ignored/generated"):
                        source_file_state(root, f"{folder}/Hidden.cs")

    def test_direct_localization_access_rejects_hidden_and_generated_trees(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                root.mkdir()
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                for folder in (".git", ".private", "obj", "bin", ".vs"):
                    target = root / folder / "en-US.hjson"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("Greeting: Hidden\n", encoding="utf-8")
                    with self.subTest(folder=folder):
                        with self.assertRaisesRegex(ValueError, "ignored/generated"):
                            server.localization_file_state(f"{folder}/en-US.hjson")
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
