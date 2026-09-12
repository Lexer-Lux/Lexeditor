from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.property_ops import PROPERTY_OPCODES, property_semantics


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


def command(opcode: int, argument: int) -> dict:
    return {"opcode": opcode, "argumentsHex": f"{argument:02X}", "argumentBytes": 1}


class PropertyOpTests(unittest.TestCase):
    def test_selected_property_commands_expose_only_known_low_bits(self):
        self.assertEqual(PROPERTY_OPCODES, frozenset({0x0D, 0x0E}))
        movement = editor_schema(command(0x0D, 0xA3))
        self.assertEqual(movement["values"], {"throughWalls": True, "throughPCs": True})
        self.assertEqual([field["key"] for field in movement["fields"]], ["throughWalls", "throughPCs"])

        destination = editor_schema(command(0x0E, 0x82))
        self.assertEqual(destination["values"], {"ontoTile": False, "ontoObject": True})
        self.assertEqual([field["key"] for field in destination["fields"]], ["ontoTile", "ontoObject"])

    def test_semantics_report_unknown_bits_as_preserved(self):
        movement = property_semantics(command(0x0D, 0xA1))
        self.assertEqual(movement["unknownBits"], 0xA0)
        self.assertIn("through walls", movement["summary"])
        self.assertIn("unknown bits 0xA0 preserved", movement["summary"])

        destination = property_semantics(command(0x0E, 0xC2))
        self.assertEqual(destination["unknownBits"], 0xC0)
        self.assertIn("onto object", destination["summary"])
        self.assertIn("unknown bits 0xC0 preserved", destination["summary"])

    def test_partial_movement_flag_write_preserves_every_unknown_bit(self):
        original = event(bytes((0x0D, 0xA2, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"throughWalls": True})
        self.assertEqual(store.overlay[34], 0xA3)
        self.assertEqual(len(store.overlay), len(original))

    def test_partial_destination_flag_write_preserves_every_unknown_bit(self):
        original = event(bytes((0x0E, 0xC3, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"ontoObject": False})
        self.assertEqual(store.overlay[34], 0xC1)
        self.assertEqual(len(store.overlay), len(original))

    def test_boolean_validation_rejects_non_boolean_values(self):
        original = event(bytes((0x0D, 0x00, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Move through walls must be true or false"):
            save_event_fields(store, 1, 0, 0, 0, sha256(original), {"throughWalls": 2})
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
