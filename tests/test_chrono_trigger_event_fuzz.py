from __future__ import annotations

import random
import struct
import unittest

from games.chrono_trigger.events import parse_event
from games.chrono_trigger.field_commands import disassemble_function


class EventParserFuzzTests(unittest.TestCase):
    def test_random_command_streams_stay_inside_function_bounds(self):
        rng = random.Random(0xC7E)
        for length in range(65):
            for _ in range(12):
                data = bytes(rng.getrandbits(8) for _ in range(length))
                result = disassemble_function(data, 0, len(data))

                self.assertEqual(result["totalBytes"], length)
                self.assertGreaterEqual(result["decodedBytes"], 0)
                self.assertLessEqual(result["decodedBytes"], length)

                cursor = 0
                for index, command in enumerate(result["commands"]):
                    self.assertEqual(command["index"], index)
                    self.assertEqual(command["offset"], cursor)
                    self.assertGreaterEqual(command["size"], 1)
                    self.assertEqual(command["size"], 1 + command["argumentBytes"])
                    self.assertLessEqual(command["offset"] + command["size"], length)
                    self.assertEqual(len(command["rawHex"].split()), command["size"])
                    self.assertEqual(len(command["argumentsHex"].split()), command["argumentBytes"])
                    cursor += command["size"]

                self.assertEqual(cursor, result["decodedBytes"])
                if result["complete"]:
                    self.assertIsNone(result["problem"])
                    self.assertEqual(result["decodedBytes"], length)
                else:
                    problem = result["problem"]
                    self.assertIsNotNone(problem)
                    self.assertEqual(problem["offset"], result["decodedBytes"])
                    self.assertEqual(problem["remainingBytes"], length - problem["offset"])
                    self.assertLessEqual(len(problem["rawPreview"].split()), 16)
                    self.assertEqual(
                        problem["truncatedPreview"],
                        problem["remainingBytes"] > 16,
                    )

    def test_random_single_object_events_count_aliased_slots_once(self):
        rng = random.Random(0xA7E1)
        for length in range(65):
            payload = bytes(rng.getrandbits(8) for _ in range(length))
            pointer_table = b"".join(struct.pack("<H", 32) for _ in range(16))
            event = parse_event(bytes((1,)) + pointer_table + payload)

            self.assertEqual(event["objectCount"], 1)
            self.assertEqual(event["functionSlots"], 16)
            self.assertEqual(event["uniqueFunctionBounds"], 1)
            self.assertEqual(
                event["completeFunctionBounds"] + event["problemFunctionBounds"],
                1,
            )
            first = event["objects"][0]["functions"][0]
            self.assertEqual(event["decodedCommandCount"], len(first["commands"]))
            for function in event["objects"][0]["functions"]:
                self.assertEqual(function["start"], 32)
                self.assertEqual(function["end"], 32 + length)
                self.assertEqual(function["complete"], first["complete"])
                self.assertEqual(function["problem"], first["problem"])
                self.assertEqual(function["commands"], first["commands"])

    def test_problem_preview_never_crosses_function_end(self):
        # The dynamic EC decoder can see bytes later in the event buffer while
        # deciding its width. Even then, fail-closed diagnostics must expose
        # only bytes that belong to the current function.
        data = bytes((0xEC, 0x88, 0x00, 0xA6, 0x01))
        result = disassemble_function(data, 0, 1)
        self.assertFalse(result["complete"])
        self.assertEqual(result["decodedBytes"], 0)
        self.assertEqual(result["problem"]["opcode"], 0xEC)
        self.assertEqual(result["problem"]["remainingBytes"], 1)
        self.assertEqual(result["problem"]["rawPreview"], "EC")
        self.assertFalse(result["problem"]["truncatedPreview"])

    def test_event_pointers_outside_bytecode_fail_closed(self):
        pointer_table = bytearray(b"".join(struct.pack("<H", 32) for _ in range(16)))
        struct.pack_into("<H", pointer_table, 0, 31)
        with self.assertRaisesRegex(ValueError, "outside bytecode"):
            parse_event(bytes((1,)) + bytes(pointer_table))

        pointer_table = bytearray(b"".join(struct.pack("<H", 32) for _ in range(16)))
        struct.pack_into("<H", pointer_table, 30, 33)
        with self.assertRaisesRegex(ValueError, "outside bytecode"):
            parse_event(bytes((1,)) + bytes(pointer_table))


if __name__ == "__main__":
    unittest.main()
