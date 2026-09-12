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


class MemoryFacingEventEditorTests(unittest.TestCase):
    def test_single_slot_outputs_expose_real_script_addresses(self):
        labels = {
            0x20: "PC1 ID",
            0x55: "Storyline counter",
            0x7F: "Random value",
        }
        for opcode, label in labels.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, b"\x10"))
                self.assertEqual(schema["values"], {"storeAddress": 0x7F0220})
                semantic = command_semantics(command(opcode, b"\x10"), {})
                self.assertEqual(semantic["storeAddress"], 0x7F0220)
                self.assertIn(label, semantic["summary"])
                self.assertIn("0x7F0220", semantic["summary"])

    def test_position_from_memory_exposes_both_sources(self):
        schema = editor_schema(command(0x8C, b"\x10\x20"))
        self.assertEqual(schema["values"], {
            "xAddress": 0x7F0220,
            "yAddress": 0x7F0240,
        })
        semantic = command_semantics(command(0x8C, b"\x10\x20"), {})
        self.assertEqual(semantic["xAddress"], 0x7F0220)
        self.assertEqual(semantic["yAddress"], 0x7F0240)

    def test_direct_facing_is_constrained_to_documented_values(self):
        names = ("up", "down", "left", "right")
        for value, name in enumerate(names):
            with self.subTest(value=value):
                schema = editor_schema(command(0xA6, bytes((value,))))
                self.assertEqual(schema["values"], {"facing": value})
                semantic = command_semantics(command(0xA6, bytes((value,))), {})
                self.assertEqual(semantic["facing"], value)
                self.assertEqual(semantic["facingName"], name)
        self.assertIsNone(editor_schema(command(0xA6, b"\x04")))
        self.assertIsNone(command_semantics(command(0xA6, b"\x04"), {}))

    def test_facing_from_memory_uses_script_address_model(self):
        schema = editor_schema(command(0xA7, b"\x7F"))
        self.assertEqual(schema["values"], {"facingAddress": 0x7F02FE})
        semantic = command_semantics(command(0xA7, b"\x7F"), {})
        self.assertEqual(semantic["facingAddress"], 0x7F02FE)
        self.assertIn("0x7F02FE", semantic["summary"])

    def test_memory_and_facing_writes_preserve_command_width(self):
        cases = [
            (bytes((0x20, 0x01, 0x00)), {"storeAddress": 0x7F0230}, bytes((0x18,))),
            (bytes((0x55, 0x02, 0x00)), {"storeAddress": 0x7F0240}, bytes((0x20,))),
            (bytes((0x7F, 0x03, 0x00)), {"storeAddress": 0x7F0250}, bytes((0x28,))),
            (bytes((0x8C, 0x02, 0x03, 0x00)), {"xAddress": 0x7F0230}, bytes((0x18, 0x03))),
            (bytes((0xA6, 0x00, 0x00)), {"facing": 3}, bytes((0x03,))),
            (bytes((0xA7, 0x02, 0x00)), {"facingAddress": 0x7F0230}, bytes((0x18,))),
        ]
        for bytecode, values, expected_args in cases:
            with self.subTest(opcode=bytecode[0]):
                original = event(bytecode)
                store = FakeStore(original)
                save_event_fields(store, 1, 0, 0, 0, sha256(original), values)
                self.assertEqual(store.overlay[34:34 + len(expected_args)], expected_args)
                self.assertEqual(len(store.overlay), len(original))

    def test_memory_sources_reject_odd_addresses_without_writing(self):
        for opcode, key in ((0x20, "storeAddress"), (0x8C, "xAddress"), (0xA7, "facingAddress")):
            with self.subTest(opcode=opcode):
                args = b"\x02\x03" if opcode == 0x8C else b"\x02"
                original = event(bytes((opcode,)) + args + b"\x00")
                store = FakeStore(original)
                with self.assertRaisesRegex(ValueError, "even script-memory address"):
                    save_event_fields(store, 1, 0, 0, 0, sha256(original), {key: 0x7F0201})
                self.assertIsNone(store.overlay)

    def test_facing_write_rejects_out_of_range_values(self):
        original = event(bytes((0xA6, 0x01, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Facing must be between 0 and 3"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"facing": 4})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
