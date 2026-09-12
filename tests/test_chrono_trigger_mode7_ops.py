from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.editor_registry import decorate_event_editors, editor_schema
from games.chrono_trigger.event_edit import save_event_arguments
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
    def test_scene_mode_has_read_only_semantics_and_no_editor(self):
        cmd = command(b"\x42")
        self.assertIsNone(editor_schema(cmd))
        semantic = mode7_semantics(cmd)
        self.assertEqual(semantic["summary"], "Mode 7 scene 66")
        self.assertEqual(semantic["sceneId"], 0x42)
        self.assertTrue(semantic["readOnlyMode"])

    def test_parameter_specials_have_read_only_payload_semantics(self):
        for code, name in ((0x90, "Black Circle"), (0x97, "Mode 97")):
            with self.subTest(code=code):
                cmd = command(bytes((code, 1, 2, 3)))
                self.assertIsNone(editor_schema(cmd))
                semantic = mode7_semantics(cmd)
                self.assertEqual(semantic["specialCode"], code)
                self.assertEqual(
                    (semantic["param1"], semantic["param2"], semantic["param3"]),
                    (1, 2, 3),
                )
                self.assertTrue(semantic["readOnlyMode"])
                self.assertIn(name, semantic["summary"])

    def test_simple_specials_are_semantic_only(self):
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

    def test_semantic_decorator_does_not_attach_writer(self):
        payload = {
            "objects": [{
                "functions": [{
                    "commands": [command(b"\x42"), command(b"\x90\x01\x02\x03")],
                }],
            }],
        }
        decorate_event_editors(payload)
        for cmd in payload["objects"][0]["functions"][0]["commands"]:
            self.assertIn("semantic", cmd)
            self.assertNotIn("editor", cmd)

    def test_shared_writer_guard_rejects_dynamic_mode7_scene(self):
        original = event(bytes((0xFF, 0x42, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "variable or unresolved PC width"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), b"\x43")
        self.assertIsNone(store.overlay)

    def test_shared_writer_guard_rejects_dynamic_mode7_parameter_special(self):
        original = event(bytes((0xFF, 0x90, 0x11, 0x22, 0x33, 0x00)))
        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "variable or unresolved PC width"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), b"\x90\x11\xAA\x33")
        self.assertIsNone(store.overlay)

    def test_wrong_width_or_unknown_special_has_no_semantics_or_editor(self):
        for args in (
            b"\x42\x01",
            b"\x90",
            b"\x90\x01\x02",
            b"\x91\x01\x02\x03",
            b"\x99",
        ):
            with self.subTest(args=args.hex()):
                cmd = command(args)
                self.assertIsNone(editor_schema(cmd))
                self.assertIsNone(mode7_semantics(cmd))


if __name__ == "__main__":
    unittest.main()
