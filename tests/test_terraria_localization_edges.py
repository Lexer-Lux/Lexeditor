from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria.localization import parse_localization_text
from games.terraria import server


class TerrariaLocalizationEdgeTests(unittest.TestCase):
    def test_inline_triple_quote_body_is_not_reparsed_as_keys(self):
        text = (
            "{\n"
            "  Tooltip: '''\n"
            "  Line: this colon is multiline text\n"
            "  Another: still text\n"
            "  '''\n"
            "  Greeting: Hello\n"
            "}\n"
        )
        document = parse_localization_text(text)
        self.assertEqual(
            [entry.key for entry in document.entries],
            ["Tooltip", "Greeting"],
        )
        self.assertEqual(document.entries[0].kind, "multiline")
        self.assertFalse(document.entries[0].editable)
        self.assertEqual(document.entries[1].value, "Hello")
        self.assertEqual(document.duplicates, ())
        self.assertEqual(document.unsupported, 1)

    def test_explicit_root_braces_are_structural_not_unsupported(self):
        document = parse_localization_text("{\n\tGreeting: Hello\n}\n")
        self.assertEqual(document.unsupported, 0)
        self.assertEqual(document.entries[0].key, "Greeting")
        self.assertTrue(document.entries[0].editable)

    def test_service_saves_existing_edits_and_new_keys_in_one_transaction(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                localization = root / "Localization"
                localization.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                target = localization / "en-US_Mods.ExampleMod.hjson"
                target.write_text("Greeting: Hello\n", encoding="utf-8")

                state = server.localization_file_state("Localization/en-US_Mods.ExampleMod.hjson")
                saved = server.save_localization(
                    state["path"],
                    {"Mods.ExampleMod.Greeting": "Howdy"},
                    state["sha256"],
                    {"Mods.ExampleMod.Custom.NewKey": "Created"},
                )

                values = {entry["key"]: entry["value"] for entry in saved["entries"]}
                self.assertEqual(values["Mods.ExampleMod.Greeting"], "Howdy")
                self.assertEqual(values["Mods.ExampleMod.Custom.NewKey"], "Created")
                raw = target.read_text(encoding="utf-8")
                self.assertIn("Greeting: Howdy\n", raw)
                self.assertIn('"Custom.NewKey": "Created"\n', raw)

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_localization(
                        state["path"],
                        {},
                        state["sha256"],
                        {"Mods.ExampleMod.Custom.Stale": "Nope"},
                    )
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
