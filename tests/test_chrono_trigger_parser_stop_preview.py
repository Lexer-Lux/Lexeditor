from __future__ import annotations

import unittest

from games.chrono_trigger.field_commands import disassemble_function


class ParserStopPreviewTests(unittest.TestCase):
    def test_unresolved_opcode_carries_bounded_raw_preview(self):
        raw = bytes((
            0xF1, 0x22, 0x80, 0x00, 0xAD, 0x01, 0xAD, 0x02,
            0xAD, 0x03, 0xAD, 0x04, 0xAD, 0x05, 0xAD, 0x06,
            0xAD, 0x07, 0x00,
        ))
        result = disassemble_function(raw, 0, len(raw))
        problem = result["problem"]
        self.assertFalse(result["complete"])
        self.assertEqual(problem["opcode"], 0xF1)
        self.assertEqual(problem["offset"], 0)
        self.assertEqual(problem["remainingBytes"], len(raw))
        self.assertEqual(
            problem["rawPreview"],
            "F1 22 80 00 AD 01 AD 02 AD 03 AD 04 AD 05 AD 06",
        )
        self.assertTrue(problem["truncatedPreview"])

    def test_truncated_known_command_carries_all_remaining_bytes(self):
        # 0x13 needs opcode + five argument bytes, but this function contains
        # only three total bytes. The preview must not cross the function end.
        raw = bytes((0x13, 0x10, 0x34, 0xAD, 0x01))
        result = disassemble_function(raw, 0, 3)
        problem = result["problem"]
        self.assertEqual(problem["opcode"], 0x13)
        self.assertEqual(problem["remainingBytes"], 3)
        self.assertEqual(problem["rawPreview"], "13 10 34")
        self.assertFalse(problem["truncatedPreview"])
        self.assertIn("command needs 6 bytes but only 3 remain", problem["reason"])


if __name__ == "__main__":
    unittest.main()
