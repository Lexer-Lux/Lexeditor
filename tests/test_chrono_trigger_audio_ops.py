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

    def test_known_ec_subcommands_have_read_only_semantics_but_no_editor(self):
        fixtures = {
            b"\x14\x05": "EC/14 Interrupt and play song · songId 5",
            b"\x19\x07": "EC/19 Play sound · soundId 7",
            b"\x82\x03\x7F": "EC/82 Sound volume · duration 3 · volume 127",
            b"\x83\x11\x22": "EC/83 Unknown sound operation · param1 17 · param2 34",
            b"\x85\x04\x60": "EC/85 Song speed · duration 4 · speed 96",
            b"\x86\x05\x70": "EC/86 Song speed · duration 5 · speed 112",
            b"\x88": "EC/88 Change song state",
            b"\xF0": "EC/F0 Song to silence",
            b"\xF2": "EC/F2 Sound to silence",
        }
        for arguments, summary in fixtures.items():
            with self.subTest(arguments=arguments):
                cmd = command(0xEC, arguments)
                semantic = audio_semantics(cmd)
                self.assertIsNotNone(semantic)
                self.assertEqual(semantic["summary"], summary)
                self.assertTrue(semantic["readOnly"])
                self.assertEqual(semantic["subcommand"], arguments[0])
                self.assertIsNone(editor_schema(cmd))

    def test_ec_semantics_require_exact_known_subcommand_width(self):
        self.assertIsNone(audio_semantics(command(0xEC, b"\x14")))
        self.assertIsNone(audio_semantics(command(0xEC, b"\x14\x05\x00")))
        self.assertIsNone(audio_semantics(command(0xEC, b"\x99")))

    def test_all_purpose_sound_remains_unregistered_for_writes(self):
        self.assertIsNone(editor_schema(command(0xEC, b"\x14\x05")))
        self.assertIsNone(editor_schema(command(0xEC, b"\x88")))
        self.assertIsNone(editor_schema(command(0xEC, b"\x82\x03\x7F")))


if __name__ == "__main__":
    unittest.main()
