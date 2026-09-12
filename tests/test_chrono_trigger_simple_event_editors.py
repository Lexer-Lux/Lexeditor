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


class SimpleEventEditorTests(unittest.TestCase):
    def test_message_table_editor_is_one_byte(self):
        schema = editor_schema(command(0xB8, b"\x07"))
        self.assertEqual(schema["values"], {"messageTable": 7})
        self.assertEqual(schema["fields"][0]["max"], 0xFF)
        semantic = command_semantics(command(0xB8, b"\x07"), {})
        self.assertEqual(semantic, {"summary": "Message table 7", "messageTable": 7})

    def test_explore_mode_editor_accepts_only_documented_boolean_bytes(self):
        self.assertEqual(editor_schema(command(0xE3, b"\x01"))["values"], {"enabled": True})
        self.assertEqual(editor_schema(command(0xE3, b"\x00"))["values"], {"enabled": False})
        self.assertIsNone(editor_schema(command(0xE3, b"\x02")))
        self.assertEqual(command_semantics(command(0xE3, b"\x01"), {})["summary"], "Explore mode on")
        self.assertIsNone(command_semantics(command(0xE3, b"\x02"), {}))

    def test_darken_duration_stays_raw(self):
        schema = editor_schema(command(0xF0, b"\x20"))
        self.assertEqual(schema["values"], {"duration": 0x20})
        self.assertIn("raw", schema["fields"][0]["label"].casefold())
        semantic = command_semantics(command(0xF0, b"\x20"), {})
        self.assertEqual(semantic["duration"], 0x20)
        self.assertIn("raw", semantic["summary"])

    def test_writes_preserve_one_byte_command_width(self):
        cases = [
            (0xB8, 0x07, {"messageTable": 9}, 9),
            (0xE3, 0x01, {"enabled": False}, 0),
            (0xF0, 0x20, {"duration": 0x44}, 0x44),
        ]
        for opcode, original_arg, values, expected_arg in cases:
            with self.subTest(opcode=opcode):
                original = event(bytes((opcode, original_arg, 0x00)))
                store = FakeStore(original)
                save_event_fields(store, 1, 0, 0, 0, sha256(original), values)
                self.assertEqual(store.overlay[34], expected_arg)
                self.assertEqual(len(store.overlay), len(original))


if __name__ == "__main__":
    unittest.main()
