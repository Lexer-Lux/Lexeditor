from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.call_ops import CALL_OPCODES, call_semantics
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


class CallOpTests(unittest.TestCase):
    def test_all_call_opcodes_have_named_schemas(self):
        for opcode in sorted(CALL_OPCODES):
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, b"\x08\xB3"))
                self.assertIsNotNone(schema)
                self.assertTrue(schema["fixedWidth"])
                self.assertEqual(schema["values"]["functionId"], 3)
                self.assertEqual(schema["values"]["priority"], 11)

    def test_object_call_decodes_doubled_target_and_mode(self):
        cmd = command(0x03, b"\x08\xB3")
        schema = editor_schema(cmd)
        self.assertEqual(schema["values"], {"objectId": 4, "functionId": 3, "priority": 11})
        semantic = call_semantics(cmd)
        self.assertEqual(semantic["summary"], "Call object 4 · function 3 · priority 11 · sync")
        self.assertEqual(semantic["mode"], "sync")

    def test_pc_call_uses_same_structural_doubled_target_without_invented_range(self):
        cmd = command(0x07, b"\x0C\x21")
        schema = editor_schema(cmd)
        self.assertEqual(schema["values"], {"playerId": 6, "functionId": 1, "priority": 2})
        self.assertEqual(schema["fields"][0]["max"], 127)
        self.assertEqual(call_semantics(cmd)["summary"], "Call PC 6 · function 1 · priority 2 · halt")

    def test_opcode_fixes_continue_sync_halt_mode(self):
        expected = {
            0x02: "continue", 0x03: "sync", 0x04: "halt",
            0x05: "continue", 0x06: "sync", 0x07: "halt",
        }
        for opcode, mode in expected.items():
            with self.subTest(opcode=opcode):
                self.assertEqual(call_semantics(command(opcode, b"\x02\x00"))["mode"], mode)

    def test_partial_function_write_preserves_target_and_priority(self):
        original = event(bytes((0x04, 0x08, 0xB3, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"functionId": 9})
        self.assertEqual(store.overlay[34:36], bytes((0x08, 0xB9)))
        self.assertEqual(len(store.overlay), len(original))

    def test_target_write_reencodes_doubled_byte(self):
        original = event(bytes((0x05, 0x04, 0x12, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"playerId": 7, "priority": 15})
        self.assertEqual(store.overlay[34:36], bytes((0x0E, 0xF2)))

    def test_odd_stored_target_is_read_only_and_ranges_fail_closed(self):
        self.assertIsNone(editor_schema(command(0x02, b"\x05\x10")))

        original = event(bytes((0x02, 0x04, 0x10, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Function ID must be between 0 and 15"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"functionId": 16})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "Priority must be between 0 and 15"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"priority": 16})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "Object ID must be between 0 and 127"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"objectId": 128})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
