from __future__ import annotations

import unittest

from games.chrono_trigger.field_commands import command_spec, disassemble_function


class FieldCommandTests(unittest.TestCase):
    def test_pc_fixed_width_overrides(self):
        data = bytes([
            0xBB, 0x34, 0x12,
            0x83, 0x78, 0x56, 0x09,
            0xDC, 0x34, 0x12, 0x02, 0x10, 0x20,
            0x47,
        ])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [3, 4, 6, 1])
        self.assertEqual(decoded["commands"][0]["name"], "Personal Textbox")
        self.assertEqual(decoded["commands"][1]["name"], "Load Enemy")
        self.assertEqual(decoded["commands"][2]["name"], "Change Location")

    def test_f1_conflicting_public_width_rules_fail_closed(self):
        # Temporal Redux's live ColorAddMenu can emit a one-argument F1 with a
        # nonzero color/intensity byte, while its command-table description says
        # a nonzero first argument carries a second 0x80 add/sub byte. Raw event
        # bytes cannot distinguish F1 21 + following opcode 80 from F1 21 80.
        for data in (
            bytes([0xF1, 0x00, 0x00]),
            bytes([0xF1, 0x21, 0x00]),
            bytes([0xF1, 0x21, 0x80, 0x00]),
        ):
            with self.subTest(data=data.hex()):
                decoded = disassemble_function(data, 0, len(data))
                self.assertFalse(decoded["complete"])
                self.assertEqual(decoded["commands"], [])
                self.assertEqual(decoded["problem"]["opcode"], 0xF1)
                self.assertIn("unresolved", decoded["problem"]["reason"])

    def test_color_math_pc_modes_match_platform_parser(self):
        data = bytes([
            0x2E, 0x40, 0x01, 0x02, 0x34, 0x05,
            0x2E, 0x57, 0x06, 0x07, 0x89, 0x0A,
            0x2E, 0x80, 0x31, 0x05,
            0x00,
        ])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [6, 6, 4, 1])
        self.assertEqual(decoded["commands"][2]["argumentsHex"], "80 31 05")

    def test_dynamic_88_pc_modes_match_platform_parser(self):
        data = bytes([
            0x88, 0x01,
            0x88, 0x20, 0x11, 0x22,
            0x88, 0x30, 0x33, 0x44,
            0x88, 0x40, 0x55, 0x66, 0x77,
            0x88, 0x50, 0x88, 0x99, 0xAA,
            0x88, 0x80, 0xBB,
            0x00,
        ])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [2, 4, 4, 5, 5, 3, 1])
        self.assertEqual(decoded["commands"][-2]["argumentsHex"], "80 BB")

    def test_dynamic_ec_known_subcommand_widths_preserve_following_boundaries(self):
        # EC/88 is subcommand-only (1 arg), EC/14 has one extra parameter
        # (2 args total), and EC/82 has two extra parameters (3 args total).
        data = bytes([
            0xEC, 0x88,
            0xAD, 0x01,
            0xEC, 0x14, 0x05,
            0xAD, 0x02,
            0xEC, 0x82, 0x03, 0x7F,
            0x00,
        ])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["opcode"] for row in decoded["commands"]], [
            0xEC, 0xAD, 0xEC, 0xAD, 0xEC, 0x00,
        ])
        self.assertEqual([row["size"] for row in decoded["commands"]], [2, 2, 3, 2, 4, 1])
        self.assertEqual(decoded["commands"][0]["argumentsHex"], "88")
        self.assertEqual(decoded["commands"][2]["argumentsHex"], "14 05")
        self.assertEqual(decoded["commands"][4]["argumentsHex"], "82 03 7F")

    def test_dynamic_ec_covers_all_documented_sound_menu_subcommands(self):
        expected_argument_bytes = {
            0x88: 1, 0xF0: 1, 0xF2: 1,
            0x14: 2, 0x19: 2,
            0x82: 3, 0x83: 3, 0x85: 3, 0x86: 3,
        }
        for subcommand, width in expected_argument_bytes.items():
            with self.subTest(subcommand=subcommand):
                data = bytes([0xEC, subcommand, 0x11, 0x22])
                spec, error = command_spec(data, 0)
                self.assertIsNone(error)
                self.assertEqual(spec.argument_bytes, width)

    def test_unknown_ec_subcommand_fails_closed(self):
        decoded = disassemble_function(bytes([0xEC, 0x99, 0x00]), 0, 3)
        self.assertFalse(decoded["complete"])
        self.assertEqual(decoded["commands"], [])
        self.assertEqual(decoded["problem"]["opcode"], 0xEC)
        self.assertIn("unknown PC all-purpose sound subcommand 0x99", decoded["problem"]["reason"])

    def test_truncated_known_ec_subcommand_does_not_consume_following_bytes(self):
        # EC/82 requires opcode + subcommand + two parameters = four bytes.
        decoded = disassemble_function(bytes([0xEC, 0x82, 0x03]), 0, 3)
        self.assertFalse(decoded["complete"])
        self.assertEqual(decoded["commands"], [])
        self.assertIn("needs 4 bytes but only 3 remain", decoded["problem"]["reason"])

    def test_dynamic_mode7_known_forms_preserve_following_boundaries(self):
        data = bytes([
            0xFF, 0x42,
            0xAD, 0x01,
            0xFF, 0x90, 0x11, 0x22, 0x33,
            0xFF, 0x91,
            0xFF, 0x97, 0x44, 0x55, 0x66,
            0xFF, 0x98,
            0x00,
        ])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["opcode"] for row in decoded["commands"]], [
            0xFF, 0xAD, 0xFF, 0xFF, 0xFF, 0xFF, 0x00,
        ])
        self.assertEqual([row["size"] for row in decoded["commands"]], [2, 2, 5, 2, 5, 2, 1])

    def test_unknown_mode7_modes_fail_closed(self):
        for mode in (0x8A, 0x8F, 0x99, 0xFF):
            with self.subTest(mode=mode):
                decoded = disassemble_function(bytes([0xFF, mode, 0x00]), 0, 3)
                self.assertFalse(decoded["complete"])
                self.assertEqual(decoded["commands"], [])
                self.assertEqual(decoded["problem"]["opcode"], 0xFF)
                self.assertIn(f"unknown PC Mode 7 mode 0x{mode:02X}", decoded["problem"]["reason"])

    def test_eb_song_volume_remains_fixed_two_argument_bytes(self):
        data = bytes([0xEB, 0x20, 0xFF, 0x00])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [3, 1])
        self.assertEqual(decoded["commands"][0]["argumentsHex"], "20 FF")

    def test_dynamic_memory_copy_uses_pc_layout_and_length_field(self):
        # PC get_command(): [destination u16][encoded length u16][payload].
        # encoded length includes its own two bytes, so 5 means three payload bytes.
        data = bytes([0x4E, 0x00, 0x20, 0x05, 0x00, 0xAA, 0xBB, 0xCC, 0x00])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [8, 1])
        self.assertEqual(decoded["commands"][0]["argumentsHex"], "00 20 05 00 AA BB CC")

    def test_invalid_memory_copy_fails_closed(self):
        data = bytes([0x4E, 0x00, 0x20, 0x01, 0x00])
        decoded = disassemble_function(data, 0, len(data))
        self.assertFalse(decoded["complete"])
        self.assertIn("encoded length", decoded["problem"]["reason"])

    def test_unknown_color_math_mode_fails_closed(self):
        spec, error = command_spec(bytes([0x2E, 0x10]), 0)
        self.assertIsNone(spec)
        self.assertIn("unknown PC color-math mode", error)

    def test_unresolved_9e_fails_closed(self):
        decoded = disassemble_function(bytes([0x9E, 0x01, 0x02]), 0, 3)
        self.assertFalse(decoded["complete"])
        self.assertEqual(decoded["problem"]["opcode"], 0x9E)
        self.assertIn("unresolved", decoded["problem"]["reason"])

    def test_command_may_not_cross_function_end(self):
        data = bytes([0x83, 0x01, 0x00, 0x02])
        decoded = disassemble_function(data, 0, 3)
        self.assertFalse(decoded["complete"])
        self.assertIn("only 3 remain", decoded["problem"]["reason"])


if __name__ == "__main__":
    unittest.main()
