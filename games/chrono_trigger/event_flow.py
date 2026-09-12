"""Read-only control-flow analysis for decoded Chrono Trigger field events.

Chrono Trigger relative jumps count from the final byte of the jump command.
This module uses that documented convention to validate that jump destinations
land on decoded command boundaries. It does not emulate conditions or execute
scripts.
"""

from __future__ import annotations


FORWARD_JUMPS = frozenset({
    0x10, 0x12, 0x13, 0x14, 0x15, 0x16, 0x18, 0x1A,
    0x27, 0x28, 0x2D, 0x30, 0x31, 0x34, 0x35, 0x36,
    0x37, 0x38, 0x39, 0x3B, 0x3C, 0x3F, 0x40, 0x41,
    0x42, 0x43, 0x44, 0x6E, 0xC9, 0xCC, 0xCF, 0xD2,
})
BACKWARD_JUMPS = frozenset({0x11})
UNCONDITIONAL_JUMPS = frozenset({0x10, 0x11})
TERMINATORS = frozenset({0x00, 0xB1, 0xB2})


def _args(command: dict) -> bytes:
    try:
        return bytes.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return b""


def analyze_function_flow(function: dict) -> dict:
    """Return jump/fallthrough edges for one already-decoded function."""
    commands = function.get("commands", [])
    start = int(function.get("start", 0))
    end = int(function.get("end", start))
    complete = bool(function.get("complete", False))
    boundaries = {int(command["offset"]) for command in commands}
    boundaries.add(end)
    edges = []
    problems = []
    jump_count = 0

    if not complete:
        return {
            "complete": False,
            "jumpCount": 0,
            "edgeCount": 0,
            "invalidJumpCount": 0,
            "edges": [],
            "problems": [{
                "code": "incomplete-disassembly",
                "message": "Control flow is not inferred past an incomplete function disassembly.",
            }],
        }

    for command in commands:
        opcode = int(command["opcode"])
        offset = int(command["offset"])
        size = int(command["size"])
        next_offset = offset + size
        args = _args(command)

        if opcode in FORWARD_JUMPS or opcode in BACKWARD_JUMPS:
            jump_count += 1
            if not args:
                problem = {
                    "code": "jump-without-offset",
                    "offset": offset,
                    "opcode": opcode,
                    "message": f"Jump opcode 0x{opcode:02X} has no decoded jump byte.",
                }
                problems.append(problem)
                continue
            distance = args[-1]
            origin = offset + size - 1
            target = origin + distance if opcode in FORWARD_JUMPS else origin - distance
            valid = target in boundaries
            within = start <= target <= end
            edges.append({
                "from": offset,
                "to": target,
                "kind": "jump",
                "opcode": opcode,
                "distance": distance,
                "direction": "forward" if opcode in FORWARD_JUMPS else "backward",
                "conditional": opcode not in UNCONDITIONAL_JUMPS,
                "validTarget": valid,
                "withinFunction": within,
            })
            if not valid:
                problems.append({
                    "code": "jump-target-not-command-boundary",
                    "offset": offset,
                    "opcode": opcode,
                    "target": target,
                    "withinFunction": within,
                    "message": (
                        f"Jump at 0x{offset:X} targets 0x{target:X}, which is not a decoded command boundary."
                    ),
                })
            if opcode not in UNCONDITIONAL_JUMPS and next_offset <= end:
                edges.append({
                    "from": offset,
                    "to": next_offset,
                    "kind": "fallthrough",
                    "opcode": opcode,
                    "conditional": True,
                    "validTarget": next_offset in boundaries,
                    "withinFunction": start <= next_offset <= end,
                })
            continue

        if opcode in TERMINATORS:
            continue
        if next_offset <= end:
            edges.append({
                "from": offset,
                "to": next_offset,
                "kind": "fallthrough",
                "opcode": opcode,
                "conditional": False,
                "validTarget": next_offset in boundaries,
                "withinFunction": start <= next_offset <= end,
            })

    return {
        "complete": True,
        "jumpCount": jump_count,
        "edgeCount": len(edges),
        "invalidJumpCount": sum(problem["code"] == "jump-target-not-command-boundary" for problem in problems),
        "edges": edges,
        "problems": problems,
    }


def decorate_event_flow(payload: dict) -> dict:
    """Attach flow analysis and aggregate unique-function diagnostics."""
    seen: set[tuple[int, int]] = set()
    unique_functions = 0
    jumps = 0
    invalid = 0
    incomplete = 0
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            flow = analyze_function_flow(function)
            function["flow"] = flow
            key = (int(function.get("start", 0)), int(function.get("end", 0)))
            if key in seen:
                continue
            seen.add(key)
            unique_functions += 1
            jumps += flow["jumpCount"]
            invalid += flow["invalidJumpCount"]
            incomplete += int(not flow["complete"])
    payload["flowSummary"] = {
        "uniqueFunctions": unique_functions,
        "jumpCount": jumps,
        "invalidJumpCount": invalid,
        "incompleteFunctions": incomplete,
    }
    return payload
