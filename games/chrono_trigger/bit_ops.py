"""Proven fixed-width local script-memory bit operations for Chrono Trigger Steam.

Temporal Redux explicitly documents the operand order for these commands and
constructs them against even script-memory addresses using the /2 slot encoding.
Bank-7F variants and the ambiguous 0x67 mask semantics remain intentionally out.
"""

from __future__ import annotations


U8 = 0xFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
BIT_OPCODES = frozenset({0x63, 0x64, 0x69, 0x6B, 0x6F})


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
    if opcode not in BIT_OPCODES or args is None or len(args) != 2:
        return None
    if opcode in {0x63, 0x64, 0x6F} and args[0] > 7:
        return None
    return opcode, args


def bit_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value = parsed
    address = {
        "key": "memoryAddress", "label": "Script-memory address",
        "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST,
    }
    if opcode in {0x63, 0x64}:
        return [address, {"key": "bitIndex", "label": "Bit index", "minimum": 0, "maximum": 7}]
    if opcode in {0x69, 0x6B}:
        return [address, {"key": "bitMask", "label": "Bit mask", "minimum": 0, "maximum": U8}]
    return [address, {"key": "shiftBits", "label": "Right shift bits", "minimum": 0, "maximum": 7}]


def bit_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    values = {"memoryAddress": _script_address(args[1])}
    if opcode in {0x63, 0x64}:
        values["bitIndex"] = args[0]
    elif opcode in {0x69, 0x6B}:
        values["bitMask"] = args[0]
    else:
        values["shiftBits"] = args[0]
    return values


def apply_bit_op(command: dict, values: dict) -> bytes | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    specs = bit_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if "memoryAddress" in values:
        args[1] = _script_offset(values["memoryAddress"], "Script-memory address")
    if opcode in {0x63, 0x64} and "bitIndex" in values:
        args[0] = _int(values["bitIndex"], 0, 7, "Bit index")
    elif opcode in {0x69, 0x6B} and "bitMask" in values:
        args[0] = _int(values["bitMask"], 0, U8, "Bit mask")
    elif opcode == 0x6F and "shiftBits" in values:
        args[0] = _int(values["shiftBits"], 0, 7, "Right shift bits")
    return bytes(args)


def bit_semantics(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    address = _script_address(args[1])
    if opcode == 0x63:
        return {"summary": f"Set bit {args[0]} in 0x{address:06X}", "memoryAddress": address, "bitIndex": args[0], "operation": "set-bit"}
    if opcode == 0x64:
        return {"summary": f"Reset bit {args[0]} in 0x{address:06X}", "memoryAddress": address, "bitIndex": args[0], "operation": "reset-bit"}
    if opcode == 0x69:
        return {"summary": f"Set bits 0x{args[0]:02X} in 0x{address:06X}", "memoryAddress": address, "bitMask": args[0], "operation": "set-mask"}
    if opcode == 0x6B:
        return {"summary": f"Toggle bits 0x{args[0]:02X} in 0x{address:06X}", "memoryAddress": address, "bitMask": args[0], "operation": "toggle-mask"}
    return {"summary": f"Shift 0x{address:06X} right by {args[0]} bit(s)", "memoryAddress": address, "shiftBits": args[0], "operation": "shift-right"}


def decorate_bit_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = bit_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
