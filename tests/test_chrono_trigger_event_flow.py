from __future__ import annotations

import unittest

from games.chrono_trigger.event_flow import analyze_function_flow, decorate_event_flow


def command(offset: int, opcode: int, size: int, args: bytes = b"") -> dict:
    return {
        "offset": offset,
        "opcode": opcode,
        "size": size,
        "argumentsHex": args.hex(" ").upper(),
    }


def function(start: int, end: int, commands: list[dict], *, complete: bool = True) -> dict:
    return {"start": start, "end": end, "commands": commands, "complete": complete}


class EventFlowTests(unittest.TestCase):
    def test_conditional_forward_jump_has_jump_and_fallthrough_edges(self):
        fn = function(32, 40, [
            command(32, 0x12, 5, b"\x00\x00\x00\x03"),  # final byte at 36, target 39
            command(37, 0xEA, 2, b"\x01"),
            command(39, 0x00, 1),
        ])
        flow = analyze_function_flow(fn)
        self.assertTrue(flow["complete"])
        self.assertEqual(flow["jumpCount"], 1)
        jump = next(edge for edge in flow["edges"] if edge["kind"] == "jump")
        fallthrough = next(edge for edge in flow["edges"] if edge["from"] == 32 and edge["kind"] == "fallthrough")
        self.assertEqual(jump["to"], 39)
        self.assertTrue(jump["validTarget"])
        self.assertTrue(jump["conditional"])
        self.assertEqual(fallthrough["to"], 37)
        self.assertEqual(flow["invalidJumpCount"], 0)

    def test_backward_jump_uses_final_command_byte_as_origin(self):
        fn = function(32, 36, [
            command(32, 0xEA, 2, b"\x01"),
            command(34, 0x11, 2, b"\x03"),  # final byte at 35; 35-3=32
        ])
        flow = analyze_function_flow(fn)
        jump = next(edge for edge in flow["edges"] if edge["kind"] == "jump")
        self.assertEqual(jump["from"], 34)
        self.assertEqual(jump["to"], 32)
        self.assertEqual(jump["direction"], "backward")
        self.assertFalse(jump["conditional"])
        self.assertEqual(flow["invalidJumpCount"], 0)

    def test_jump_to_function_end_is_a_valid_boundary(self):
        fn = function(10, 14, [
            command(10, 0x10, 2, b"\x03"),  # final byte at 11 + 3 = end 14
            command(12, 0x00, 1),
            command(13, 0x00, 1),
        ])
        flow = analyze_function_flow(fn)
        jump = next(edge for edge in flow["edges"] if edge["kind"] == "jump")
        self.assertEqual(jump["to"], 14)
        self.assertTrue(jump["validTarget"])

    def test_mid_command_jump_target_is_reported_not_guessed(self):
        fn = function(32, 40, [
            command(32, 0x10, 2, b"\x03"),  # final byte at 33 -> 36, mid next command
            command(34, 0x83, 4, b"\x01\x00\x00"),
            command(38, 0xEA, 2, b"\x01"),
        ])
        flow = analyze_function_flow(fn)
        self.assertEqual(flow["invalidJumpCount"], 1)
        problem = flow["problems"][0]
        self.assertEqual(problem["code"], "jump-target-not-command-boundary")
        self.assertEqual(problem["target"], 36)
        self.assertTrue(problem["withinFunction"])

    def test_out_of_function_target_is_reported(self):
        fn = function(100, 103, [command(100, 0x10, 2, b"\xFF")])
        flow = analyze_function_flow(fn)
        jump = flow["edges"][0]
        self.assertFalse(jump["withinFunction"])
        self.assertFalse(jump["validTarget"])

    def test_terminator_has_no_fallthrough(self):
        fn = function(0, 2, [command(0, 0x00, 1), command(1, 0x00, 1)])
        flow = analyze_function_flow(fn)
        self.assertEqual(flow["edges"], [])

    def test_incomplete_disassembly_has_no_inferred_edges(self):
        fn = function(0, 4, [command(0, 0xEA, 2, b"\x01")], complete=False)
        flow = analyze_function_flow(fn)
        self.assertFalse(flow["complete"])
        self.assertEqual(flow["edges"], [])
        self.assertEqual(flow["problems"][0]["code"], "incomplete-disassembly")

    def test_decorator_counts_aliased_function_bounds_once(self):
        fn_a = function(32, 36, [command(32, 0x11, 2, b"\x01")])
        fn_b = function(32, 36, [command(32, 0x11, 2, b"\x01")])
        payload = {"objects": [{"functions": [fn_a, fn_b]}]}
        result = decorate_event_flow(payload)
        self.assertEqual(result["flowSummary"]["uniqueFunctions"], 1)
        self.assertEqual(result["flowSummary"]["jumpCount"], 1)
        self.assertIn("flow", fn_a)
        self.assertIn("flow", fn_b)


if __name__ == "__main__":
    unittest.main()
