from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.comparisons import comparison_semantics
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


class MemoryComparisonEditorTests(unittest.TestCase):
    def test_u8_immediate_comparison_schema_and_semantics(self):
        cmd = command(0x12, bytes((0x10, 0x7F, 2, 3)))
        schema = editor_schema(cmd)
        self.assertEqual(schema["values"], {
            "memoryAddress": 0x7F0220,
            "value": 0x7F,
            "operation": 2,
            "jumpOffset": 3,
        })
        self.assertEqual([field["key"] for field in schema["fields"]], [
            "memoryAddress", "value", "operation", "jumpOffset",
        ])
        semantic = comparison_semantics(cmd)
        self.assertEqual(semantic["widthBytes"], 1)
        self.assertEqual(semantic["operationName"], "greater than")
        self.assertTrue(semantic["jumpOnFalse"])
        self.assertEqual(semantic["summary"],
                         "8-bit 0x7F0220 greater than 127 · false → jump +3")

    def test_u16_immediate_comparison_is_little_endian(self):
        cmd = command(0x13, bytes((0x18, 0x34, 0x12, 3, 1)))
        schema = editor_schema(cmd)
        self.assertEqual(schema["values"], {
            "memoryAddress": 0x7F0230,
            "value": 0x1234,
            "operation": 3,
            "jumpOffset": 1,
        })
        self.assertEqual(schema["fields"][1]["max"], 0xFFFF)
        semantic = comparison_semantics(cmd)
        self.assertEqual(semantic["widthBytes"], 2)
        self.assertEqual(semantic["value"], 0x1234)
        self.assertEqual(semantic["operationName"], "less than")

    def test_mem_to_mem_opcodes_preserve_width_in_semantics_not_editable_values(self):
        for opcode, width in ((0x14, 1), (0x15, 2)):
            with self.subTest(opcode=opcode):
                cmd = command(opcode, bytes((0x02, 0x03, 4, 1)))
                schema = editor_schema(cmd)
                self.assertEqual(schema["values"], {
                    "leftAddress": 0x7F0204,
                    "rightAddress": 0x7F0206,
                    "operation": 4,
                    "jumpOffset": 1,
                })
                semantic = comparison_semantics(cmd)
                self.assertEqual(semantic["widthBytes"], width)
                self.assertEqual(semantic["operationName"], "greater or equal")
                self.assertTrue(semantic["jumpOnFalse"])

    def test_invalid_comparator_and_0x16_fail_closed(self):
        invalid = command(0x12, bytes((0x02, 0x10, 8, 1)))
        self.assertIsNone(editor_schema(invalid))
        self.assertIsNone(comparison_semantics(invalid))
        self.assertIsNone(editor_schema(command(0x16, bytes((0x02, 0x10, 0, 1)))))

    def test_u16_partial_write_preserves_operation_and_jump(self):
        original = event(bytes((
            0x13, 0x10, 0x34, 0x12, 5, 1,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"memoryAddress": 0x7F0240, "value": 0xBEEF},
        )
        self.assertEqual(store.overlay[34:39], bytes((0x20, 0xEF, 0xBE, 5, 1)))
        self.assertEqual(len(store.overlay), len(original))

    def test_mem_to_mem_partial_write_preserves_other_operand(self):
        original = event(bytes((
            0x15, 0x02, 0x03, 1, 1,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"leftAddress": 0x7F0220, "operation": 7},
        )
        self.assertEqual(store.overlay[34:38], bytes((0x10, 0x03, 7, 1)))
        self.assertEqual(len(store.overlay), len(original))

    def test_changed_jump_must_land_on_decoded_boundary(self):
        original = event(bytes((
            0x12, 0x02, 0x10, 0, 1,
            0xAD, 0x01,
            0xAD, 0x02,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 3})
        self.assertEqual(store.overlay[37], 3)

        rejected = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(rejected, 1, 0, 0, 0, sha256(original), {"jumpOffset": 2})
        self.assertIsNone(rejected.overlay)

    def test_script_addresses_and_operation_range_are_validated(self):
        original = event(bytes((
            0x12, 0x02, 0x10, 0, 1,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(
                store, 1, 0, 0, 0, sha256(original), {"memoryAddress": 0x7F0201}
            )
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "Comparison operation must be between 0 and 7"):
            save_event_fields(
                store, 1, 0, 0, 0, sha256(original), {"operation": 8}
            )
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
