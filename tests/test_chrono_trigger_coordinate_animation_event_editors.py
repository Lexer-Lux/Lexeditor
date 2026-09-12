from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.field_editors import editor_schema, save_event_fields
from games.chrono_trigger.field_semantics import command_semantics


EVENT_PATH = "Game/field/atel/Atel_0001.dat"
LABELS = {"playerNames": ["Crono", "Marle", "Lucca", "Robo"]}


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


class CoordinateAnimationEventEditorTests(unittest.TestCase):
    def test_object_coordinate_read_decodes_doubled_target_and_addresses(self):
        schema = editor_schema(command(0x21, b"\x06\x10\x20"))
        self.assertEqual(schema["values"], {
            "targetId": 3,
            "xStoreAddress": 0x7F0220,
            "yStoreAddress": 0x7F0240,
        })
        semantic = command_semantics(command(0x21, b"\x06\x10\x20"), LABELS)
        self.assertEqual(semantic["targetId"], 3)
        self.assertIn("Object 3", semantic["summary"])
        self.assertIn("0x7F0220", semantic["summary"])
        self.assertIn("0x7F0240", semantic["summary"])

    def test_pc_coordinate_read_uses_player_label(self):
        semantic = command_semantics(command(0x22, b"\x02\x01\x02"), LABELS)
        self.assertEqual(semantic["targetId"], 1)
        self.assertIn("Marle (1)", semantic["summary"])
        schema = editor_schema(command(0x22, b"\x02\x01\x02"))
        self.assertEqual(schema["values"]["targetId"], 1)

    def test_odd_encoded_coordinate_target_stays_read_only(self):
        self.assertIsNone(editor_schema(command(0x21, b"\x03\x10\x20")))
        self.assertIsNone(command_semantics(command(0x21, b"\x03\x10\x20"), LABELS))
        self.assertIsNone(editor_schema(command(0x22, b"\x05\x10\x20")))
        self.assertIsNone(command_semantics(command(0x22, b"\x05\x10\x20"), LABELS))

    def test_animation_and_pause_commands_are_named(self):
        expected_modes = {
            0xAA: "Loop animation",
            0xAB: "Animation",
            0xAC: "Static animation",
        }
        for opcode, name in expected_modes.items():
            with self.subTest(opcode=opcode):
                schema = editor_schema(command(opcode, b"\x2A"))
                self.assertEqual(schema["values"], {"animationId": 0x2A})
                semantic = command_semantics(command(opcode, b"\x2A"), LABELS)
                self.assertEqual(semantic["animationId"], 0x2A)
                self.assertIn(name, semantic["summary"])

        pause = editor_schema(command(0xAD, b"\x05"))
        self.assertEqual(pause["values"], {"pauseTicks": 5})
        pause_semantic = command_semantics(command(0xAD, b"\x05"), LABELS)
        self.assertEqual(pause_semantic["pauseTicks"], 5)
        self.assertIn("5/16 second", pause_semantic["summary"])

        counted = editor_schema(command(0xB7, b"\x11\x04"))
        self.assertEqual(counted["values"], {"animationId": 0x11, "loopCount": 4})
        counted_semantic = command_semantics(command(0xB7, b"\x11\x04"), LABELS)
        self.assertEqual(counted_semantic["animationId"], 0x11)
        self.assertEqual(counted_semantic["loopCount"], 4)

    def test_coordinate_read_write_preserves_width_and_unspecified_bytes(self):
        original = event(bytes((0x21, 0x06, 0x10, 0x20, 0x00)))
        store = FakeStore(original)
        save_event_fields(
            store, 1, 0, 0, 0, sha256(original),
            {"targetId": 4, "xStoreAddress": 0x7F0230},
        )
        self.assertEqual(store.overlay[34:37], bytes((0x08, 0x18, 0x20)))
        self.assertEqual(len(store.overlay), len(original))

    def test_animation_and_pause_writes_preserve_width(self):
        cases = [
            (bytes((0xAA, 0x01, 0x00)), {"animationId": 0x20}, bytes((0x20,))),
            (bytes((0xAB, 0x02, 0x00)), {"animationId": 0x21}, bytes((0x21,))),
            (bytes((0xAC, 0x03, 0x00)), {"animationId": 0x22}, bytes((0x22,))),
            (bytes((0xAD, 0x04, 0x00)), {"pauseTicks": 0x30}, bytes((0x30,))),
            (bytes((0xB7, 0x05, 0x06, 0x00)), {"loopCount": 9}, bytes((0x05, 0x09))),
        ]
        for bytecode, values, expected_args in cases:
            with self.subTest(opcode=bytecode[0]):
                original = event(bytecode)
                store = FakeStore(original)
                save_event_fields(store, 1, 0, 0, 0, sha256(original), values)
                self.assertEqual(store.overlay[34:34 + len(expected_args)], expected_args)
                self.assertEqual(len(store.overlay), len(original))

    def test_coordinate_read_rejects_unrepresentable_target_id(self):
        original = event(bytes((0x21, 0x02, 0x10, 0x20, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Object ID must be between 0 and 127"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"targetId": 128})
        self.assertIsNone(store.overlay)

    def test_coordinate_read_rejects_odd_script_address(self):
        original = event(bytes((0x22, 0x02, 0x10, 0x20, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"yStoreAddress": 0x7F0201})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
