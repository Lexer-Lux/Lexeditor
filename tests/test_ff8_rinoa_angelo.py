"""Static contracts for Rinoa's fixed Angelo command."""
from pathlib import Path
import unittest

from games.ff8 import fixed_command_menu, kernel_text


class RinoaAngeloFixedCommandTests(unittest.TestCase):
    def test_angelo_uses_vanilla_combine_command(self):
        self.assertEqual(fixed_command_menu.RINOA, 4)
        self.assertEqual(fixed_command_menu.COMBINE_COMMAND, 0x13)
        self.assertEqual(
            fixed_command_menu.CHARACTER_COMMANDS[fixed_command_menu.RINOA],
            ("Rinoa", "Angelo", 0x13),
        )
        self.assertEqual(
            fixed_command_menu.supported_command_audit()["Rinoa"],
            ("Angelo", "verified vanilla Combine submenu/dispatcher"),
        )

    def test_runtime_metadata_is_copied_from_loaded_kernel_command(self):
        self.assertEqual(fixed_command_menu.KERNEL_BATTLE_COMMANDS, 0x01CF3F2C)
        self.assertEqual(
            fixed_command_menu.COMBINE_MENU_TARGET,
            fixed_command_menu.KERNEL_BATTLE_COMMANDS
            + fixed_command_menu.COMBINE_COMMAND * 8 + 5,
        )
        payload = fixed_command_menu._post_builder_payload()
        self.assertIn(bytes.fromhex("C6 46 26 13"), payload)
        self.assertIn(
            bytes.fromhex("66 A1")
            + fixed_command_menu.COMBINE_MENU_TARGET.to_bytes(4, "little"),
            payload,
        )
        self.assertIn(bytes.fromhex("66 89 46 27"), payload)
        self.assertIn(bytes.fromhex("C6 46 29 00"), payload)

    def test_rinoa_source_slot_remains_empty_until_post_builder(self):
        magic, character, gf, alternate = fixed_command_menu.fixed_source_commands(
            fixed_command_menu.RINOA, 0
        )
        self.assertEqual(magic, fixed_command_menu.MAGIC_SOURCE_ABILITY)
        self.assertEqual(character, fixed_command_menu.EMPTY_SOURCE_ABILITY)
        self.assertEqual(gf, fixed_command_menu.EMPTY_SOURCE_ABILITY)
        self.assertEqual(alternate, fixed_command_menu.EMPTY_SOURCE_ABILITY)

    def test_angelo_label_uses_ff8_encoding(self):
        self.assertEqual(
            fixed_command_menu.ANGELO_TEXT,
            kernel_text.encode("Angelo", compress=False) + b"\0",
        )
        label = fixed_command_menu._command_label_payload()
        self.assertIn(fixed_command_menu.ANGELO_TEXT, label)
        self.assertLessEqual(
            fixed_command_menu.COMMAND_LABEL_CAVE + len(label),
            fixed_command_menu.POST_BUILDER_CAVE,
        )

    def test_post_builder_still_fits_reserved_region(self):
        payload = fixed_command_menu._post_builder_payload()
        self.assertLessEqual(
            fixed_command_menu.POST_BUILDER_CAVE + len(payload),
            fixed_command_menu.LEARNED_COMMAND_CAVE,
        )

    def test_no_stale_rinoa_blocker_remains(self):
        source = (Path(__file__).resolve().parents[1] / "games/ff8/fixed_command_menu.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Angelo is explicitly TBD", source)
        self.assertNotIn("Rinoa's Angelo remains unavailable", source)


if __name__ == "__main__":
    unittest.main()
