from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.comparisons import COMPARISON_OPCODES, comparison_semantics
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
    def test_selected_comparison_opcodes_are_registered(self):
        self.assertEqual(COMPARISON_OPCODES, frozenset({0x12, 0x13, 0x14, 0x15, 0x16}))

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

    def test_bank7f_comparison_decodes_low_and_high_address_pages(self):
        low = command(0x16, bytes((0x44, 0x7F, 2, 3)))
        low_schema = editor_schema(low)
        self.assertEqual(low_schema["values"], {
            "memoryAddress": 0x7F0044,
            "value": 0x7F,
            "operation": 2,
            "jumpOffset": 3,
        })
        self.assertEqual(low_schema["fields"][0]["min"], 0x7F0000)
        self.assertEqual(low_schema["fields"][0]["max"], 0x7F01FF)
        self.assertEqual(
            comparison_semantics(low)["summary"],
            "8-bit 0x7F0044 greater than 127 · false → jump +3",
        )
        self.assertTrue(comparison_semantics(low)["bank7F"])

        high = command(0x16, bytes((0x55, 0x22, 0x85, 1)))
        self.assertEqual(editor_schema(high)["values"], {
            "memoryAddress": 0x7F0155,
            "value": 0x22,
            "operation": 5,
            "jumpOffset": 1,
        })
        self.assertEqual(comparison_semantics(high)["operationName"], "less or equal")

    def test_invalid_comparator_and_noncanonical_bank7f_operator_bits_fail_closed(self):
        invalid = command(0x12, bytes((0x02, 0x10, 8, 1)))
        self.assertIsNone(editor_schema(invalid))
        self.assertIsNone(comparison_semantics(invalid))

        for packed_operation in (0x08, 0x78, 0x88, 0xFF):
            with self.subTest(packed_operation=packed_operation):
                cmd = command(0x16, bytes((0x02, 0x10, packed_operation, 1)))
                self.assertIsNone(editor_schema(cmd))
                self.assertIsNone(comparison_semantics(cmd))

        # Page bit 7 plus a valid operation remains canonical.
        self.assertIsNotNone(editor_schema(command(0x16, bytes((0x02, 0x10, 0x80, 1)))))
        self.assertIsNotNone(editor_schema(command(0x16, bytes((0x02, 0x10, 0x87, 1)))))

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

    def test_bank7f_write_reencodes_page_and_operation_without_resizing(self):
        original = event(bytes((
            0x16, 0x44, 0x10, 2, 1,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"memoryAddress": 0x7F01AA, "operation": 7},
        )
        self.assertEqual(store.overlay[34:38], bytes((0xAA, 0x10, 0x87, 1)))
        self.assertEqual(len(store.overlay), len(original))

        high_original = event(bytes((
            0x16, 0x55, 0x22, 0x85, 1,
            0xAD, 0x01,
            0x00,
        )))
        partial = FakeStore(high_original)
        save_event_fields(
            partial, 1, 0, 0, 0, sha256(high_original), {"operation": 1}
        )
        self.assertEqual(partial.overlay[34:38], bytes((0x55, 0x22, 0x81, 1)))

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

    def test_bank7f_jump_retargeting_uses_same_boundary_validator(self):
        original = event(bytes((
            0x16, 0x44, 0x10, 0, 1,
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

    def test_script_and_bank7f_addresses_and_value_ranges_are_validated(self):
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

        bank_original = event(bytes((
            0x16, 0x02, 0x10, 0, 1,
            0xAD, 0x01,
            0x00,
        )))
        bank = FakeStore(bank_original)
        with self.assertRaisesRegex(ValueError, "Bank-7F address must be between"):
            save_event_fields(
                bank, 1, 0, 0, 0, sha256(bank_original), {"memoryAddress": 0x7F0200}
            )
        self.assertIsNone(bank.overlay)

        with self.assertRaisesRegex(ValueError, "Comparison value must be between 0 and 255"):
            save_event_fields(
                bank, 1, 0, 0, 0, sha256(bank_original), {"value": 256}
            )
        self.assertIsNone(bank.overlay)


if __name__ == "__main__":
    unittest.main()
