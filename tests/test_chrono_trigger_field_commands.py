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

    def test_dynamic_f1_width(self):
        decoded = disassemble_function(bytes([0xF1, 0x00, 0xF1, 0x21, 0x80]), 0, 5)
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [2, 3])

    def test_dynamic_88_modes(self):
        decoded = disassemble_function(bytes([0x88, 0x01, 0x88, 0x80, 0x44]), 0, 5)
        self.assertTrue(decoded["complete"])
        self.assertEqual([row["size"] for row in decoded["commands"]], [2, 3])

    def test_dynamic_memory_copy_uses_pc_length_field(self):
        data = bytes([0x4E, 0x00, 0x20, 0x05, 0x00, 0xAA, 0xBB, 0xCC])
        decoded = disassemble_function(data, 0, len(data))
        self.assertTrue(decoded["complete"])
        self.assertEqual(decoded["commands"][0]["size"], 8)

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
