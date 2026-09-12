from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.bit_ops import BIT_OPCODES, bit_semantics
from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields


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


class BitOpTests(unittest.TestCase):
    def test_selected_opcodes_have_named_schemas(self):
        fixtures = {
            0x63: b"\x03\x10",
            0x64: b"\x04\x11",
            0x65: b"\x03\x12",
            0x66: b"\x86\x44",
            0x69: b"\xA5\x12",
            0x6B: b"\x5A\x13",
            0x6F: b"\x03\x14",
        }
        self.assertEqual(set(fixtures), set(BIT_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])

    def test_single_bit_set_reset_decode_bit_index_and_address(self):
        set_bit = command(0x63, b"\x03\x10")
        reset_bit = command(0x64, b"\x07\x18")
        self.assertEqual(editor_schema(set_bit)["values"], {
            "memoryAddress": 0x7F0220, "bitIndex": 3,
        })
        self.assertEqual(editor_schema(reset_bit)["values"], {
            "memoryAddress": 0x7F0230, "bitIndex": 7,
        })
        self.assertEqual(bit_semantics(set_bit)["summary"], "Set bit 3 in 0x7F0220")
        self.assertEqual(bit_semantics(reset_bit)["summary"], "Reset bit 7 in 0x7F0230")

    def test_bank7f_single_bits_decode_page_bit_and_low_address_byte(self):
        low = command(0x65, b"\x03\x44")
        high = command(0x66, b"\x86\x55")
        self.assertEqual(editor_schema(low)["values"], {
            "memoryAddress": 0x7F0044, "bitIndex": 3,
        })
        self.assertEqual(editor_schema(high)["values"], {
            "memoryAddress": 0x7F0155, "bitIndex": 6,
        })
        self.assertEqual(bit_semantics(low)["summary"], "Set bit 3 in 0x7F0044")
        self.assertEqual(bit_semantics(high)["summary"], "Reset bit 6 in 0x7F0155")

    def test_bank7f_write_reencodes_page_and_bit_index_without_resizing(self):
        original = event(bytes((0x65, 0x02, 0x44, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {
            "memoryAddress": 0x7F01AA,
            "bitIndex": 7,
        })
        self.assertEqual(store.overlay[34:36], bytes((0x87, 0xAA)))
        self.assertEqual(len(store.overlay), len(original))

        partial = FakeStore(original)
        save_event_fields(partial, 1, 0, 0, 0, sha256(original), {"bitIndex": 5})
        self.assertEqual(partial.overlay[34:36], bytes((0x05, 0x44)))

    def test_bank7f_noncanonical_flag_bits_and_out_of_range_address_fail_closed(self):
        for first in (0x08, 0x78, 0x88, 0xFF):
            with self.subTest(first=first):
                self.assertIsNone(editor_schema(command(0x65, bytes((first, 0x10)))))

        original = event(bytes((0x66, 0x80, 0x00, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Bank-7F address must be between"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"memoryAddress": 0x7F0200})
        self.assertIsNone(store.overlay)

    def test_mask_and_shift_semantics_stay_literal(self):
        self.assertEqual(bit_semantics(command(0x69, b"\xA5\x10"))["summary"],
                         "Set bits 0xA5 in 0x7F0220")
        self.assertEqual(bit_semantics(command(0x6B, b"\x5A\x11"))["summary"],
                         "Toggle bits 0x5A in 0x7F0222")
        self.assertEqual(bit_semantics(command(0x6F, b"\x03\x12"))["summary"],
                         "Shift 0x7F0224 right by 3 bit(s)")

    def test_mask_write_preserves_size_and_uses_even_script_address(self):
        original = event(bytes((0x6B, 0x55, 0x10, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {
            "bitMask": 0xAA, "memoryAddress": 0x7F0240,
        })
        self.assertEqual(store.overlay[34:36], bytes((0xAA, 0x20)))
        self.assertEqual(len(store.overlay), len(original))

    def test_single_bit_partial_write_preserves_address(self):
        original = event(bytes((0x63, 0x01, 0x18, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"bitIndex": 6})
        self.assertEqual(store.overlay[34:36], bytes((0x06, 0x18)))

    def test_odd_address_and_out_of_range_bit_shift_fail_closed(self):
        original = event(bytes((0x6F, 0x02, 0x10, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"memoryAddress": 0x7F0201})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "Right shift bits must be between 0 and 7"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"shiftBits": 8})
        self.assertIsNone(store.overlay)

        self.assertIsNone(editor_schema(command(0x63, b"\x08\x10")))
        self.assertIsNone(editor_schema(command(0x6F, b"\xFF\x10")))

    def test_ambiguous_reset_mask_neighbor_stays_unregistered(self):
        self.assertIsNone(editor_schema(command(0x67, b"\x01\x10")))


if __name__ == "__main__":
    unittest.main()
