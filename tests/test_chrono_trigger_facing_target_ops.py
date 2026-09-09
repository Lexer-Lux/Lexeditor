from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.facing_target_ops import (
    FACING_TARGET_OPCODES,
    facing_target_semantics,
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


class FacingTargetOpTests(unittest.TestCase):
    def test_selected_opcodes_have_named_schemas(self):
        fixtures = {
            0x23: b"\x06\x10",
            0x24: b"\x04\x11",
            0xA8: b"\x08",
            0xA9: b"\x0A",
        }
        self.assertEqual(set(fixtures), set(FACING_TARGET_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, args))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])

    def test_get_facing_decodes_doubled_target_and_script_memory_destination(self):
        obj = command(0x23, b"\x06\x10")
        self.assertEqual(editor_schema(obj)["values"], {
            "targetId": 3,
            "storeAddress": 0x7F0220,
        })
        self.assertEqual(
            facing_target_semantics(obj)["summary"],
            "Get object 3 facing → 0x7F0220",
        )

        pc = command(0x24, b"\x04\x11")
        self.assertEqual(editor_schema(pc)["values"], {
            "targetId": 2,
            "storeAddress": 0x7F0222,
        })
        self.assertEqual(facing_target_semantics(pc)["targetType"], "pc")

    def test_face_target_decodes_object_vs_pc_from_opcode(self):
        obj = command(0xA8, b"\x08")
        pc = command(0xA9, b"\x0A")
        self.assertEqual(editor_schema(obj)["values"], {"targetId": 4})
        self.assertEqual(editor_schema(pc)["values"], {"targetId": 5})
        self.assertEqual(facing_target_semantics(obj)["summary"], "Face object 4")
        self.assertEqual(facing_target_semantics(pc)["summary"], "Face PC 5")

    def test_get_facing_partial_writes_preserve_other_operand(self):
        original = event(bytes((0x23, 0x06, 0x10, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"targetId": 7})
        self.assertEqual(store.overlay[34:36], bytes((0x0E, 0x10)))
        self.assertEqual(len(store.overlay), len(original))

        second = FakeStore(original)
        save_event_fields(second, 1, 0, 0, 0, sha256(original), {"storeAddress": 0x7F0240})
        self.assertEqual(second.overlay[34:36], bytes((0x06, 0x20)))
        self.assertEqual(len(second.overlay), len(original))

    def test_face_pc_write_uses_exact_doubled_target_byte(self):
        original = event(bytes((0xA9, 0x04, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"targetId": 12})
        self.assertEqual(store.overlay[34], 24)
        self.assertEqual(len(store.overlay), len(original))

    def test_odd_stored_targets_remain_read_only(self):
        for opcode, args in (
            (0x23, b"\x05\x10"),
            (0x24, b"\x03\x10"),
            (0xA8, b"\x07"),
            (0xA9, b"\x09"),
        ):
            with self.subTest(opcode=opcode):
                self.assertIsNone(editor_schema(command(opcode, args)))
                self.assertIsNone(facing_target_semantics(command(opcode, args)))

    def test_target_and_address_ranges_fail_closed(self):
        original = event(bytes((0x23, 0x06, 0x10, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "between 0 and 127"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"targetId": 128})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"storeAddress": 0x7F0201})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "between"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"storeAddress": 0x7F0400})
        self.assertIsNone(store.overlay)

    def test_unknown_fields_are_rejected(self):
        original = event(bytes((0xA8, 0x04, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Unknown fields"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"facing": 2})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
