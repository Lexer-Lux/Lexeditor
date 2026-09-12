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


def command(arguments: bytes) -> dict:
    return {
        "opcode": 0x18,
        "argumentsHex": arguments.hex(" ").upper(),
        "argumentBytes": len(arguments),
    }


class StorylineCheckEditorTests(unittest.TestCase):
    def test_schema_and_semantics_use_threshold_then_forward_jump(self):
        schema = editor_schema(command(bytes((0x20, 0x05))))
        self.assertEqual(schema["values"], {"storylineValue": 0x20, "jumpOffset": 5})
        self.assertEqual([field["key"] for field in schema["fields"]], [
            "storylineValue", "jumpOffset",
        ])
        semantic = command_semantics(command(bytes((0x20, 0x05))), {})
        self.assertEqual(semantic["storylineValue"], 0x20)
        self.assertEqual(semantic["jumpOffset"], 5)
        self.assertEqual(semantic["summary"], "Storyline < 32 → jump +5")

    def test_threshold_only_edit_preserves_existing_jump_byte(self):
        original = event(bytes((
            0x18, 0x20, 0x01,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original), {"storylineValue": 0x30}
        )
        self.assertEqual(store.overlay[34:36], bytes((0x30, 0x01)))
        self.assertEqual(len(store.overlay), len(original))

    def test_jump_edit_can_retarget_only_to_a_decoded_boundary(self):
        original = event(bytes((
            0x18, 0x20, 0x01,
            0xAD, 0x01,
            0xAD, 0x02,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original), {"jumpOffset": 3}
        )
        self.assertEqual(store.overlay[34:36], bytes((0x20, 0x03)))

        rejected = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "not a decoded command boundary"):
            save_event_fields(
                rejected, 1, 0, 0, 0, sha256(original), {"jumpOffset": 2}
            )
        self.assertIsNone(rejected.overlay)

    def test_legacy_invalid_jump_does_not_block_threshold_only_edit(self):
        original = event(bytes((
            0x18, 0x20, 0x02,
            0xAD, 0x01,
            0x00,
        )))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original), {"storylineValue": 0x44}
        )
        self.assertEqual(store.overlay[34:36], bytes((0x44, 0x02)))


if __name__ == "__main__":
    unittest.main()
