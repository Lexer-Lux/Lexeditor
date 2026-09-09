from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.pc_extended_ops import PC_EXTENDED_OPCODES, pc_extended_semantics


EVENT_PATH = "Game/field/atel/Atel_0001.dat"


class FakeStore:
    def __init__(self, raw: bytes):
        self.base = raw
        self.overlay: bytes | None = None
        self.archive = SimpleNamespace(entries=[SimpleNamespace(path=EVENT_PATH)])

    def read(self, path: str, source: str = "mine"):
        if path != EVENT_PATH:
            raise KeyError(path)
        if source != "vanilla" and self.overlay is not None:
            return self.overlay, "project"
        return self.base, "archive"

    def write(self, path: str, data: bytes):
        if path != EVENT_PATH:
            raise KeyError(path)
        self.overlay = bytes(data)
        return SimpleNamespace()

    def localization_files(self):
        return []


def event(bytecode: bytes) -> bytes:
    data = bytearray(32)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 32)
    data.extend(bytecode)
    return bytes([1]) + bytes(data)


def command(opcode: int, arguments: bytes) -> dict:
    return {"opcode": opcode, "argumentsHex": arguments.hex(" ").upper(), "argumentBytes": len(arguments)}


class PcExtendedOpTests(unittest.TestCase):
    def test_all_selected_pc_only_opcodes_have_named_schemas(self):
        fixtures = {
            0x3A: b"\x7F\x10",
            0x3D: b"\x11\x12",
            0x3E: b"\x13\x14",
            0x45: b"\x02\x15",
            0x46: b"\x03\x16",
            0x70: b"\x04\x17",
            0x74: b"\x18\x19",
            0x78: b"\x1A\x1B",
        }
        self.assertEqual(set(fixtures), set(PC_EXTENDED_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])
                self.assertTrue(schema["fields"])

    def test_operand_order_matches_pc_factories(self):
        self.assertEqual(editor_schema(command(0x3A, b"\x7F\x10"))["values"],
                         {"value": 0x7F, "extendedSlot": 0x10})
        self.assertEqual(editor_schema(command(0x3D, b"\x11\x12"))["values"],
                         {"localSlot": 0x11, "extendedSlot": 0x12})
        self.assertEqual(editor_schema(command(0x3E, b"\x13\x14"))["values"],
                         {"extendedSlot": 0x13, "localSlot": 0x14})
        self.assertEqual(editor_schema(command(0x45, b"\x02\x15"))["values"],
                         {"bit": 2, "extendedSlot": 0x15})
        self.assertEqual(editor_schema(command(0x70, b"\x04\x17"))["values"],
                         {"partySlot": 4, "localSlot": 0x17})
        self.assertEqual(editor_schema(command(0x74, b"\x18\x19"))["values"],
                         {"extendedSlot": 0x18, "localSlot": 0x19})
        self.assertEqual(editor_schema(command(0x78, b"\x1A\x1B"))["values"],
                         {"localSlot": 0x1A, "extendedSlot": 0x1B})

    def test_semantics_explicitly_keep_slots_raw_and_pc_only(self):
        semantic = pc_extended_semantics(command(0x3D, b"\x11\x12"))
        self.assertTrue(semantic["pcOnly"])
        self.assertTrue(semantic["rawSlots"])
        self.assertEqual(semantic["widthBytes"], 1)
        self.assertIn("raw slots", semantic["summary"])

        wide = pc_extended_semantics(command(0x74, b"\x18\x19"))
        self.assertEqual(wide["widthBytes"], 2)
        self.assertIn("Copy16", wide["summary"])

    def test_partial_write_preserves_other_slot_and_size(self):
        original = event(bytes((0x3D, 0x11, 0x12, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"extendedSlot": 0x44})
        self.assertEqual(store.overlay[34:36], bytes((0x11, 0x44)))
        self.assertEqual(len(store.overlay), len(original))

    def test_values_are_raw_u8_and_out_of_range_fails_closed(self):
        original = event(bytes((0x3A, 0x01, 0x02, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Immediate value must be between 0 and 255"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"value": 256})
        self.assertIsNone(store.overlay)

    def test_pc_extended_comparison_stays_unregistered(self):
        # 0x6E has a known four-byte PC width/factory, but its public
        # extended-memory comparison semantics/address model are intentionally
        # not promoted into a named Lexeditor writer yet.
        self.assertIsNone(editor_schema(command(0x6E, b"\x01\x02\x03\x04")))


if __name__ == "__main__":
    unittest.main()
