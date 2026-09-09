"""Proven fixed-width local script-memory operations for Chrono Trigger Steam.

These layouts come from Temporal Redux's event command table and constructors.
Only commands with explicit operand order/width and semantics are included.
Ambiguous bank-7F, extended-memory and uncertain-width operations stay out.
"""

from __future__ import annotations


U8 = 0xFF
U16 = 0xFFFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
MEMORY_OPCODES = frozenset({
    0x19, 0x1A,
    0x4F, 0x50, 0x51, 0x52,
    0x5B, 0x5D, 0x5E, 0x5F,
    0x71, 0x72, 0x73,
})


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
    if args is None:
        return None
    expected = {
        0x19: 1, 0x1A: 2,
        0x4F: 2, 0x50: 3, 0x51: 2, 0x52: 2,
        0x5B: 2, 0x5D: 2, 0x5E: 2, 0x5F: 2,
        0x71: 1, 0x72: 1, 0x73: 1,
    }.get(opcode)
    if expected is None or len(args) != expected:
        return None
    return opcode, args


def memory_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value = parsed
    address = lambda key, label: {
        "key": key, "label": label,
        "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST,
    }
    number = lambda key, label, maximum=U8: {
        "key": key, "label": label, "minimum": 0, "maximum": maximum,
    }

    if opcode == 0x19:
        return [address("storeAddress", "Store result at")]
    if opcode == 0x1A:
        return [number("resultValue", "Expected result"), number("jumpOffset", "Jump bytes if result differs")]
    if opcode in {0x4F, 0x50}:
        return [
            number("value", "Value", U8 if opcode == 0x4F else U16),
            address("storeAddress", "Store at"),
        ]
    if opcode in {0x51, 0x52}:
        return [address("sourceAddress", "Source address"), address("storeAddress", "Destination address")]
    if opcode in {0x5B, 0x5F}:
        return [number("value", "Value"), address("memoryAddress", "Memory address")]
    if opcode in {0x5D, 0x5E}:
        return [address("sourceAddress", "Add source address"), address("memoryAddress", "Add into address")]
    if opcode in {0x71, 0x72, 0x73}:
        return [address("memoryAddress", "Memory address")]
    return None


def memory_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    if opcode == 0x19:
        return {"storeAddress": _script_address(args[0])}
    if opcode == 0x1A:
        return {"resultValue": args[0], "jumpOffset": args[1]}
    if opcode == 0x4F:
        return {"value": args[0], "storeAddress": _script_address(args[1])}
    if opcode == 0x50:
        return {"value": int.from_bytes(args[:2], "little"), "storeAddress": _script_address(args[2])}
    if opcode in {0x51, 0x52}:
        return {"sourceAddress": _script_address(args[0]), "storeAddress": _script_address(args[1])}
    if opcode in {0x5B, 0x5F}:
        return {"value": args[0], "memoryAddress": _script_address(args[1])}
    if opcode in {0x5D, 0x5E}:
        return {"sourceAddress": _script_address(args[0]), "memoryAddress": _script_address(args[1])}
    if opcode in {0x71, 0x72, 0x73}:
        return {"memoryAddress": _script_address(args[0])}
    return None


def apply_memory_op(command: dict, values: dict) -> bytes | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    specs = memory_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    if opcode == 0x19:
        if "storeAddress" in values:
            args[0] = _script_offset(values["storeAddress"], "Store result address")
    elif opcode == 0x1A:
        if "resultValue" in values:
            args[0] = _int(values["resultValue"], 0, U8, "Expected result")
        if "jumpOffset" in values:
            args[1] = _int(values["jumpOffset"], 0, U8, "Jump bytes")
    elif opcode in {0x4F, 0x50}:
        if "value" in values:
            maximum = U8 if opcode == 0x4F else U16
            value = _int(values["value"], 0, maximum, "Value")
            if opcode == 0x4F:
                args[0] = value
            else:
                args[:2] = value.to_bytes(2, "little")
        if "storeAddress" in values:
            args[-1] = _script_offset(values["storeAddress"], "Store address")
    elif opcode in {0x51, 0x52}:
        if "sourceAddress" in values:
            args[0] = _script_offset(values["sourceAddress"], "Source address")
        if "storeAddress" in values:
            args[1] = _script_offset(values["storeAddress"], "Destination address")
    elif opcode in {0x5B, 0x5F}:
        if "value" in values:
            args[0] = _int(values["value"], 0, U8, "Value")
        if "memoryAddress" in values:
            args[1] = _script_offset(values["memoryAddress"], "Memory address")
    elif opcode in {0x5D, 0x5E}:
        if "sourceAddress" in values:
            args[0] = _script_offset(values["sourceAddress"], "Add source address")
        if "memoryAddress" in values:
            args[1] = _script_offset(values["memoryAddress"], "Add destination address")
    elif opcode in {0x71, 0x72, 0x73}:
        if "memoryAddress" in values:
            args[0] = _script_offset(values["memoryAddress"], "Memory address")
    return bytes(args)


def memory_semantics(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    if opcode == 0x19:
        address = _script_address(args[0])
        return {"summary": f"Result → 0x{address:06X}", "storeAddress": address}
    if opcode == 0x1A:
        return {
            "summary": f"Result must equal {args[0]} · mismatch → jump +{args[1]}",
            "resultValue": args[0], "jumpOffset": args[1], "jumpOnMismatch": True,
        }
    if opcode in {0x4F, 0x50}:
        width = 1 if opcode == 0x4F else 2
        value = args[0] if width == 1 else int.from_bytes(args[:2], "little")
        address = _script_address(args[-1])
        return {
            "summary": f"Store {width * 8}-bit {value} → 0x{address:06X}",
            "widthBytes": width, "value": value, "storeAddress": address,
        }
    if opcode in {0x51, 0x52}:
        width = 1 if opcode == 0x51 else 2
        source, dest = _script_address(args[0]), _script_address(args[1])
        return {
            "summary": f"Copy {width * 8}-bit 0x{source:06X} → 0x{dest:06X}",
            "widthBytes": width, "sourceAddress": source, "storeAddress": dest,
        }
    if opcode == 0x5B:
        address = _script_address(args[1])
        return {"summary": f"Add {args[0]} to 8-bit 0x{address:06X}", "widthBytes": 1, "value": args[0], "memoryAddress": address}
    if opcode in {0x5D, 0x5E}:
        width = 1 if opcode == 0x5D else 2
        source, dest = _script_address(args[0]), _script_address(args[1])
        return {
            "summary": f"Add {width * 8}-bit 0x{source:06X} into 0x{dest:06X}",
            "widthBytes": width, "sourceAddress": source, "memoryAddress": dest,
        }
    if opcode == 0x5F:
        address = _script_address(args[1])
        return {"summary": f"Subtract {args[0]} from 8-bit 0x{address:06X}", "widthBytes": 1, "value": args[0], "memoryAddress": address}
    if opcode in {0x71, 0x72}:
        width = 1 if opcode == 0x71 else 2
        address = _script_address(args[0])
        return {"summary": f"Increment {width * 8}-bit 0x{address:06X}", "widthBytes": width, "memoryAddress": address}
    if opcode == 0x73:
        address = _script_address(args[0])
        return {"summary": f"Decrement 8-bit 0x{address:06X}", "widthBytes": 1, "memoryAddress": address}
    return None


def decorate_memory_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = memory_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
