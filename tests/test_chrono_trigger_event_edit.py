from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.event_edit import save_event_arguments


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


def _event(bytecode: bytes) -> bytes:
    # One object, all 16 functions alias the same function beginning directly
    # after the 32-byte pointer table in raw[1:].
    data = bytearray(32)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 32)
    data.extend(bytecode)
    return bytes([1]) + bytes(data)


class EventEditTests(unittest.TestCase):
    def test_edits_fixed_width_pc_load_enemy_arguments_without_moving_bytes(self):
        # PC 0x83: enemy u16 + slot/flags u8, followed by Return.
        original = _event(bytes((0x83, 0x34, 0x12, 0x80, 0x00)))
        store = FakeStore(original)
        result = save_event_arguments(
            store, 1, 0, 0, 0, sha256(original), "78 56 01"
        )
        self.assertIsNotNone(store.overlay)
        self.assertEqual(len(store.overlay), len(original))
        self.assertEqual(store.overlay[33], 0x83)
        self.assertEqual(store.overlay[34:37], bytes((0x78, 0x56, 0x01)))
        saved = result["savedCommand"]
        self.assertEqual(saved["opcode"], 0x83)
        self.assertEqual(saved["argumentsHex"], "78 56 01")
        command = result["objects"][0]["functions"][0]["commands"][0]
        self.assertEqual(command["size"], 4)
        self.assertEqual(command["argumentsHex"], "78 56 01")

    def test_rejects_stale_sha_without_writing(self):
        original = _event(bytes((0x83, 0x34, 0x12, 0x80, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(RuntimeError, "changed since"):
            save_event_arguments(store, 1, 0, 0, 0, "0" * 64, "78 56 01")
        self.assertIsNone(store.overlay)

    def test_rejects_wrong_argument_length(self):
        original = _event(bytes((0x83, 0x34, 0x12, 0x80, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "exactly 3"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), "01 02")
        self.assertIsNone(store.overlay)

    def test_variable_width_color_addition_remains_read_only(self):
        # F1 with nonzero color has two argument bytes in the decoded command.
        original = _event(bytes((0xF1, 0x21, 0x80, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "variable or unresolved"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), "22 80")
        self.assertIsNone(store.overlay)

    def test_zero_argument_command_has_nothing_to_edit(self):
        original = _event(bytes((0x00,)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "no argument"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), "")


if __name__ == "__main__":
    unittest.main()
