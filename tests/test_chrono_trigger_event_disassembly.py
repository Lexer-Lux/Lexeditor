from __future__ import annotations

import struct
import unittest

from games.chrono_trigger.events import parse_event


def _event_with_function(payload: bytes) -> bytes:
    pointer_table = b"".join(struct.pack("<H", 32) for _ in range(16))
    return bytes([1]) + pointer_table + payload


class FieldEventDisassemblyTests(unittest.TestCase):
    def test_event_exposes_pc_command_disassembly(self):
        event = parse_event(_event_with_function(bytes([0x83, 0x34, 0x12, 0x80, 0x00])))
        self.assertEqual(event["uniqueFunctionBounds"], 1)
        self.assertEqual(event["decodedCommandCount"], 2)
        self.assertEqual(event["completeFunctionBounds"], 1)
        first = event["objects"][0]["functions"][0]
        self.assertTrue(first["complete"])
        self.assertEqual(first["commands"][0]["name"], "Load Enemy")
        self.assertEqual(first["commands"][0]["size"], 4)
        self.assertEqual(first["commands"][1]["name"], "Return")

    def test_event_reports_fail_closed_problem(self):
        event = parse_event(_event_with_function(bytes([0x9E, 0x01, 0x02])))
        self.assertEqual(event["problemFunctionBounds"], 1)
        self.assertEqual(event["completeFunctionBounds"], 0)
        first = event["objects"][0]["functions"][0]
        self.assertFalse(first["complete"])
        self.assertEqual(first["problem"]["opcode"], 0x9E)


if __name__ == "__main__":
    unittest.main()
