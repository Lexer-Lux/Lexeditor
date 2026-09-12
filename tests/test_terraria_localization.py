from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from games.terraria.localization import (
    parse_localization_text,
    try_get_culture_and_prefix,
    update_localization_text,
)
from games.terraria import server


class TerrariaLocalizationTests(unittest.TestCase):
    def test_culture_and_prefix_matches_tmodloader_path_shapes(self):
        self.assertEqual(
            try_get_culture_and_prefix("Localization/en-US.hjson"),
            ("en-US", ""),
        )
        self.assertEqual(
            try_get_culture_and_prefix("Localization/en-US_Mods.ExampleMod.hjson"),
            ("en-US", "Mods.ExampleMod"),
        )
        self.assertEqual(
            try_get_culture_and_prefix("Localization/en-US/Mods.ExampleMod.hjson"),
            ("en-US", "Mods.ExampleMod"),
        )
        self.assertIsNone(try_get_culture_and_prefix("Localization/notes.hjson"))

    def test_flattens_nested_and_dotted_keys_without_losing_source_shape(self):
        text = (
            "# keep me\n"
            "Mods: {\n"
            "  ExampleMod: {\n"
            "    Common.PaperAirplane: Paper Airplane\n"
            "    Items: {\n"
            "      Sword.DisplayName: \"Example Sword\"\n"
            "      Sword.Tooltip: Damage: {0} // retained\n"
            "    }\n"
            "  }\n"
            "}\n"
        )
        document = parse_localization_text(text)
        self.assertEqual(document.duplicates, ())
        self.assertEqual(
            [entry.key for entry in document.entries],
            [
                "Mods.ExampleMod.Common.PaperAirplane",
                "Mods.ExampleMod.Items.Sword.DisplayName",
                "Mods.ExampleMod.Items.Sword.Tooltip",
            ],
        )
        self.assertEqual(document.entries[0].value, "Paper Airplane")
        self.assertEqual(document.entries[1].value, "Example Sword")
        self.assertEqual(document.entries[2].value, "Damage: {0}")
        self.assertTrue(all(entry.editable for entry in document.entries))

    def test_prefix_is_applied_to_effective_keys(self):
        document = parse_localization_text(
            "Items: {\n  Sword.DisplayName: Example Sword\n}\n",
            prefix="Mods.ExampleMod",
        )
        self.assertEqual(
            document.entries[0].key,
            "Mods.ExampleMod.Items.Sword.DisplayName",
        )
        self.assertEqual(document.entries[0].source_key, "Items.Sword.DisplayName")

    def test_noop_is_byte_exact_and_changed_lines_preserve_formatting(self):
        text = (
            "Mods: {\r\n"
            "\tExampleMod: {\r\n"
            "\t\tGreeting   :   Hello there,   # keep this\r\n"
            "\t\tQuoted: \"Old value\", // keep too\r\n"
            "\t}\r\n"
            "}\r\n"
        )
        self.assertEqual(
            update_localization_text(
                text,
                {"Mods.ExampleMod.Greeting": "Hello there"},
            ),
            text,
        )
        changed = update_localization_text(
            text,
            {
                "Mods.ExampleMod.Greeting": "Howdy",
                "Mods.ExampleMod.Quoted": "New value",
            },
        )
        self.assertEqual(
            changed,
            "Mods: {\r\n"
            "\tExampleMod: {\r\n"
            "\t\tGreeting   :   Howdy,   # keep this\r\n"
            "\t\tQuoted: \"New value\", // keep too\r\n"
            "\t}\r\n"
            "}\r\n",
        )

    def test_risky_unquoted_value_is_json_quoted(self):
        text = "Mods: {\n  ExampleMod: {\n    Greeting: Hello\n  }\n}\n"
        changed = update_localization_text(
            text,
            {"Mods.ExampleMod.Greeting": "Hello, # world"},
        )
        self.assertIn('Greeting: "Hello, # world"', changed)

    def test_multiline_and_typed_values_are_read_only(self):
        text = (
            "Mods: {\n"
            "  ExampleMod: {\n"
            "    Tooltip:\n"
            "      '''\n"
            "      Line one\n"
            "      Line two\n"
            "      '''\n"
            "    Count: 3\n"
            "  }\n"
            "}\n"
        )
        document = parse_localization_text(text)
        by_key = {entry.key: entry for entry in document.entries}
        self.assertFalse(by_key["Mods.ExampleMod.Tooltip"].editable)
        self.assertEqual(by_key["Mods.ExampleMod.Tooltip"].kind, "multiline")
        self.assertFalse(by_key["Mods.ExampleMod.Count"].editable)
        with self.assertRaisesRegex(ValueError, "not safely editable"):
            update_localization_text(text, {"Mods.ExampleMod.Tooltip": "One line"})

    def test_parent_value_matches_tmodloader_flattening(self):
        document = parse_localization_text(
            "Mods: {\n  ExampleMod: {\n    Items: {\n      $parentVal: Items parent\n    }\n  }\n}\n"
        )
        self.assertEqual(document.entries[0].key, "Mods.ExampleMod.Items")

    def test_duplicate_effective_keys_fail_closed(self):
        text = (
            "Mods: {\n"
            "  ExampleMod: {\n"
            "    Greeting: One\n"
            "    Greeting: Two\n"
            "  }\n"
            "}\n"
        )
        document = parse_localization_text(text)
        self.assertEqual(document.duplicates, ("Mods.ExampleMod.Greeting",))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            update_localization_text(text, {"Mods.ExampleMod.Greeting": "Three"})

    def test_unknown_or_multiline_new_values_are_rejected(self):
        text = "Mods: {\n  ExampleMod: {\n    Greeting: Hello\n  }\n}\n"
        with self.assertRaisesRegex(ValueError, "not present"):
            update_localization_text(text, {"Mods.ExampleMod.Missing": "Nope"})
        with self.assertRaisesRegex(ValueError, "one line"):
            update_localization_text(text, {"Mods.ExampleMod.Greeting": "Hello\nWorld"})

    def test_service_discovers_saves_and_stale_checks_localization(self):
        previous_project = os.environ.get("LEXEDITOR_TERRARIA_PROJECT")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "ExampleMod"
                localization = root / "Localization"
                localization.mkdir(parents=True)
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = str(root)
                target = localization / "en-US_Mods.ExampleMod.hjson"
                original = server.UTF8_BOM + (
                    "Items: {\r\n"
                    "  Sword.DisplayName: Example Sword\r\n"
                    "}\r\n"
                ).encode("utf-8")
                target.write_bytes(original)

                index = server.localization_index()
                self.assertEqual(len(index["files"]), 1)
                summary = index["files"][0]
                self.assertEqual(summary["culture"], "en-US")
                self.assertEqual(summary["prefix"], "Mods.ExampleMod")
                self.assertEqual(summary["editableEntries"], 1)

                state = server.localization_file_state(summary["path"])
                self.assertTrue(state["editable"])
                self.assertEqual(
                    state["entries"][0]["key"],
                    "Mods.ExampleMod.Items.Sword.DisplayName",
                )
                original_sha = state["sha256"]
                saved = server.save_localization(
                    summary["path"],
                    {"Mods.ExampleMod.Items.Sword.DisplayName": "Renamed Sword"},
                    original_sha,
                )
                self.assertNotEqual(saved["sha256"], original_sha)
                raw = target.read_bytes()
                self.assertTrue(raw.startswith(server.UTF8_BOM))
                self.assertIn(b"Sword.DisplayName: Renamed Sword\r\n", raw)

                with self.assertRaisesRegex(ValueError, "changed outside Lexeditor"):
                    server.save_localization(
                        summary["path"],
                        {"Mods.ExampleMod.Items.Sword.DisplayName": "Again"},
                        original_sha,
                    )
                with self.assertRaisesRegex(ValueError, "Invalid localization path"):
                    server.localization_file_state("../outside.hjson")

                data_map = server.data_map()
                row = next(row for row in data_map["rows"] if row["path"].endswith(".hjson"))
                self.assertEqual(row["status"], "structured")
        finally:
            if previous_project is None:
                os.environ.pop("LEXEDITOR_TERRARIA_PROJECT", None)
            else:
                os.environ["LEXEDITOR_TERRARIA_PROJECT"] = previous_project


if __name__ == "__main__":
    unittest.main()
