from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from games.terraria.content_wizard import (
    create_mod_item,
    default_display_name,
    placeholder_png,
    render_mod_item_source,
    validate_content_name,
)
from games.terraria.localization import parse_localization_text


class TerrariaContentWizardTests(unittest.TestCase):
    def test_identifier_and_display_name_validation(self):
        self.assertEqual(validate_content_name("ExampleSword"), "ExampleSword")
        self.assertEqual(default_display_name("ExampleSword"), "Example Sword")
        self.assertEqual(default_display_name("XMLSword_Item"), "XML Sword Item")
        for invalid in ("", "Bad Name", "123Item", "class", "Item-Name"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_content_name(invalid)

    def test_source_template_is_minimal_moditem_scaffold(self):
        source = render_mod_item_source("ExampleMod", "ExampleSword")
        self.assertIn("using Terraria.ModLoader;", source)
        self.assertIn("namespace ExampleMod.Content.Items;", source)
        self.assertIn("public sealed class ExampleSword : ModItem", source)
        self.assertIn("public override void SetDefaults()", source)
        self.assertIn("Item.width = 20;", source)
        self.assertIn("Item.height = 20;", source)
        self.assertNotIn("AddRecipes", source)
        self.assertNotIn("Item.damage", source)

    def test_placeholder_texture_is_valid_16_pixel_png(self):
        data = placeholder_png()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(int.from_bytes(data[16:20], "big"), 16)
        self.assertEqual(int.from_bytes(data[20:24], "big"), 16)

    def test_create_mod_item_writes_source_texture_and_localization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            result = create_mod_item(
                root,
                "ExampleSword",
                "Example Sword",
                "A generated test item.",
            )

            self.assertEqual(result["kind"], "item")
            self.assertEqual(result["source"]["path"], "Content/Items/ExampleSword.cs")
            self.assertEqual(result["texture"]["path"], "Content/Items/ExampleSword.png")
            self.assertEqual((result["texture"]["width"], result["texture"]["height"]), (16, 16))
            self.assertTrue((root / result["source"]["path"]).is_file())
            self.assertTrue((root / result["texture"]["path"]).is_file())

            localization = (root / "Localization" / "en-US.hjson").read_text(encoding="utf-8")
            document = parse_localization_text(localization)
            values = {entry.key: entry.value for entry in document.entries}
            self.assertEqual(values["Mods.ExampleMod.Items.ExampleSword.DisplayName"], "Example Sword")
            self.assertEqual(values["Mods.ExampleMod.Items.ExampleSword.Tooltip"], "A generated test item.")
            self.assertEqual(document.duplicates, ())

    def test_create_mod_item_reuses_existing_localization_and_omits_empty_tooltip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            localization = root / "Localization"
            localization.mkdir(parents=True)
            target = localization / "en-US.hjson"
            target.write_text("Existing.Key: Keep me\n", encoding="utf-8")

            result = create_mod_item(root, "MagicRock", "", "")
            self.assertEqual(result["displayName"], "Magic Rock")
            self.assertEqual(result["tooltip"], "")
            text = target.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("Existing.Key: Keep me\n"))
            document = parse_localization_text(text)
            values = {entry.key: entry.value for entry in document.entries}
            self.assertEqual(values["Existing.Key"], "Keep me")
            self.assertEqual(values["Mods.ExampleMod.Items.MagicRock.DisplayName"], "Magic Rock")
            self.assertNotIn("Mods.ExampleMod.Items.MagicRock.Tooltip", values)

    def test_create_mod_item_never_overwrites_existing_source_or_texture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            content = root / "Content" / "Items"
            content.mkdir(parents=True)
            existing = content / "Existing.cs"
            existing.write_text("keep", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "already exists"):
                create_mod_item(root, "Existing")
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")
            self.assertFalse((content / "Existing.png").exists())

            existing.unlink()
            texture = content / "Existing.png"
            texture.write_bytes(placeholder_png())
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_mod_item(root, "Existing")
            self.assertFalse(existing.exists())

    def test_multiline_user_text_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ExampleMod"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "one line"):
                create_mod_item(root, "Thing", "Thing", "bad\ntooltip")
            self.assertFalse((root / "Content").exists())


if __name__ == "__main__":
    unittest.main()
