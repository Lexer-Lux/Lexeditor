from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.memory_ops import MEMORY_OPCODES, memory_semantics


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
    return {
        "opcode": opcode,
        "argumentsHex": arguments.hex(" ").upper(),
        "argumentBytes": len(arguments),
    }


class MemoryOpTests(unittest.TestCase):
    def test_all_selected_opcodes_have_named_schemas(self):
        fixtures = {
            0x19: b"\x10",
            0x1A: b"\x05\x01",
            0x1C: b"\x44",
            0x4F: b"\x7F\x10",
            0x50: b"\x34\x12\x10",
            0x51: b"\x10\x11",
            0x52: b"\x10\x11",
            0x5B: b"\x04\x10",
            0x5D: b"\x10\x11",
            0x5E: b"\x10\x11",
            0x5F: b"\x04\x10",
            0x71: b"\x10",
            0x72: b"\x10",
            0x73: b"\x10",
        }
        self.assertEqual(set(fixtures), set(MEMORY_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])
                self.assertTrue(schema["fields"])
                self.assertTrue(schema["values"])

    def test_result_store_and_result_mismatch_jump(self):
        store_result = command(0x19, b"\x18")
        self.assertEqual(editor_schema(store_result)["values"], {"storeAddress": 0x7F0230})
        self.assertEqual(memory_semantics(store_result)["summary"], "Result → 0x7F0230")

        bank_result = command(0x1C, b"\x44")
        bank_schema = editor_schema(bank_result)
        self.assertEqual(bank_schema["values"], {"storeAddress": 0x7F0044})
        self.assertEqual(bank_schema["fields"][0]["min"], 0x7F0000)
        self.assertEqual(bank_schema["fields"][0]["max"], 0x7F00FF)
        self.assertEqual(memory_semantics(bank_result)["summary"], "Result → 0x7F0044 (bank 7F)")
        self.assertEqual(memory_semantics(bank_result)["addressMode"], "bank7f-byte-offset")

        check = command(0x1A, b"\x05\x03")
        self.assertEqual(editor_schema(check)["values"], {"resultValue": 5, "jumpOffset": 3})
        semantic = memory_semantics(check)
        self.assertTrue(semantic["jumpOnMismatch"])
        self.assertEqual(semantic["summary"], "Result must equal 5 · mismatch → jump +3")

    def test_bank7f_result_write_uses_literal_one_byte_offset(self):
        original = event(bytes((0x1C, 0x44, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"storeAddress": 0x7F00AA})
        self.assertEqual(store.overlay[33:35], bytes((0x1C, 0xAA)))
        self.assertEqual(len(store.overlay), len(original))

    def test_bank7f_result_range_is_narrowed_to_encodable_byte(self):
        original = event(bytes((0x1C, 0x44, 0x00)))
        for address in (0x7EFFFF, 0x7F0100, 0x7F0200):
            with self.subTest(address=address):
                store = FakeStore(original)
                with self.assertRaisesRegex(ValueError, "Bank-7F result address must be between"):
                    save_event_fields(store, 1, 0, 0, 0, sha256(original), {"storeAddress": address})
                self.assertIsNone(store.overlay)

    def test_immediate_assignments_use_u8_and_little_endian_u16(self):
        one = command(0x4F, b"\x7F\x10")
        self.assertEqual(editor_schema(one)["values"], {"value": 0x7F, "storeAddress": 0x7F0220})
        self.assertEqual(memory_semantics(one)["summary"], "Store 8-bit 127 → 0x7F0220")

        two = command(0x50, b"\x34\x12\x18")
        self.assertEqual(editor_schema(two)["values"], {"value": 0x1234, "storeAddress": 0x7F0230})
        self.assertEqual(editor_schema(two)["fields"][0]["max"], 0xFFFF)
        self.assertEqual(memory_semantics(two)["summary"], "Store 16-bit 4660 → 0x7F0230")

    def test_copy_and_arithmetic_semantics_include_width_and_direction(self):
        self.assertEqual(memory_semantics(command(0x51, b"\x10\x11"))["summary"],
                         "Copy 8-bit 0x7F0220 → 0x7F0222")
        self.assertEqual(memory_semantics(command(0x52, b"\x10\x11"))["summary"],
                         "Copy 16-bit 0x7F0220 → 0x7F0222")
        self.assertEqual(memory_semantics(command(0x5B, b"\x04\x10"))["summary"],
                         "Add 4 to 8-bit 0x7F0220")
        self.assertEqual(memory_semantics(command(0x5D, b"\x10\x11"))["summary"],
                         "Add 8-bit 0x7F0220 into 0x7F0222")
        self.assertEqual(memory_semantics(command(0x5E, b"\x10\x11"))["summary"],
                         "Add 16-bit 0x7F0220 into 0x7F0222")
        self.assertEqual(memory_semantics(command(0x5F, b"\x04\x10"))["summary"],
                         "Subtract 4 from 8-bit 0x7F0220")
        self.assertEqual(memory_semantics(command(0x71, b"\x10"))["summary"],
                         "Increment 8-bit 0x7F0220")
        self.assertEqual(memory_semantics(command(0x72, b"\x10"))["summary"],
                         "Increment 16-bit 0x7F0220")
        self.assertEqual(memory_semantics(command(0x73, b"\x10"))["summary"],
                         "Decrement 8-bit 0x7F0220")

    def test_u16_assignment_partial_write_preserves_destination(self):
        original = event(bytes((0x50, 0x34, 0x12, 0x10, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"value": 0xBEEF})
        self.assertEqual(store.overlay[34:37], bytes((0xEF, 0xBE, 0x10)))
        self.assertEqual(len(store.overlay), len(original))

    def test_memory_copy_partial_write_preserves_other_address(self):
        original = event(bytes((0x52, 0x10, 0x11, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"sourceAddress": 0x7F0240})
        self.assertEqual(store.overlay[34:36], bytes((0x20, 0x11)))
        self.assertEqual(len(store.overlay), len(original))

    def test_result_jump_retargeting_uses_generic_boundary_validator(self):
        # 0x1A starts at 32, size 3, jump origin 34. Pauses begin at 35 and 37.
        original = event(bytes((
            0x1A, 0x05, 0x01,
            0xAD, 0x01,
            0xAD, 0x02,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 3})
        self.assertEqual(store.overlay[35], 3)

        rejected = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(rejected, 1, 0, 0, 0, sha256(original), {"jumpOffset": 2})
        self.assertIsNone(rejected.overlay)

    def test_addresses_and_value_ranges_fail_closed(self):
        original = event(bytes((0x4F, 0x01, 0x10, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"storeAddress": 0x7F0201})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "Value must be between 0 and 255"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"value": 256})
        self.assertIsNone(store.overlay)

    def test_ambiguous_neighbors_are_not_registered(self):
        for opcode, args in (
            (0x60, b"\x01\x02"),
            (0x61, b"\x01\x02"),
            (0x75, b"\x01"),
            (0x76, b"\x01"),
            (0x77, b"\x01"),
        ):
            with self.subTest(opcode=opcode):
                self.assertIsNone(editor_schema(command(opcode, args)))


if __name__ == "__main__":
    unittest.main()
