from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.misc_ops import MISC_OPCODES, misc_semantics


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


class MiscOpTests(unittest.TestCase):
    def test_selected_misc_commands_have_named_schemas(self):
        self.assertEqual(MISC_OPCODES, frozenset({0x29, 0x82, 0xC8}))
        self.assertEqual(editor_schema(command(0x29, 0x85))["values"], {"asciiIndex": 5})
        self.assertEqual(editor_schema(command(0x82, 0x44))["values"], {"npcId": 0x44})
        self.assertEqual(editor_schema(command(0xC8, 0xC2))["values"], {"dialogId": 0xC2})

    def test_ascii_index_requires_and_preserves_encoded_high_bit(self):
        self.assertEqual(misc_semantics(command(0x29, 0x85))["summary"], "Load ASCII text index 5")
        self.assertEqual(misc_semantics(command(0x29, 0x85))["storedByte"], 0x85)
        self.assertIsNone(editor_schema(command(0x29, 0x05)))

        original = event(bytes((0x29, 0x85, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"asciiIndex": 0x2A})
        self.assertEqual(store.overlay[34], 0xAA)
        self.assertEqual(len(store.overlay), len(original))

    def test_ascii_index_range_fails_closed(self):
        original = event(bytes((0x29, 0x80, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "ASCII text index must be between 0 and 127"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"asciiIndex": 128})
        self.assertIsNone(store.overlay)

    def test_npc_and_special_dialog_are_raw_one_byte_operands(self):
        self.assertEqual(misc_semantics(command(0x82, 0x44))["summary"], "Load NPC 68")
        self.assertEqual(misc_semantics(command(0xC8, 0xC2))["summary"], "Special dialog 0xC2 (raw)")

        npc_original = event(bytes((0x82, 0x11, 0x00)))
        npc_store = FakeStore(npc_original)
        save_event_fields(npc_store, 1, 0, 0, 0, sha256(npc_original), {"npcId": 0xFE})
        self.assertEqual(npc_store.overlay[34], 0xFE)

        dialog_original = event(bytes((0xC8, 0x01, 0x00)))
        dialog_store = FakeStore(dialog_original)
        save_event_fields(dialog_store, 1, 0, 0, 0, sha256(dialog_original), {"dialogId": 0xC5})
        self.assertEqual(dialog_store.overlay[34], 0xC5)


if __name__ == "__main__":
    unittest.main()
