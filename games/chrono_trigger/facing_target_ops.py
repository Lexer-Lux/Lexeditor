"""Proven target-facing editors for Chrono Trigger Steam field events.

Temporal Redux's live FaceObjectMenu and GetFacingMenu establish that 0xA8/0xA9
and 0x23/0x24 store target IDs doubled in one byte. Get-facing commands also
store their result through the ordinary one-byte /2 script-memory slot.
Malformed odd target bytes remain read-only rather than being rounded.
"""

from __future__ import annotations


U8 = 0xFF
TARGET_MAX = U8 // 2
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
FACING_TARGET_OPCODES = frozenset({0x23, 0x24, 0xA8, 0xA9})


def _args(command: dict) -> bytearray | None:
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    opcode = int(command["opcode"])
    expected = {0x23: 2, 0x24: 2, 0xA8: 1, 0xA9: 1}.get(opcode)
    if expected is None or len(args) != expected or args[0] & 1:
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


def _script_address(slot: int) -> int:
    return SCRIPT_MEM_START + int(slot) * 2


def _script_offset(value, label: str) -> int:
    address = _int(value, SCRIPT_MEM_START, SCRIPT_MEM_LAST, label)
    if (address - SCRIPT_MEM_START) % 2:
        raise ValueError(f"{label} must be an even script-memory address")
    return (address - SCRIPT_MEM_START) // 2


def _target_label(opcode: int) -> str:
    return "Player character" if opcode in {0x24, 0xA9} else "Object ID"


def facing_target_field_specs(command: dict) -> list[dict] | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    fields = [{
        "key": "targetId",
        "label": _target_label(opcode),
        "minimum": 0,
        "maximum": TARGET_MAX,
    }]
    if opcode in {0x23, 0x24}:
        fields.append({
            "key": "storeAddress",
            "label": "Store facing at",
            "minimum": SCRIPT_MEM_START,
            "maximum": SCRIPT_MEM_LAST,
        })
    return fields


def facing_target_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    values = {"targetId": args[0] // 2}
    if opcode in {0x23, 0x24}:
        values["storeAddress"] = _script_address(args[1])
    return values


def apply_facing_target_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = facing_target_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if "targetId" in values:
        args[0] = _int(values["targetId"], 0, TARGET_MAX, _target_label(opcode)) * 2
    if opcode in {0x23, 0x24} and "storeAddress" in values:
        args[1] = _script_offset(values["storeAddress"], "Facing destination")
    return bytes(args)


def facing_target_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    target_id = args[0] // 2
    is_pc = opcode in {0x24, 0xA9}
    target = "PC" if is_pc else "object"
    if opcode in {0x23, 0x24}:
        store_address = _script_address(args[1])
        return {
            "summary": f"Get {target} {target_id} facing → 0x{store_address:06X}",
            "targetId": target_id,
            "targetType": "pc" if is_pc else "object",
            "storeAddress": store_address,
            "operation": "get-facing",
        }
    return {
        "summary": f"Face {target} {target_id}",
        "targetId": target_id,
        "targetType": "pc" if is_pc else "object",
        "operation": "face-target",
    }


def decorate_facing_target_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = facing_target_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
