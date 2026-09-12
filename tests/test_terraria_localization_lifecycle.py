from __future__ import annotations

import unittest

from games.terraria.localization_lifecycle import (
    apply_localization_transaction,
    delete_localization_entries,
)


class TerrariaLocalizationLifecycleTests(unittest.TestCase):
    def test_delete_scalar_leaf_preserves_neighboring_source(self):
        text = (
            "Mods: {\r\n"
            "  ExampleMod: {\r\n"
            "    Keep: Keep me\r\n"
            "    Remove: Delete me # inline comment\r\n"
            "    After: Still here\r\n"
            "  }\r\n"
            "}\r\n"
        )
        changed = delete_localization_entries(text, ["Mods.ExampleMod.Remove"])
        self.assertEqual(
            changed,
            "Mods: {\r\n"
            "  ExampleMod: {\r\n"
            "    Keep: Keep me\r\n"
            "    After: Still here\r\n"
            "  }\r\n"
            "}\r\n",
        )

    def test_delete_rejects_multiline_typed_unknown_and_duplicates(self):
        multiline = (
            "Mods: {\n"
            "  ExampleMod: {\n"
            "    Tooltip:\n"
            "      '''\n"
            "      Line\n"
            "      '''\n"
            "    Count: 3\n"
            "  }\n"
            "}\n"
        )
        with self.assertRaisesRegex(ValueError, "not safely deletable"):
            delete_localization_entries(multiline, ["Mods.ExampleMod.Tooltip"])
        with self.assertRaisesRegex(ValueError, "not safely deletable"):
            delete_localization_entries(multiline, ["Mods.ExampleMod.Count"])
        with self.assertRaisesRegex(ValueError, "not present"):
            delete_localization_entries(multiline, ["Mods.ExampleMod.Missing"])

        duplicate = "Greeting: One\nGreeting: Two\n"
        with self.assertRaisesRegex(ValueError, "duplicate"):
            delete_localization_entries(duplicate, ["Greeting"])

    def test_transaction_rejects_operation_overlap(self):
        text = "Greeting: Hello\n"
        with self.assertRaisesRegex(ValueError, "multiple operations"):
            apply_localization_transaction(
                text,
                {"Greeting": "Changed"},
                {},
                ["Greeting"],
            )
        with self.assertRaisesRegex(ValueError, "multiple operations"):
            apply_localization_transaction(
                text,
                {},
                {"New": "Value"},
                ["New"],
            )

    def test_transaction_updates_deletes_and_creates_together(self):
        text = "Keep: Old\nRemove: Gone\n"
        changed = apply_localization_transaction(
            text,
            {"Keep": "New"},
            {"Added": "Fresh"},
            ["Remove"],
        )
        self.assertIn("Keep: New\n", changed)
        self.assertNotIn("Remove:", changed)
        self.assertIn('"Added": "Fresh"\n', changed)


if __name__ == "__main__":
    unittest.main()
