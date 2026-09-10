from __future__ import annotations

import unittest

from games.chrono_trigger.event_edit import VARIABLE_OR_UNRESOLVED
from games.chrono_trigger.field_commands import _PC_ARGUMENT_BYTES
from games.chrono_trigger.editor_registry import editor_schema


class DynamicWritePolicyTests(unittest.TestCase):
    def test_raw_writer_blocks_every_dynamic_or_unresolved_pc_opcode(self):
        decoder_dynamic = {
            opcode
            for opcode, width in enumerate(_PC_ARGUMENT_BYTES)
            if width is None or width == -1
        }
        self.assertEqual(
            VARIABLE_OR_UNRESOLVED,
            decoder_dynamic,
            "raw event writer policy must track every dynamic/unresolved PC boundary",
        )

    def test_dynamic_or_unresolved_pc_opcodes_never_get_named_fixed_editors(self):
        # Canonical representatives for dynamic forms that can be decoded; the
        # unresolved opcodes only need a width-shaped placeholder because a
        # named editor must never attach to them in the first place.
        representatives = {
            0x2E: b"\x40\x01\x02\x03\x04",
            0x4E: b"\x00\x20\x02\x00",
            0x88: b"\x80\x11",
            0x9E: b"\x00",
            0x9F: b"\x00",
            0xEC: b"\x88",
            0xF1: b"\x21\x80",
            0xFF: b"\x42",
        }
        self.assertEqual(set(representatives), VARIABLE_OR_UNRESOLVED)
        for opcode, arguments in representatives.items():
            with self.subTest(opcode=f"0x{opcode:02X}"):
                command = {
                    "opcode": opcode,
                    "argumentsHex": arguments.hex(" ").upper(),
                    "argumentBytes": len(arguments),
                }
                self.assertIsNone(editor_schema(command))


if __name__ == "__main__":
    unittest.main()
