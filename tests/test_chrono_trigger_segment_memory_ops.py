from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.segment_memory_ops import (
    SEGMENT_MEMORY_OPCODES,
    segment_memory_semantics,
)


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


class SegmentMemoryOpTests(unittest.TestCase):
    def test_all_pc_segment_opcodes_have_named_schemas(self):
        fixtures = {
            0x48: b"\x34\x12\x10",
            0x49: b"\x78\x56\x11",
            0x4A: b"\xBC\x9A\x7F",
            0x4B: b"\x34\x12\x78\x56",
            0x4C: b"\x44\x33\x12",
            0x4D: b"\x66\x55\x13",
        }
        self.assertEqual(set(fixtures), set(SEGMENT_MEMORY_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])
                self.assertEqual(schema["fields"][0]["max"], 0xFFFF)
                self.assertIn("raw", schema["fields"][0]["label"].lower())

    def test_copy_from_segment_keeps_local_destination_raw(self):
        for opcode, width in ((0x48, 1), (0x49, 2)):
            with self.subTest(opcode=opcode):
                cmd = command(opcode, b"\x34\x12\x10")
                schema = editor_schema(cmd)
                self.assertEqual(schema["values"], {"segment": 0x1234, "localSlot": 0x10})
                semantic = segment_memory_semantics(cmd)
                self.assertEqual(semantic["widthBytes"], width)
                self.assertTrue(semantic["pcSegmentRaw"])
                self.assertFalse(semantic["fullAddressKnown"])
                self.assertIn("raw segment 0x1234", semantic["summary"])
                self.assertIn("local slot 16", semantic["summary"])

    def test_immediate_to_segment_uses_little_endian_value_width(self):
        byte_cmd = command(0x4A, b"\x34\x12\x7F")
        word_cmd = command(0x4B, b"\x34\x12\x78\x56")
        self.assertEqual(editor_schema(byte_cmd)["values"], {"segment": 0x1234, "value": 0x7F})
        self.assertEqual(editor_schema(word_cmd)["values"], {"segment": 0x1234, "value": 0x5678})
        self.assertEqual(segment_memory_semantics(byte_cmd)["widthBytes"], 1)
        self.assertEqual(segment_memory_semantics(word_cmd)["widthBytes"], 2)

    def test_copy_to_segment_keeps_local_source_raw(self):
        byte_cmd = command(0x4C, b"\x34\x12\x20")
        word_cmd = command(0x4D, b"\x34\x12\x21")
        self.assertEqual(editor_schema(byte_cmd)["values"], {"segment": 0x1234, "localSlot": 0x20})
        self.assertEqual(editor_schema(word_cmd)["values"], {"segment": 0x1234, "localSlot": 0x21})
        self.assertIn("local slot 32 → raw segment 0x1234", segment_memory_semantics(byte_cmd)["summary"])
        self.assertIn("local slot 33 → raw segment 0x1234", segment_memory_semantics(word_cmd)["summary"])

    def test_u16_segment_and_value_write_little_endian_without_resizing(self):
        original = event(bytes((0x4B, 0x34, 0x12, 0x78, 0x56, 0x00)))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"segment": 0xBEEF, "value": 0xCAFE},
        )
        self.assertEqual(store.overlay[34:38], bytes((0xEF, 0xBE, 0xFE, 0xCA)))
        self.assertEqual(len(store.overlay), len(original))

    def test_partial_raw_slot_write_preserves_segment(self):
        original = event(bytes((0x48, 0x34, 0x12, 0x10, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"localSlot": 0xFE})
        self.assertEqual(store.overlay[34:37], bytes((0x34, 0x12, 0xFE)))
        self.assertEqual(len(store.overlay), len(original))

    def test_raw_field_ranges_and_argument_widths_fail_closed(self):
        self.assertIsNone(editor_schema(command(0x48, b"\x34\x12")))
        self.assertIsNone(editor_schema(command(0x4B, b"\x34\x12\x78")))

        original = event(bytes((0x4A, 0x34, 0x12, 0x01, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "PC segment must be between 0 and 65535"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"segment": 0x10000})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "8-bit value must be between 0 and 255"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"value": 256})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
