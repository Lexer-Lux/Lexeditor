from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import editor_schema, save_event_fields
from games.chrono_trigger.mode7_ops import mode7_semantics


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
        "opcode": 0xFF,
        "argumentsHex": arguments.hex(" ").upper(),
        "argumentBytes": len(arguments),
    }


class Mode7OpTests(unittest.TestCase):
    def test_scene_mode_exposes_only_width_stable_scene_id(self):
        schema = editor_schema(command(b"\x42"))
        self.assertIsNotNone(schema)
        self.assertEqual(schema["values"], {"sceneId": 0x42})
        self.assertEqual(schema["fields"], [{
            "key": "sceneId", "label": "Mode 7 scene", "kind": "integer",
            "min": 0, "max": 0x89,
        }])
        self.assertEqual(mode7_semantics(command(b"\x42"))["summary"], "Mode 7 scene 66")

    def test_scene_edit_preserves_one_argument_byte(self):
        original = event(bytes((0xFF, 0x42, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"sceneId": 0x89})
        self.assertEqual(store.overlay[33:35], bytes((0xFF, 0x89)))
        self.assertEqual(len(store.overlay), len(original))

        rejected = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "Mode 7 scene must be between 0 and 137"):
            save_event_fields(rejected, 1, 0, 0, 0, sha256(original), {"sceneId": 0x90})
        self.assertIsNone(rejected.overlay)

    def test_parameter_specials_expose_payload_but_not_mode_byte(self):
        for code, name in ((0x90, "Black Circle"), (0x97, "Mode 97")):
            with self.subTest(code=code):
                cmd = command(bytes((code, 1, 2, 3)))
                schema = editor_schema(cmd)
                self.assertEqual(schema["values"], {"param1": 1, "param2": 2, "param3": 3})
                self.assertEqual([field["key"] for field in schema["fields"]], ["param1", "param2", "param3"])
                semantic = mode7_semantics(cmd)
                self.assertEqual(semantic["specialCode"], code)
                self.assertIn(name, semantic["summary"])

    def test_parameter_special_partial_write_keeps_code_and_other_params(self):
        original = event(bytes((0xFF, 0x90, 0x11, 0x22, 0x33, 0x00)))
        store = FakeStore(original)
        save_event_fields(store, 1, 0, 0, 0, sha256(original), {"param2": 0xAA})
        self.assertEqual(store.overlay[34:38], bytes((0x90, 0x11, 0xAA, 0x33)))
        self.assertEqual(len(store.overlay), len(original))

        with self.assertRaisesRegex(ValueError, "Unknown fields"):
            second = FakeStore(original)
            save_event_fields(second, 1, 0, 0, 0, sha256(original), {"specialCode": 0x97})

    def test_simple_specials_are_semantic_only_and_not_writable(self):
        expected = {
            0x91: "Mode 91",
            0x92: "Left-Right Swipe Open",
            0x93: "Right-Left Swipe Open",
            0x94: "Left-Right Swipe Close",
            0x95: "Right-Left Swipe Close",
            0x96: "Reset",
            0x98: "Mode 98",
        }
        for code, name in expected.items():
            with self.subTest(code=code):
                cmd = command(bytes((code,)))
                self.assertIsNone(editor_schema(cmd))
                semantic = mode7_semantics(cmd)
                self.assertTrue(semantic["readOnlyMode"])
                self.assertIn(name, semantic["summary"])

    def test_wrong_width_or_unknown_special_stays_unregistered(self):
        for args in (
            b"\x42\x01",
            b"\x90",
            b"\x90\x01\x02",
            b"\x91\x01\x02\x03",
            b"\x99",
        ):
            with self.subTest(args=args.hex()):
                self.assertIsNone(editor_schema(command(args)))


if __name__ == "__main__":
    unittest.main()
