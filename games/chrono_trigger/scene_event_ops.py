"""Proven fixed-width party/screen event editors for Chrono Trigger Steam."""

from __future__ import annotations


U8 = 0xFF
SCENE_EVENT_OPCODES = frozenset({0xD9, 0xE7, 0xF4})


def _args(command: dict) -> bytearray | None:
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    opcode = int(command["opcode"])
    expected = {0xD9: 6, 0xE7: 2, 0xF4: 1}.get(opcode)
    if expected is None or len(args) != expected:
        return None
    if opcode == 0xF4 and args[0] not in {0, 1}:
        return None
    return args


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _bool(value, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{label} must be true or false")


def scene_event_field_specs(command: dict) -> list[dict] | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    number = lambda key, label: {"key": key, "label": label, "minimum": 0, "maximum": U8}
    if opcode == 0xD9:
        return [
            number("pc1X", "PC1 X coordinate byte"), number("pc1Y", "PC1 Y coordinate byte"),
            number("pc2X", "PC2 X coordinate byte"), number("pc2Y", "PC2 Y coordinate byte"),
            number("pc3X", "PC3 X coordinate byte"), number("pc3Y", "PC3 Y coordinate byte"),
        ]
    if opcode == 0xE7:
        return [number("x", "Screen X coordinate byte"), number("y", "Screen Y coordinate byte")]
    return [{"key": "enabled", "label": "Screen shake", "minimum": 0, "maximum": 1, "kind": "boolean"}]


def scene_event_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0xD9:
        return {
            "pc1X": args[0], "pc1Y": args[1],
            "pc2X": args[2], "pc2Y": args[3],
            "pc3X": args[4], "pc3Y": args[5],
        }
    if opcode == 0xE7:
        return {"x": args[0], "y": args[1]}
    return {"enabled": bool(args[0])}


def apply_scene_event_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = scene_event_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if opcode == 0xD9:
        mapping = (
            ("pc1X", 0, "PC1 X coordinate byte"), ("pc1Y", 1, "PC1 Y coordinate byte"),
            ("pc2X", 2, "PC2 X coordinate byte"), ("pc2Y", 3, "PC2 Y coordinate byte"),
            ("pc3X", 4, "PC3 X coordinate byte"), ("pc3Y", 5, "PC3 Y coordinate byte"),
        )
        for key, offset, label in mapping:
            if key in values:
                args[offset] = _int(values[key], 0, U8, label)
    elif opcode == 0xE7:
        if "x" in values:
            args[0] = _int(values["x"], 0, U8, "Screen X coordinate byte")
        if "y" in values:
            args[1] = _int(values["y"], 0, U8, "Screen Y coordinate byte")
    elif "enabled" in values:
        args[0] = 1 if _bool(values["enabled"], "Screen shake") else 0
    return bytes(args)


def scene_event_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0xD9:
        return {
            "summary": f"Move party · PC1 ({args[0]}, {args[1]}) · PC2 ({args[2]}, {args[3]}) · PC3 ({args[4]}, {args[5]}) · coordinate bytes",
            "pc1X": args[0], "pc1Y": args[1],
            "pc2X": args[2], "pc2Y": args[3],
            "pc3X": args[4], "pc3Y": args[5],
        }
    if opcode == 0xE7:
        return {"summary": f"Scroll screen · coordinate bytes ({args[0]}, {args[1]})", "x": args[0], "y": args[1]}
    return {"summary": f"Screen shake {'on' if args[0] else 'off'}", "enabled": bool(args[0])}


def decorate_scene_event_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = scene_event_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
