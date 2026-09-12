from __future__ import annotations

from types import SimpleNamespace
import struct
import unittest

from games.chrono_trigger.data import sha256
from games.chrono_trigger.event_edit import save_event_arguments
from games.chrono_trigger.events import parse_event


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


def event(bytecode: bytes) -> bytes:
    data = bytearray(32)
    for index in range(16):
        struct.pack_into("<H", data, index * 2, 32)
    data.extend(bytecode)
    return bytes([1]) + bytes(data)


class DynamicWriteGuardTests(unittest.TestCase):
    def test_known_ec_form_decodes_but_raw_writer_still_blocks_it(self):
        original = event(bytes((0xEC, 0x88, 0x00)))
        parsed = parse_event(original)
        command = parsed["objects"][0]["functions"][0]["commands"][0]
        self.assertEqual(command["opcode"], 0xEC)
        self.assertEqual(command["argumentsHex"], "88")
        self.assertEqual(command["argumentBytes"], 1)

        store = FakeStore(original)
        with self.assertRaisesRegex(ValueError, "0xEC.*variable or unresolved.*read-only"):
            save_event_arguments(store, 1, 0, 0, 0, sha256(original), "F0")
        self.assertIsNone(store.overlay)


if __name__ == "__main__":
    unittest.main()
