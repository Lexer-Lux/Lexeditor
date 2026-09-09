"""Proven fixed-width Steam field-event memory comparisons.

Temporal Redux's PC command definitions establish the four comparison layouts
handled here. This module deliberately excludes 0x16 because that command folds
bank-7F addressing state into the operator byte and is not equivalent to the
plain script-memory layouts below.
"""

from __future__ import annotations


U8 = 0xFF
U16 = 0xFFFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
OPERATION_NAMES = (
    "equals",
    "not equals",
    "greater than",
    "less than",
    "greater or equal",
    "less or equal",
    "bitwise AND nonzero",
    "bitwise OR nonzero",
)
COMPARISON_OPCODES = frozenset({0x12, 0x13, 0x14, 0x15})


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


def _layout(command: dict) -> tuple[int, bytearray, int] | None:
    opcode = int(command["opcode"])
    args = _args(command)
    if args is None:
        return None
    if opcode == 0x12 and len(args) == 4:
        operation_offset = 2
    elif opcode == 0x13 and len(args) == 5:
        operation_offset = 3
    elif opcode in {0x14, 0x15} and len(args) == 4:
        operation_offset = 2
    else:
        return None
    if args[operation_offset] >= len(OPERATION_NAMES):
        return None
    return opcode, args, operation_offset


def comparison_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value, _operation_offset = parsed
    if opcode in {0x12, 0x13}:
        value_max = U8 if opcode == 0x12 else U16
        return [
            {"key": "memoryAddress", "label": "Script-memory address", "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST},
            {"key": "value", "label": "Comparison value", "minimum": 0, "maximum": value_max},
            {"key": "operation", "label": "Comparison operation (0–7)", "minimum": 0, "maximum": 7},
            {"key": "jumpOffset", "label": "Jump bytes if false", "minimum": 0, "maximum": U8},
        ]
    return [
        {"key": "leftAddress", "label": "Left script-memory address", "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST},
        {"key": "rightAddress", "label": "Right script-memory address", "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST},
        {"key": "operation", "label": "Comparison operation (0–7)", "minimum": 0, "maximum": 7},
        {"key": "jumpOffset", "label": "Jump bytes if false", "minimum": 0, "maximum": U8},
    ]


def comparison_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args, operation_offset = parsed
    width = 2 if opcode in {0x13, 0x15} else 1
    if opcode == 0x12:
        value = args[1]
        return {
            "memoryAddress": _script_address(args[0]),
            "value": value,
            "operation": args[operation_offset],
            "jumpOffset": args[3],
        }
    if opcode == 0x13:
        value = int.from_bytes(args[1:3], "little")
        return {
            "memoryAddress": _script_address(args[0]),
            "value": value,
            "operation": args[operation_offset],
            "jumpOffset": args[4],
        }
    return {
        "leftAddress": _script_address(args[0]),
        "rightAddress": _script_address(args[1]),
        "operation": args[operation_offset],
        "jumpOffset": args[3],
        "widthBytes": width,
    }


def apply_comparison(command: dict, values: dict) -> bytes | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args, operation_offset = parsed
    if opcode in {0x12, 0x13}:
        allowed = {"memoryAddress", "value", "operation", "jumpOffset"}
    else:
        allowed = {"leftAddress", "rightAddress", "operation", "jumpOffset"}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if opcode in {0x12, 0x13}:
        if "memoryAddress" in values:
            args[0] = _script_offset(values["memoryAddress"], "Script-memory address")
        if "value" in values:
            maximum = U8 if opcode == 0x12 else U16
            value = _int(values["value"], 0, maximum, "Comparison value")
            if opcode == 0x12:
                args[1] = value
            else:
                args[1:3] = value.to_bytes(2, "little")
    else:
        if "leftAddress" in values:
            args[0] = _script_offset(values["leftAddress"], "Left script-memory address")
        if "rightAddress" in values:
            args[1] = _script_offset(values["rightAddress"], "Right script-memory address")
    if "operation" in values:
        args[operation_offset] = _int(values["operation"], 0, 7, "Comparison operation")
    if "jumpOffset" in values:
        args[-1] = _int(values["jumpOffset"], 0, U8, "Jump bytes")
    return bytes(args)


def comparison_semantics(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args, operation_offset = parsed
    width = 2 if opcode in {0x13, 0x15} else 1
    operation = args[operation_offset]
    operation_name = OPERATION_NAMES[operation]
    if opcode == 0x12:
        left = _script_address(args[0])
        value = args[1]
        jump = args[3]
        summary = f"8-bit 0x{left:06X} {operation_name} {value} · false → jump +{jump}"
        return {
            "summary": summary,
            "widthBytes": 1,
            "memoryAddress": left,
            "value": value,
            "operation": operation,
            "operationName": operation_name,
            "jumpOffset": jump,
            "jumpOnFalse": True,
        }
    if opcode == 0x13:
        left = _script_address(args[0])
        value = int.from_bytes(args[1:3], "little")
        jump = args[4]
        summary = f"16-bit 0x{left:06X} {operation_name} {value} · false → jump +{jump}"
        return {
            "summary": summary,
            "widthBytes": 2,
            "memoryAddress": left,
            "value": value,
            "operation": operation,
            "operationName": operation_name,
            "jumpOffset": jump,
            "jumpOnFalse": True,
        }
    left = _script_address(args[0])
    right = _script_address(args[1])
    jump = args[3]
    summary = f"{width * 8}-bit 0x{left:06X} {operation_name} 0x{right:06X} · false → jump +{jump}"
    return {
        "summary": summary,
        "widthBytes": width,
        "leftAddress": left,
        "rightAddress": right,
        "operation": operation,
        "operationName": operation_name,
        "jumpOffset": jump,
        "jumpOnFalse": True,
    }


def decorate_comparison_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = comparison_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
