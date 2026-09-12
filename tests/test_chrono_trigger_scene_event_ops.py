from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.scene_event_ops import SCENE_EVENT_OPCODES, scene_event_semantics


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


class SceneEventOpTests(unittest.TestCase):
    def test_selected_opcodes_have_named_schemas(self):
        fixtures = {
            0xD9: b"\x01\x02\x03\x04\x05\x06",
            0xE2: b"\x10\x11\x12\x13",
            0xE7: b"\x10\x20",
            0xF4: b"\x01",
        }
        self.assertEqual(set(fixtures), set(SCENE_EVENT_OPCODES))
        for opcode, args in fixtures.items():
            with self.subTest(opcode=opcode):
                self.assertIsNotNone(editor_schema(command(opcode, args)))

    def test_party_move_exposes_all_six_literal_coordinate_bytes(self):
        cmd = command(0xD9, b"\x01\x02\x03\x04\x05\x06")
        self.assertEqual(editor_schema(cmd)["values"], {
            "pc1X": 1, "pc1Y": 2, "pc2X": 3, "pc2Y": 4, "pc3X": 5, "pc3Y": 6,
        })
        summary = scene_event_semantics(cmd)["summary"]
        self.assertIn("coordinate bytes", summary)
        self.assertNotIn("tile", summary.casefold())
        self.assertNotIn("pixel", summary.casefold())

    def test_change_location_from_memory_decodes_four_script_addresses(self):
        cmd = command(0xE2, b"\x10\x11\x12\x13")
        values = editor_schema(cmd)["values"]
        self.assertEqual(values, {
            "locationAddress": 0x7F0220,
            "xAddress": 0x7F0222,
            "yAddress": 0x7F0224,
            "facingAddress": 0x7F0226,
        })
        summary = scene_event_semantics(cmd)["summary"]
        self.assertIn("location 0x7F0220", summary)
        self.assertIn("X 0x7F0222", summary)
        self.assertIn("Y 0x7F0224", summary)
        self.assertIn("facing 0x7F0226", summary)

    def test_change_location_from_memory_partial_write_uses_even_local_encoding(self):
        original = event(bytes((0xE2, 0x10, 0x11, 0x12, 0x13, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {
            "locationAddress": 0x7F0240,
            "facingAddress": 0x7F0250,
        })
        self.assertEqual(store.overlay[34:38], bytes((0x20, 0x11, 0x12, 0x28)))
        self.assertEqual(len(store.overlay), len(original))

    def test_change_location_from_memory_rejects_odd_or_unrepresentable_address(self):
        original = event(bytes((0xE2, 0x10, 0x11, 0x12, 0x13, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "even script-memory address"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"xAddress": 0x7F0201})
        self.assertIsNone(store.overlay)

        with self.assertRaisesRegex(ValueError, "between"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"xAddress": 0x7F0400})
        self.assertIsNone(store.overlay)

    def test_scroll_coordinates_stay_literal_and_partial_write_preserves_y(self):
        cmd = command(0xE7, b"\x10\x20")
        self.assertEqual(scene_event_semantics(cmd)["summary"], "Scroll screen · coordinate bytes (16, 32)")

        original = event(bytes((0xE7, 0x10, 0x20, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"x": 0x33})
        self.assertEqual(store.overlay[34:36], bytes((0x33, 0x20)))
        self.assertEqual(len(store.overlay), len(original))

    def test_party_partial_write_preserves_other_members(self):
        original = event(bytes((0xD9, 1, 2, 3, 4, 5, 6, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"pc2X": 0x44, "pc3Y": 0x66})
        self.assertEqual(store.overlay[34:40], bytes((1, 2, 0x44, 4, 5, 0x66)))
        self.assertEqual(len(store.overlay), len(original))

    def test_shake_screen_is_boolean_only_for_canonical_zero_one_bytes(self):
        off = editor_schema(command(0xF4, b"\x00"))
        on = editor_schema(command(0xF4, b"\x01"))
        self.assertEqual(off["values"], {"enabled": False})
        self.assertEqual(on["values"], {"enabled": True})
        self.assertEqual(scene_event_semantics(command(0xF4, b"\x01"))["summary"], "Screen shake on")
        self.assertIsNone(editor_schema(command(0xF4, b"\x02")))

        original = event(bytes((0xF4, 0x00, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"enabled": True})
        self.assertEqual(store.overlay[34], 1)

    def test_unknown_copy_scroll_layer_commands_remain_unregistered(self):
        self.assertIsNone(editor_schema(command(0xE4, bytes(7))))
        self.assertIsNone(editor_schema(command(0xE5, bytes(7))))
        self.assertIsNone(editor_schema(command(0xE6, bytes(4))))


if __name__ == "__main__":
    unittest.main()
