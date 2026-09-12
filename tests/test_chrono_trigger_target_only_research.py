from __future__ import annotations

import unittest

from games.chrono_trigger.editor_registry import editor_schema
from games.chrono_trigger.target_only_ops import (
    TARGET_ONLY_OPCODES,
    apply_target_only_op,
    target_only_semantics,
    target_only_values,
)


def command(opcode: int, arguments: bytes) -> dict:
    return {
        "opcode": opcode,
        "argumentsHex": arguments.hex(" ").upper(),
        "argumentBytes": len(arguments),
    }


class TargetOnlyResearchTests(unittest.TestCase):
    def test_research_candidates_are_not_registered_for_writes(self):
        fixtures = {
            0x67: b"\xA5\x10",
            0x75: b"\x11",
            0x76: b"\x12",
            0x77: b"\x13",
        }
        self.assertEqual(set(fixtures), set(TARGET_ONLY_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=f"0x{opcode:02X}"):
                # Direct research helpers may decode the proven target operand,
                # but the production editor registry must remain closed until
                # the unresolved operation semantics are deliberately promoted.
                self.assertIsNotNone(target_only_values(command(opcode, args)))
                self.assertIsNotNone(target_only_semantics(command(opcode, args)))
                self.assertIsNone(editor_schema(command(opcode, args)))

    def test_research_patch_changes_only_the_proven_target_operand(self):
        reset_bits = command(0x67, b"\xA5\x10")
        rewritten = apply_target_only_op(reset_bits, {"memoryAddress": 0x7F0240})
        self.assertEqual(rewritten, b"\xA5\x20")
        self.assertEqual(target_only_semantics(reset_bits)["rawMask"], 0xA5)
        self.assertFalse(target_only_semantics(reset_bits)["operationDetailsResolved"])

        for opcode in (0x75, 0x76, 0x77):
            with self.subTest(opcode=f"0x{opcode:02X}"):
                rewritten = apply_target_only_op(command(opcode, b"\x10"), {"memoryAddress": 0x7F0240})
                self.assertEqual(rewritten, b"\x20")

    def test_research_helpers_preserve_even_script_memory_domain(self):
        for opcode, args in ((0x67, b"\xA5\x10"), (0x75, b"\x10")):
            with self.subTest(opcode=f"0x{opcode:02X}"):
                with self.assertRaisesRegex(ValueError, "even script-memory address"):
                    apply_target_only_op(command(opcode, args), {"memoryAddress": 0x7F0201})


if __name__ == "__main__":
    unittest.main()
