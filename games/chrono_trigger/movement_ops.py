"""Proven fixed-width Chrono Trigger Steam movement/follow command editors.

Only commands whose Temporal Redux constructors and command-table descriptions
agree on operand order/width are included. Coordinate bytes are kept literal
where their world/tile/pixel unit is not independently established.
"""

from __future__ import annotations


U8 = 0xFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
MOVEMENT_OPCODES = frozenset({
    0x7A,
    0x8F, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0x9D,
    0xA0, 0xA1, 0xB5, 0xB6,
})
_PC_TARGET_OPCODES = frozenset({0x8F, 0x95, 0x99, 0xB6})
_DIRECT_COORD_OPCODES = frozenset({0x96, 0xA0})
_MEMORY_COORD_OPCODES = frozenset({0x97, 0xA1})


def _args(command: dict) -> bytearray | None:
    try:
        return bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _script_address(slot: int) -> int:
    return SCRIPT_MEM_START + int(slot) * 2


def _script_offset(value, label: str) -> int:
    address = _int(value, SCRIPT_MEM_START, SCRIPT_MEM_LAST, label)
    if (address - SCRIPT_MEM_START) % 2:
        raise ValueError(f"{label} must be an even script-memory address")
    return (address - SCRIPT_MEM_START) // 2


def _layout(command: dict) -> tuple[int, bytearray] | None:
    opcode = int(command["opcode"])
    args = _args(command)
    if opcode not in MOVEMENT_OPCODES or args is None:
        return None
    expected = {
        0x7A: 3,
        0x8F: 1,
        0x94: 1, 0x95: 1,
        0x96: 2, 0x97: 2,
        0x98: 2, 0x99: 2,
        0x9A: 3, 0x9D: 2,
        0xA0: 2, 0xA1: 2,
        0xB5: 1, 0xB6: 1,
    }[opcode]
    if len(args) != expected:
        return None
    if opcode in _PC_TARGET_OPCODES and not 1 <= args[0] <= 6:
        return None
    return opcode, args


def movement_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value = parsed
    number = lambda key, label, minimum=0, maximum=U8: {
        "key": key, "label": label, "minimum": minimum, "maximum": maximum,
    }
    address = lambda key, label: {
        "key": key, "label": label,
        "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST,
    }
    if opcode == 0x7A:
        return [
            number("x", "X coordinate byte"),
            number("y", "Y coordinate byte"),
            number("jumpHeightSpeed", "Jump height/speed byte"),
        ]
    if opcode in {0x8F, 0x95, 0xB6}:
        return [number("playerId", "Player character", 1, 6)]
    if opcode in {0x94, 0xB5}:
        return [number("objectId", "Object ID")]
    if opcode in _DIRECT_COORD_OPCODES:
        return [number("x", "X coordinate byte"), number("y", "Y coordinate byte")]
    if opcode in _MEMORY_COORD_OPCODES:
        return [address("xAddress", "X coordinate source"), address("yAddress", "Y coordinate source")]
    if opcode == 0x9D:
        return [address("directionAddress", "Direction source"), address("magnitudeAddress", "Magnitude source")]
    if opcode == 0x98:
        return [number("objectId", "Object ID"), number("distance", "Distance")]
    if opcode == 0x99:
        return [number("playerId", "Player character", 1, 6), number("distance", "Distance")]
    return [number("x", "X coordinate byte"), number("y", "Y coordinate byte"), number("distance", "Distance")]


def movement_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    if opcode == 0x7A:
        return {"x": args[0], "y": args[1], "jumpHeightSpeed": args[2]}
    if opcode in {0x8F, 0x95, 0xB6}:
        return {"playerId": args[0]}
    if opcode in {0x94, 0xB5}:
        return {"objectId": args[0]}
    if opcode in _DIRECT_COORD_OPCODES:
        return {"x": args[0], "y": args[1]}
    if opcode in _MEMORY_COORD_OPCODES:
        return {"xAddress": _script_address(args[0]), "yAddress": _script_address(args[1])}
    if opcode == 0x9D:
        return {"directionAddress": _script_address(args[0]), "magnitudeAddress": _script_address(args[1])}
    if opcode == 0x98:
        return {"objectId": args[0], "distance": args[1]}
    if opcode == 0x99:
        return {"playerId": args[0], "distance": args[1]}
    return {"x": args[0], "y": args[1], "distance": args[2]}


def apply_movement_op(command: dict, values: dict) -> bytes | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    specs = movement_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if opcode == 0x7A:
        if "x" in values:
            args[0] = _int(values["x"], 0, U8, "X coordinate byte")
        if "y" in values:
            args[1] = _int(values["y"], 0, U8, "Y coordinate byte")
        if "jumpHeightSpeed" in values:
            args[2] = _int(values["jumpHeightSpeed"], 0, U8, "Jump height/speed byte")
    elif opcode in {0x8F, 0x95, 0xB6}:
        if "playerId" in values:
            args[0] = _int(values["playerId"], 1, 6, "Player character")
    elif opcode in {0x94, 0xB5}:
        if "objectId" in values:
            args[0] = _int(values["objectId"], 0, U8, "Object ID")
    elif opcode in _DIRECT_COORD_OPCODES:
        if "x" in values:
            args[0] = _int(values["x"], 0, U8, "X coordinate byte")
        if "y" in values:
            args[1] = _int(values["y"], 0, U8, "Y coordinate byte")
    elif opcode in _MEMORY_COORD_OPCODES:
        if "xAddress" in values:
            args[0] = _script_offset(values["xAddress"], "X coordinate source")
        if "yAddress" in values:
            args[1] = _script_offset(values["yAddress"], "Y coordinate source")
    elif opcode == 0x9D:
        if "directionAddress" in values:
            args[0] = _script_offset(values["directionAddress"], "Direction source")
        if "magnitudeAddress" in values:
            args[1] = _script_offset(values["magnitudeAddress"], "Magnitude source")
    elif opcode == 0x98:
        if "objectId" in values:
            args[0] = _int(values["objectId"], 0, U8, "Object ID")
        if "distance" in values:
            args[1] = _int(values["distance"], 0, U8, "Distance")
    elif opcode == 0x99:
        if "playerId" in values:
            args[0] = _int(values["playerId"], 1, 6, "Player character")
        if "distance" in values:
            args[1] = _int(values["distance"], 0, U8, "Distance")
    else:
        if "x" in values:
            args[0] = _int(values["x"], 0, U8, "X coordinate byte")
        if "y" in values:
            args[1] = _int(values["y"], 0, U8, "Y coordinate byte")
        if "distance" in values:
            args[2] = _int(values["distance"], 0, U8, "Distance")
    return bytes(args)


def movement_semantics(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    if opcode == 0x7A:
        return {
            "summary": f"NPC jump · coordinate bytes ({args[0]}, {args[1]}) · height/speed byte {args[2]}",
            "x": args[0], "y": args[1], "jumpHeightSpeed": args[2],
            "operation": "npc-jump",
        }
    if opcode == 0x8F:
        return {"summary": f"Follow PC {args[0]} at distance", "playerId": args[0], "operation": "follow-pc-distance"}
    if opcode == 0x94:
        return {"summary": f"Follow object {args[0]}", "objectId": args[0], "operation": "follow-object"}
    if opcode == 0x95:
        return {"summary": f"Follow PC {args[0]}", "playerId": args[0], "operation": "follow-pc"}
    if opcode in _DIRECT_COORD_OPCODES:
        animated = opcode == 0xA0
        prefix = "Animated move" if animated else "NPC move"
        return {"summary": f"{prefix} · coordinate bytes ({args[0]}, {args[1]})", "x": args[0], "y": args[1], "animated": animated}
    if opcode in _MEMORY_COORD_OPCODES:
        x_address, y_address = _script_address(args[0]), _script_address(args[1])
        animated = opcode == 0xA1
        prefix = "Animated move" if animated else "NPC move"
        return {"summary": f"{prefix} from X 0x{x_address:06X} · Y 0x{y_address:06X}", "xAddress": x_address, "yAddress": y_address, "animated": animated}
    if opcode == 0x9D:
        direction, magnitude = _script_address(args[0]), _script_address(args[1])
        return {
            "summary": f"Vector move from direction 0x{direction:06X} · magnitude 0x{magnitude:06X}",
            "directionAddress": direction,
            "magnitudeAddress": magnitude,
            "operation": "vector-move-from-memory",
        }
    if opcode == 0x98:
        return {"summary": f"Move toward object {args[0]} · distance {args[1]}", "objectId": args[0], "distance": args[1]}
    if opcode == 0x99:
        return {"summary": f"Move toward PC {args[0]} · distance {args[1]}", "playerId": args[0], "distance": args[1]}
    if opcode == 0x9A:
        return {"summary": f"Move toward coordinate bytes ({args[0]}, {args[1]}) · distance {args[2]}", "x": args[0], "y": args[1], "distance": args[2]}
    if opcode == 0xB5:
        return {"summary": f"Loop follow object {args[0]}", "objectId": args[0], "operation": "loop-follow-object"}
    return {"summary": f"Loop follow PC {args[0]}", "playerId": args[0], "operation": "loop-follow-pc"}


def decorate_movement_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = movement_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
