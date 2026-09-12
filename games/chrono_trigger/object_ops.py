"""Proven fixed-width object-control editors for Chrono Trigger Steam events."""

from __future__ import annotations


U8 = 0xFF
ENCODED_TARGET_MAX = U8 // 2
OBJECT_OPCODES = frozenset({0x0A, 0x0B, 0x0C, 0x7C, 0x7D})
_OPERATION = {
    0x0A: "remove",
    0x0B: "processing-off",
    0x0C: "processing-on",
    0x7C: "drawing-on",
    0x7D: "drawing-off",
}


def _args(command: dict) -> bytearray | None:
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    opcode = int(command["opcode"])
    if opcode not in OBJECT_OPCODES or len(args) != 1 or args[0] & 1:
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


def object_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    return [{"key": "objectId", "label": "Object ID", "minimum": 0, "maximum": ENCODED_TARGET_MAX}]


def object_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    return {"objectId": args[0] // 2}


def apply_object_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    unknown = set(values) - {"objectId"}
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if "objectId" in values:
        args[0] = _int(values["objectId"], 0, ENCODED_TARGET_MAX, "Object ID") * 2
    return bytes(args)


def object_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    object_id = args[0] // 2
    summary = {
        0x0A: f"Remove object {object_id}",
        0x0B: f"Disable script processing for object {object_id}",
        0x0C: f"Enable script processing for object {object_id}",
        0x7C: f"Turn drawing on for object {object_id}",
        0x7D: f"Turn drawing off for object {object_id}",
    }[opcode]
    return {"summary": summary, "objectId": object_id, "operation": _OPERATION[opcode]}


def decorate_object_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = object_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
