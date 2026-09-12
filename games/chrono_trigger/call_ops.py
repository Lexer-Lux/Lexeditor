"""Proven fixed-width field-event function-call editors for Chrono Trigger Steam.

Temporal Redux constructors establish a doubled target byte plus one packed
priority/function byte for opcodes 0x02-0x07. The opcode fixes whether the call
continues immediately, synchronizes until start, or halts until completion.
"""

from __future__ import annotations


U8 = 0xFF
ENCODED_TARGET_MAX = U8 // 2
CALL_OPCODES = frozenset({0x02, 0x03, 0x04, 0x05, 0x06, 0x07})
_OBJECT_OPCODES = frozenset({0x02, 0x03, 0x04})
_MODE = {
    0x02: "continue", 0x03: "sync", 0x04: "halt",
    0x05: "continue", 0x06: "sync", 0x07: "halt",
}


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


def _layout(command: dict) -> tuple[int, bytearray] | None:
    opcode = int(command["opcode"])
    args = _args(command)
    if opcode not in CALL_OPCODES or args is None or len(args) != 2:
        return None
    if args[0] & 1:
        return None
    return opcode, args


def call_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value = parsed
    target_key = "objectId" if opcode in _OBJECT_OPCODES else "playerId"
    target_label = "Object ID" if opcode in _OBJECT_OPCODES else "Player character ID"
    return [
        {"key": target_key, "label": target_label, "minimum": 0, "maximum": ENCODED_TARGET_MAX},
        {"key": "functionId", "label": "Function ID", "minimum": 0, "maximum": 0x0F},
        {"key": "priority", "label": "Priority", "minimum": 0, "maximum": 0x0F},
    ]


def call_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    target_key = "objectId" if opcode in _OBJECT_OPCODES else "playerId"
    return {
        target_key: args[0] // 2,
        "functionId": args[1] & 0x0F,
        "priority": args[1] >> 4,
    }


def apply_call_op(command: dict, values: dict) -> bytes | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    specs = call_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    target_key = "objectId" if opcode in _OBJECT_OPCODES else "playerId"
    target_label = "Object ID" if opcode in _OBJECT_OPCODES else "Player character ID"
    if target_key in values:
        args[0] = _int(values[target_key], 0, ENCODED_TARGET_MAX, target_label) * 2
    function_id = _int(values.get("functionId", args[1] & 0x0F), 0, 0x0F, "Function ID")
    priority = _int(values.get("priority", args[1] >> 4), 0, 0x0F, "Priority")
    args[1] = (priority << 4) | function_id
    return bytes(args)


def call_semantics(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    target = args[0] // 2
    function_id = args[1] & 0x0F
    priority = args[1] >> 4
    mode = _MODE[opcode]
    target_kind = "object" if opcode in _OBJECT_OPCODES else "PC"
    target_key = "objectId" if opcode in _OBJECT_OPCODES else "playerId"
    return {
        "summary": f"Call {target_kind} {target} · function {function_id} · priority {priority} · {mode}",
        target_key: target,
        "functionId": function_id,
        "priority": priority,
        "mode": mode,
    }


def decorate_call_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = call_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
