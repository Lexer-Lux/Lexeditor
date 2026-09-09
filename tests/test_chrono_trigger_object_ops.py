from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.object_ops import OBJECT_OPCODES, object_semantics


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


def command(opcode: int, argument: int) -> dict:
    return {"opcode": opcode, "argumentsHex": f"{argument:02X}", "argumentBytes": 1}


class ObjectOpTests(unittest.TestCase):
    def test_all_selected_object_ops_decode_doubled_target(self):
        self.assertEqual(OBJECT_OPCODES, frozenset({0x0A, 0x7C, 0x7D}))
        for opcode in sorted(OBJECT_OPCODES):
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, 0x08))
                self.assertEqual(schema["values"], {"objectId": 4})
                self.assertEqual(schema["fields"][0]["max"], 127)

    def test_semantics_match_constructor_operations(self):
        self.assertEqual(object_semantics(command(0x0A, 0x08))["summary"], "Remove object 4")
        self.assertEqual(object_semantics(command(0x7C, 0x08))["summary"], "Turn drawing on for object 4")
        self.assertEqual(object_semantics(command(0x7D, 0x08))["summary"], "Turn drawing off for object 4")

    def test_write_reencodes_object_id_times_two_without_resizing(self):
        original = event(bytes((0x7C, 0x08, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"objectId": 11})
        self.assertEqual(store.overlay[34], 22)
        self.assertEqual(len(store.overlay), len(original))

    def test_odd_stored_target_and_out_of_range_logical_target_fail_closed(self):
        self.assertIsNone(editor_schema(command(0x0A, 0x09)))

        original = event(bytes((0x0A, 0x08, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Object ID must be between 0 and 127"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"objectId": 128})
        self.assertIsNone(store.overlay)

    def test_processing_neighbors_are_not_assumed_to_use_same_target_encoding(self):
        self.assertIsNone(editor_schema(command(0x0B, 0x08)))
        self.assertIsNone(editor_schema(command(0x0C, 0x08)))


if __name__ == "__main__":
    unittest.main()
