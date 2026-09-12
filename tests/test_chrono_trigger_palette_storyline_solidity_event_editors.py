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


def command(opcode: int, args: bytes) -> dict:
    return {"opcode": opcode, "argumentsHex": args.hex(" ").upper(), "argumentBytes": len(args)}


class PaletteStorylineSolidityEventEditorTests(unittest.TestCase):
    def test_palette_id_is_named_one_byte_value(self):
        schema = editor_schema(command(0x33, b"\x2A"))
        self.assertEqual(schema["values"], {"paletteId": 0x2A})
        self.assertEqual(schema["fields"][0]["max"], 0xFF)
        semantic = command_semantics(command(0x33, b"\x2A"), {})
        self.assertEqual(semantic, {"summary": "Change palette 42", "paletteId": 0x2A})

    def test_storyline_value_is_named_one_byte_value(self):
        schema = editor_schema(command(0x5A, b"\x80"))
        self.assertEqual(schema["values"], {"storylineValue": 0x80})
        semantic = command_semantics(command(0x5A, b"\x80"), {})
        self.assertEqual(semantic, {"summary": "Set storyline 128", "storylineValue": 0x80})

    def test_solidity_properties_remain_explicitly_raw(self):
        schema = editor_schema(command(0x84, b"\xA5"))
        self.assertEqual(schema["values"], {"solidityProperties": 0xA5})
        self.assertEqual(schema["fields"][0]["label"], "Solidity properties (raw)")
        semantic = command_semantics(command(0x84, b"\xA5"), {})
        self.assertEqual(semantic["solidityProperties"], 0xA5)
        self.assertIn("0xA5 (raw)", semantic["summary"])
        self.assertNotIn("solid", semantic.keys())
        self.assertNotIn("collision", semantic.keys())

    def test_all_three_writes_preserve_one_byte_width(self):
        cases = [
            (0x33, "paletteId", 0x11, 0xCC),
            (0x5A, "storylineValue", 0x22, 0xDD),
            (0x84, "solidityProperties", 0x33, 0xEE),
        ]
        for opcode, key, old_value, new_value in cases:
            with self.subTest(opcode=opcode):
                original = event(bytes((opcode, old_value, 0x00)))
                store = FakeStore(original)
                result = save_event_fields(
                    store, 1, 0, 0, 0, sha256(original), {key: new_value}
                )
                self.assertEqual(store.overlay[34], new_value)
                self.assertEqual(len(store.overlay), len(original))
                saved = result["objects"][0]["functions"][0]["commands"][0]
                self.assertEqual(saved["argumentsHex"], f"{new_value:02X}")

    def test_out_of_range_values_are_rejected_without_writing(self):
        for opcode, key, label in (
            (0x33, "paletteId", "Palette ID"),
            (0x5A, "storylineValue", "Storyline value"),
            (0x84, "solidityProperties", "Solidity properties"),
        ):
            with self.subTest(opcode=opcode):
                original = event(bytes((opcode, 0x00, 0x00)))
                store = FakeStore(original)
                with self.assertRaisesRegex(ValueError, f"{label} must be between 0 and 255"):
                    save_event_fields(store, 1, 0, 0, 0, sha256(original), {key: 256})
                self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
