from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.jump_ops import jump_semantics


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


def command(opcode: int, distance: int) -> dict:
    return {"opcode": opcode, "argumentsHex": f"{distance:02X}", "argumentBytes": 1}


class JumpEditorTests(unittest.TestCase):
    def test_forward_and_backward_named_schemas(self):
        forward = editor_schema(command(0x10, 5))
        backward = editor_schema(command(0x11, 7))
        self.assertEqual(forward["values"], {"jumpOffset": 5})
        self.assertEqual(backward["values"], {"jumpOffset": 7})
        self.assertEqual([field["key"] for field in forward["fields"]], ["jumpOffset"])
        self.assertEqual(jump_semantics(command(0x10, 5))["summary"], "Jump forward +5")
        self.assertEqual(jump_semantics(command(0x11, 7))["summary"], "Jump backward -7")

    def test_forward_retarget_accepts_command_boundary_and_function_end(self):
        original = event(bytes((
            0x10, 0x01,
            0xAD, 0x01,
            0xAD, 0x02,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 3})
        self.assertEqual(store.overlay[34], 3)

        end_store = FakeStore(original)
        save_event_fields(end_store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 6})
        self.assertEqual(end_store.overlay[34], 6)

    def test_forward_retarget_rejects_middle_of_command(self):
        original = event(bytes((
            0x10, 0x01,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 2})
        self.assertIsNone(store.overlay)

    def test_backward_retarget_accepts_boundary_and_rejects_split(self):
        original = event(bytes((
            0xAD, 0x01,
            0xAD, 0x02,
            0x11, 0x03,
            0x00,
        )))
        valid = FakeStore(original)
        save_event_fields(valid, 1, 0, 0, 2, sha256(original), {"jumpOffset": 5})
        self.assertEqual(valid.overlay[38], 5)

        invalid = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(invalid, 1, 0, 0, 2, sha256(original), {"jumpOffset": 4})
        self.assertIsNone(invalid.overlay)

    def test_jump_value_range_is_bounded(self):
        original = event(bytes((0x10, 0x01, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "between 0 and 255"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 256})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
