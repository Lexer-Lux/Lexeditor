from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.audio_ops import audio_semantics
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
    return {"opcode": opcode, "argumentsHex": arguments.hex(" ").upper(), "argumentBytes": len(arguments)}


class AudioOpTests(unittest.TestCase):
    def test_song_volume_schema_matches_duration_volume_order(self):
        schema = editor_schema(command(0xEB, b"\x20\xFF"))
        self.assertEqual(schema["values"], {"duration": 0x20, "volume": 0xFF})
        self.assertEqual([field["key"] for field in schema["fields"]], ["duration", "volume"])
        self.assertIn("0xFF normal", schema["fields"][1]["label"])

    def test_song_volume_semantics_marks_normal_volume(self):
        semantic = audio_semantics(command(0xEB, b"\x20\xFF"))
        self.assertEqual(semantic["summary"], "Song volume 255 · change duration 32")
        self.assertTrue(semantic["normalVolume"])
        self.assertFalse(audio_semantics(command(0xEB, b"\x20\x80"))["normalVolume"])

    def test_partial_song_volume_write_preserves_duration_and_size(self):
        original = event(bytes((0xEB, 0x20, 0x80, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"volume": 0xFF})
        self.assertEqual(store.overlay[34:36], bytes((0x20, 0xFF)))
        self.assertEqual(len(store.overlay), len(original))

    def test_out_of_range_audio_values_fail_closed(self):
        original = event(bytes((0xEB, 0x20, 0x80, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Song volume must be between 0 and 255"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"volume": 256})
        self.assertIsNone(store.overlay)

    def test_all_purpose_sound_remains_unregistered_due_length_conflict(self):
        self.assertIsNone(editor_schema(command(0xEC, b"\x14\x05\x00")))
        self.assertIsNone(editor_schema(command(0xEC, b"\x88")))


if __name__ == "__main__":
    unittest.main()
