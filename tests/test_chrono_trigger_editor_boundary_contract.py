from __future__ import annotations

import unittest

from games.chrono_trigger.editor_registry import editor_schema
from games.chrono_trigger.field_commands import command_spec


# Representative canonical encodings for every custom registry family.  The
# purpose is not to retest each module's semantics; those have dedicated suites.
# This contract ensures no named custom editor can disagree with the Steam
# command-boundary decoder about how many bytes belong to its opcode.
CUSTOM_EDITOR_FIXTURES = {
    # comparisons
    0x12: b"\x10\x7F\x02\x01",
    0x13: b"\x10\x34\x12\x02\x01",
    0x14: b"\x10\x11\x02\x01",
    0x15: b"\x10\x11\x02\x01",
    0x16: b"\x44\x7F\x02\x01",
    # raw PC segment memory
    0x48: b"\x34\x12\x10",
    0x49: b"\x34\x12\x10",
    0x4A: b"\x34\x12\x7F",
    0x4B: b"\x34\x12\x78\x56",
    0x4C: b"\x34\x12\x10",
    0x4D: b"\x34\x12\x10",
    # memory
    0x19: b"\x10",
    0x1A: b"\x05\x01",
    0x1C: b"\x44",
    0x4F: b"\x7F\x10",
    0x50: b"\x34\x12\x10",
    0x51: b"\x10\x11",
    0x52: b"\x10\x11",
    0x53: b"\x34\x01\x10",
    0x54: b"\x34\x01\x10",
    0x56: b"\x7F\x34\x12",
    0x58: b"\x10\x34\x01",
    0x59: b"\x10\x34\x01",
    0x5B: b"\x04\x10",
    0x5D: b"\x10\x11",
    0x5E: b"\x10\x11",
    0x5F: b"\x04\x10",
    0x71: b"\x10",
    0x72: b"\x10",
    0x73: b"\x10",
    # bit operations
    0x63: b"\x03\x10",
    0x64: b"\x04\x10",
    0x65: b"\x03\x44",
    0x66: b"\x85\x55",
    0x69: b"\xA5\x10",
    0x6B: b"\x5A\x10",
    0x6F: b"\x03\x10",
    # PC-only extended raw slots
    0x3A: b"\x7F\x10",
    0x3D: b"\x11\x12",
    0x3E: b"\x13\x14",
    0x45: b"\x02\x15",
    0x46: b"\x03\x16",
    0x6E: b"\x20\x7F\x02\x01",
    0x70: b"\x04\x17",
    0x74: b"\x18\x19",
    0x78: b"\x1A\x1B",
    # calls
    0x02: b"\x08\x21",
    0x03: b"\x08\x21",
    0x04: b"\x08\x21",
    0x05: b"\x08\x21",
    0x06: b"\x08\x21",
    0x07: b"\x08\x21",
    # object / facing / property
    0x0A: b"\x08",
    0x0B: b"\x08",
    0x0C: b"\x08",
    0x7C: b"\x08",
    0x7D: b"\x08",
    0x23: b"\x06\x10",
    0x24: b"\x04\x10",
    0xA8: b"\x08",
    0xA9: b"\x0A",
    0x1E: b"\x08",
    0x1F: b"\x08",
    0x25: b"\x08",
    0x26: b"\x08",
    0x0D: b"\x03",
    0x0E: b"\x03",
    # movement / scene event
    0x7A: b"\x10\x20\x08",
    0x8F: b"\x02",
    0x94: b"\x20",
    0x95: b"\x03",
    0x96: b"\x10\x20",
    0x97: b"\x10\x11",
    0x98: b"\x20\x08",
    0x99: b"\x04\x08",
    0x9A: b"\x10\x20\x08",
    0x9D: b"\x10\x11",
    0xA0: b"\x10\x20",
    0xA1: b"\x10\x11",
    0xB5: b"\x20",
    0xB6: b"\x03",
    0xD9: b"\x01\x02\x03\x04\x05\x06",
    0xE2: b"\x10\x11\x12\x13",
    0xE7: b"\x10\x20",
    0xF4: b"\x01",
    # audio / misc
    0xEB: b"\x20\xFF",
    0x29: b"\x85",
    0x82: b"\x44",
    0xC8: b"\xC2",
}


class EditorBoundaryContractTests(unittest.TestCase):
    def test_every_custom_editor_fixture_matches_pc_decoder_width(self):
        for opcode, arguments in CUSTOM_EDITOR_FIXTURES.items():
            with self.subTest(opcode=f"0x{opcode:02X}"):
                command = {
                    "opcode": opcode,
                    "argumentsHex": arguments.hex(" ").upper(),
                    "argumentBytes": len(arguments),
                }
                schema = editor_schema(command)
                self.assertIsNotNone(schema, f"fixture has no editor for 0x{opcode:02X}")
                self.assertTrue(schema["fixedWidth"])
                spec, error = command_spec(bytes((opcode,)) + arguments, 0)
                self.assertIsNone(error)
                self.assertIsNotNone(spec)
                self.assertEqual(
                    spec.argument_bytes,
                    len(arguments),
                    f"editor/parser width mismatch for 0x{opcode:02X}",
                )

    def test_dynamic_and_unresolved_opcodes_have_no_named_editor(self):
        fixtures = {
            0x2E: b"\x40\x01\x02\x03\x04",
            0x4E: b"\x00\x20\x02\x00",
            0x88: b"\x80\x11",
            0xEC: b"\x88",
            0xF1: b"\x21\x80",
            0xFF: b"\x42",
        }
        for opcode, arguments in fixtures.items():
            with self.subTest(opcode=f"0x{opcode:02X}"):
                command = {
                    "opcode": opcode,
                    "argumentsHex": arguments.hex(" ").upper(),
                    "argumentBytes": len(arguments),
                }
                self.assertIsNone(editor_schema(command))


if __name__ == "__main__":
    unittest.main()
