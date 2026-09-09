from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.movement_ops import MOVEMENT_OPCODES, movement_semantics


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


class MovementOpTests(unittest.TestCase):
    def test_selected_opcodes_have_named_schemas(self):
        fixtures = {
            0x8F: b"\x02",
            0x94: b"\x20",
            0x95: b"\x03",
            0x96: b"\x10\x20",
            0x97: b"\x10\x11",
            0x98: b"\x20\x08",
            0x99: b"\x04\x08",
            0x9A: b"\x10\x20\x08",
            0x9D: b"\x14\x15",
            0xA0: b"\x30\x40",
            0xA1: b"\x12\x13",
            0xB5: b"\x21",
            0xB6: b"\x05",
        }
        self.assertEqual(set(fixtures), set(MOVEMENT_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])

    def test_follow_targets_keep_object_and_pc_ranges_distinct(self):
        self.assertEqual(editor_schema(command(0x8F, b"\x02"))["values"], {"playerId": 2})
        self.assertEqual(editor_schema(command(0x94, b"\x20"))["values"], {"objectId": 0x20})
        self.assertEqual(editor_schema(command(0x95, b"\x03"))["values"], {"playerId": 3})
        self.assertEqual(movement_semantics(command(0xB5, b"\x21"))["summary"], "Loop follow object 33")
        self.assertEqual(movement_semantics(command(0xB6, b"\x05"))["summary"], "Loop follow PC 5")

    def test_direct_coordinate_bytes_do_not_claim_units(self):
        normal = movement_semantics(command(0x96, b"\x10\x20"))
        animated = movement_semantics(command(0xA0, b"\x30\x40"))
        self.assertEqual(normal["summary"], "NPC move · coordinate bytes (16, 32)")
        self.assertEqual(animated["summary"], "Animated move · coordinate bytes (48, 64)")
        self.assertNotIn("tile", normal["summary"].casefold())
        self.assertNotIn("pixel", normal["summary"].casefold())

    def test_memory_coordinate_and_vector_sources_decode_script_addresses(self):
        normal = editor_schema(command(0x97, b"\x10\x11"))["values"]
        animated = editor_schema(command(0xA1, b"\x12\x13"))["values"]
        vector = editor_schema(command(0x9D, b"\x14\x15"))["values"]
        self.assertEqual(normal, {"xAddress": 0x7F0220, "yAddress": 0x7F0222})
        self.assertEqual(animated, {"xAddress": 0x7F0224, "yAddress": 0x7F0226})
        self.assertEqual(vector, {
            "directionAddress": 0x7F0228,
            "magnitudeAddress": 0x7F022A,
        })
        self.assertEqual(
            movement_semantics(command(0x9D, b"\x14\x15"))["summary"],
            "Vector move from direction 0x7F0228 · magnitude 0x7F022A",
        )

    def test_move_toward_semantics_preserve_target_kind(self):
        self.assertEqual(movement_semantics(command(0x98, b"\x20\x08"))["summary"],
                         "Move toward object 32 · distance 8")
        self.assertEqual(movement_semantics(command(0x99, b"\x04\x08"))["summary"],
                         "Move toward PC 4 · distance 8")
        self.assertEqual(movement_semantics(command(0x9A, b"\x10\x20\x08"))["summary"],
                         "Move toward coordinate bytes (16, 32) · distance 8")

    def test_partial_memory_coordinate_write_preserves_other_source_and_size(self):
        original = event(bytes((0xA1, 0x10, 0x11, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"xAddress": 0x7F0240})
        self.assertEqual(store.overlay[34:36], bytes((0x20, 0x11)))
        self.assertEqual(len(store.overlay), len(original))

        vector_original = event(bytes((0x9D, 0x14, 0x15, 0x00)))
        vector_store = FakeStore(vector_original)
        save_event_fields(vector_store, 1, 0, 0, 0, sha256(vector_original),
                          {"magnitudeAddress": 0x7F0244})
        self.assertEqual(vector_store.overlay[34:36], bytes((0x14, 0x22)))
        self.assertEqual(len(vector_store.overlay), len(vector_original))

    def test_pc_range_and_even_memory_address_fail_closed(self):
        self.assertIsNone(editor_schema(command(0x95, b"\x00")))
        self.assertIsNone(editor_schema(command(0xB6, b"\x07")))

        pc_original = event(bytes((0x99, 0x03, 0x08, 0x00)))
        pc_store = FakeStore(pc_original)
        with self.assertRaisesRegex(ValueError, "Player character must be between 1 and 6"):
            save_event_fields(pc_store, 1, 0, 0, 0, sha256(pc_original), {"playerId": 7})
        self.assertIsNone(pc_store.overlay)

        mem_original = event(bytes((0x97, 0x10, 0x11, 0x00)))
        mem_store = FakeStore(mem_original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(mem_store, 1, 0, 0, 0, sha256(mem_original), {"xAddress": 0x7F0201})
        self.assertIsNone(mem_store.overlay)

        vector_original = event(bytes((0x9D, 0x10, 0x11, 0x00)))
        vector_store = FakeStore(vector_original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(vector_store, 1, 0, 0, 0, sha256(vector_original),
                              {"directionAddress": 0x7F0201})
        self.assertIsNone(vector_store.overlay)

    def test_malformed_or_ambiguous_neighbors_remain_unregistered(self):
        for opcode, args in (
            (0x92, b"\x01\x02"),
            (0x9C, b"\x01\x02"),
            (0x9E, b"\x01"),
            (0x9F, b"\x01"),
            (0x8D, b"\x00\x00\x00\x00"),
            (0x8E, b"\x80"),
        ):
            with self.subTest(opcode=opcode):
                self.assertIsNone(editor_schema(command(opcode, args)))


if __name__ == "__main__":
    unittest.main()
