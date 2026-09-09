from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.field_editors import (
    decorate_event_editors,
    editor_schema,
    editor_values,
    save_event_fields,
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


def _event(bytecode: bytes) -> bytes:
    data = bytearray(32)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 32)
    data.extend(bytecode)
    return bytes([1]) + bytes(data)


def _command(opcode: int, arguments: bytes) -> dict:
    return {
        "opcode": opcode,
        "argumentsHex": arguments.hex(" ").upper(),
        "argumentBytes": len(arguments),
    }


class FieldEditorSchemaTests(unittest.TestCase):
    def test_load_enemy_schema_exposes_named_values(self):
        command = _command(0x83, bytes((0x34, 0x12, 0x85)))
        schema = editor_schema(command)
        self.assertEqual(schema["values"], {"enemyId": 0x1234, "slot": 5, "static": True})
        self.assertEqual([field["key"] for field in schema["fields"]], ["enemyId", "slot", "static"])

    def test_location_schema_uses_pc_separate_facing_byte(self):
        command = _command(0xE1, bytes((0x23, 0x01, 0x02, 0x11, 0x22)))
        self.assertEqual(editor_values(command), {
            "sceneId": 0x0123, "facing": 2, "tileX": 0x11, "tileY": 0x22,
        })

    def test_battle_schema_exposes_all_two_byte_flags(self):
        command = _command(0xD8, bytes((0x90, 0xA0)))
        values = editor_schema(command)["values"]
        self.assertTrue(values["staticEnemies"])
        self.assertTrue(values["noRun"])
        self.assertTrue(values["noGameOver"])
        self.assertTrue(values["regroup"])
        self.assertFalse(values["mapMusic"])

    def test_unsupported_command_has_no_named_editor(self):
        self.assertIsNone(editor_schema(_command(0x92, b"\x01\x02")))

    def test_decorator_only_attaches_supported_editors(self):
        payload = {"objects": [{"functions": [{"commands": [
            _command(0x83, b"\x01\x00\x00"),
            _command(0x92, b"\x01\x02"),
        ]}]}]}
        decorate_event_editors(payload)
        commands = payload["objects"][0]["functions"][0]["commands"]
        self.assertIn("editor", commands[0])
        self.assertNotIn("editor", commands[1])


class FieldEditorWriteTests(unittest.TestCase):
    def test_partial_load_enemy_patch_preserves_static_flag(self):
        original = _event(bytes((0x83, 0x34, 0x12, 0x85, 0x00)))
        store = FakeStore(original)
        result = save_event_fields(
            store, 1, 0, 0, 0, sha256(original), {"enemyId": 0x5678, "slot": 3}
        )
        self.assertEqual(store.overlay[34:37], bytes((0x78, 0x56, 0x83)))
        saved = result["objects"][0]["functions"][0]["commands"][0]
        self.assertEqual(saved["argumentsHex"], "78 56 83")

    def test_location_patch_preserves_unspecified_coordinates(self):
        original = _event(bytes((0xE1, 0x23, 0x01, 0x02, 0x11, 0x22, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"sceneId": 0x345, "facing": 3})
        self.assertEqual(store.overlay[34:39], bytes((0x45, 0x03, 0x03, 0x11, 0x22)))

    def test_battle_flag_patch_preserves_every_unspecified_bit(self):
        original = _event(bytes((0xD8, 0x49, 0x15, 0x00)))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"noRun": True, "mapMusic": True, "unknown201": False},
        )
        # Byte 1: original 0x49 plus noRun. Byte 2: original 0x15 clears 0x01,
        # then sets mapMusic, preserving 0x04 and 0x10.
        self.assertEqual(store.overlay[34:36], bytes((0xC9, 0x54)))

    def test_gold_and_jump_are_little_endian_and_fixed_width(self):
        original = _event(bytes((0xCC, 0x34, 0x12, 0x05, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"gold": 5000, "jumpOffset": 9})
        self.assertEqual(store.overlay[34:37], bytes((0x88, 0x13, 0x09)))
        self.assertEqual(len(store.overlay), len(original))

    def test_textbox_patch_only_changes_string_index(self):
        original = _event(bytes((0xC3, 0x34, 0x12, 0x0B, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"stringIndex": 0x2222})
        self.assertEqual(store.overlay[34:37], bytes((0x22, 0x22, 0x0B)))

    def test_unknown_field_is_rejected_without_writing(self):
        original = _event(bytes((0xEA, 0x05, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Unknown fields"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"songName": "Battle"})
        self.assertIsNone(store.overlay)

    def test_out_of_range_named_value_is_rejected(self):
        original = _event(bytes((0xE1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Facing must be between 0 and 3"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"facing": 9})
        self.assertIsNone(store.overlay)

    def test_unsupported_opcode_remains_read_only(self):
        original = _event(bytes((0x92, 0x01, 0x02, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "no named fixed-width editor"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"direction": 3})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
