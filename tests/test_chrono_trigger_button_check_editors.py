from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.field_editors import BUTTON_JUMP_OPCODES, editor_schema, save_event_fields
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


def command(opcode: int, jump: int = 1) -> dict:
    return {
        "opcode": opcode,
        "argumentsHex": f"{jump:02X}",
        "argumentBytes": 1,
    }


class ButtonCheckEditorTests(unittest.TestCase):
    def test_every_proven_button_check_exposes_only_jump_offset(self):
        for opcode in sorted(BUTTON_JUMP_OPCODES):
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, 5))
                self.assertEqual(schema["values"], {"jumpOffset": 5})
                self.assertEqual([field["key"] for field in schema["fields"]], ["jumpOffset"])

    def test_semantics_identify_check_and_proven_failure_branch(self):
        current = command_semantics(command(0x34, 3), {})
        self.assertEqual(current["check"], "A button · current")
        self.assertEqual(current["jumpOffset"], 3)
        self.assertTrue(current["jumpOnFailure"])
        self.assertEqual(current["summary"], "A button · current check · failure → jump +3")

        since = command_semantics(command(0x3C, 7), {})
        self.assertEqual(since["check"], "Confirm action · since last")
        self.assertTrue(since["jumpOnFailure"])
        self.assertEqual(since["summary"], "Confirm action · since last check · failure → jump +7")

    def test_jump_only_editor_retargets_to_valid_boundary(self):
        # One-byte argument means the check at 32 has jump origin 33. Pause
        # commands begin at 34 and 36, then Return at 38.
        original = event(bytes((
            0x34, 0x01,
            0xAD, 0x01,
            0xAD, 0x02,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 3})
        self.assertEqual(store.overlay[34], 0x03)
        self.assertEqual(len(store.overlay), len(original))

        rejected = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(rejected, 1, 0, 0, 0, sha256(original), {"jumpOffset": 2})
        self.assertIsNone(rejected.overlay)

    def test_opcode_is_never_part_of_button_editor_values(self):
        schema = editor_schema(command(0x3F, 1))
        self.assertNotIn("button", schema["values"])
        self.assertNotIn("mode", schema["values"])
        self.assertNotIn("opcode", schema["values"])


if __name__ == "__main__":
    unittest.main()
