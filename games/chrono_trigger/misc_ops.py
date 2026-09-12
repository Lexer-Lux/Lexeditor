"""Small proven fixed-width Chrono Trigger Steam event operands.

This module collects one-byte commands whose constructor/table evidence is
explicit but which do not warrant a larger subsystem.  It intentionally does
not absorb neighboring opcodes with ambiguous target/address semantics.
"""

from __future__ import annotations


U8 = 0xFF
MISC_OPCODES = frozenset({0x29, 0x82, 0xC8})


def _args(command: dict) -> bytearray | None:
    opcode = int(command["opcode"])
    if opcode not in MISC_OPCODES:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    if len(args) != 1:
        return None
    # Temporal Redux constructs Load ASCII as index | 0x80 and its command
    # table describes the stored value as an index +0x80.  Do not normalize a
    # noncanonical byte whose high bit is clear.
    if opcode == 0x29 and not (args[0] & 0x80):
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


def misc_field_specs(command: dict) -> list[dict] | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0x29:
        return [{"key": "asciiIndex", "label": "ASCII text index", "minimum": 0, "maximum": 0x7F}]
    if opcode == 0x82:
        return [{"key": "npcId", "label": "NPC ID", "minimum": 0, "maximum": U8}]
    return [{"key": "dialogId", "label": "Special dialog ID (raw)", "minimum": 0, "maximum": U8}]


def misc_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0x29:
        return {"asciiIndex": args[0] & 0x7F}
    if opcode == 0x82:
        return {"npcId": args[0]}
    return {"dialogId": args[0]}


def apply_misc_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = misc_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if opcode == 0x29 and "asciiIndex" in values:
        args[0] = _int(values["asciiIndex"], 0, 0x7F, "ASCII text index") | 0x80
    elif opcode == 0x82 and "npcId" in values:
        args[0] = _int(values["npcId"], 0, U8, "NPC ID")
    elif opcode == 0xC8 and "dialogId" in values:
        args[0] = _int(values["dialogId"], 0, U8, "Special dialog ID")
    return bytes(args)


def misc_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0x29:
        index = args[0] & 0x7F
        return {"summary": f"Load ASCII text index {index}", "asciiIndex": index, "storedByte": args[0]}
    if opcode == 0x82:
        return {"summary": f"Load NPC {args[0]}", "npcId": args[0]}
    return {"summary": f"Special dialog 0x{args[0]:02X} (raw)", "dialogId": args[0]}


def decorate_misc_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = misc_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
