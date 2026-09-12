from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.field_editors import editor_schema, save_event_fields
from games.chrono_trigger.field_semantics import command_semantics


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


def command(opcode: int, args: bytes) -> dict:
    return {"opcode": opcode, "argumentsHex": args.hex(" ").upper(), "argumentBytes": len(args)}


class MovementEventEditorTests(unittest.TestCase):
    def test_script_speed_uses_documented_zero_to_stop_range(self):
        schema = editor_schema(command(0x87, b"\x40"))
        self.assertEqual(schema["values"], {"scriptSpeed": 0x40})
        self.assertEqual(schema["fields"][0]["max"], 0x80)
        self.assertIsNone(editor_schema(command(0x87, b"\x81")))
        self.assertEqual(command_semantics(command(0x87, b"\x80"), {})["scriptSpeed"], 0x80)
        self.assertIsNone(command_semantics(command(0x87, b"\x81"), {}))

    def test_npc_speed_and_memory_source_are_named(self):
        direct = editor_schema(command(0x89, b"\x55"))
        self.assertEqual(direct["values"], {"movementSpeed": 0x55})
        semantic = command_semantics(command(0x89, b"\x55"), {})
        self.assertEqual(semantic["movementSpeed"], 0x55)
        self.assertIn("85", semantic["summary"])

        from_mem = editor_schema(command(0x8A, b"\x10"))
        self.assertEqual(from_mem["values"], {"speedAddress": 0x7F0220})
        semantic = command_semantics(command(0x8A, b"\x10"), {})
        self.assertEqual(semantic["speedAddress"], 0x7F0220)
        self.assertIn("0x7F0220", semantic["summary"])

    def test_tile_position_uses_two_independent_bytes(self):
        schema = editor_schema(command(0x8B, b"\x12\x34"))
        self.assertEqual(schema["values"], {"tileX": 0x12, "tileY": 0x34})
        semantic = command_semantics(command(0x8B, b"\x12\x34"), {})
        self.assertEqual((semantic["tileX"], semantic["tileY"]), (0x12, 0x34))

    def test_movement_writes_preserve_command_width_and_unspecified_bytes(self):
        cases = [
            (bytes((0x87, 0x20, 0x00)), {"scriptSpeed": 0x80}, bytes((0x80,))),
            (bytes((0x89, 0x20, 0x00)), {"movementSpeed": 0x77}, bytes((0x77,))),
            (bytes((0x8A, 0x02, 0x00)), {"speedAddress": 0x7F0230}, bytes((0x18,))),
            (bytes((0x8B, 0x12, 0x34, 0x00)), {"tileX": 0x56}, bytes((0x56, 0x34))),
        ]
        for bytecode, values, expected_args in cases:
            with self.subTest(opcode=bytecode[0]):
                original = event(bytecode)
                store = FakeStore(original)
                save_event_fields(store, 1, 0, 0, 0, sha256(original), values)
                self.assertEqual(store.overlay[34:34 + len(expected_args)], expected_args)
                self.assertEqual(len(store.overlay), len(original))

    def test_speed_memory_source_reuses_even_script_address_validation(self):
        original = event(bytes((0x8A, 0x02, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"speedAddress": 0x7F0201})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
