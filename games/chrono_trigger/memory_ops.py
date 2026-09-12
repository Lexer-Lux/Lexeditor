"""Proven fixed-width memory operations for Chrono Trigger Steam.

These layouts come from Temporal Redux's event command table, constructors and
live menus. Ordinary script memory uses the even /2 slot model. Bank-7F forms
are enabled only where their encoded offset base and constructor range are
explicit; PC two-byte "segment address" forms remain excluded.
"""

from __future__ import annotations


U8 = 0xFF
U16 = 0xFFFF
BANK7F_START = 0x7F0000
BANK7F_LAST = 0x7FFFFF
BANK7F_RESULT_LAST = BANK7F_START + U8
BANK7F_LOCAL_LAST = 0x7F01FF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
MEMORY_OPCODES = frozenset({
    0x19, 0x1A, 0x1C,
    0x4F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x56, 0x58, 0x59,
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


def _bank_address(offset: int) -> int:
    return BANK7F_START + int(offset)


def _bank_offset(value, maximum: int, label: str) -> int:
    address = _int(value, BANK7F_START, maximum, label)
    return address - BANK7F_START


def _u16(args: bytearray, offset: int = 0) -> int:
    return int.from_bytes(args[offset:offset + 2], "little")


def _layout(command: dict) -> tuple[int, bytearray] | None:
    opcode = int(command["opcode"])
    args = _args(command)
    if args is None:
        return None
    expected = {
        0x19: 1, 0x1A: 2, 0x1C: 1,
        0x4F: 2, 0x50: 3, 0x51: 2, 0x52: 2,
        0x53: 3, 0x54: 3, 0x56: 3, 0x58: 3, 0x59: 3,
        0x5B: 2, 0x5D: 2, 0x5E: 2, 0x5F: 2,
        0x71: 1, 0x72: 1, 0x73: 1,
    }.get(opcode)
    if expected is None or len(args) != expected:
        return None
    # Temporal Redux's assign_mem_to_mem constructor uses 0x53/54 and 0x58/59
    # only for is_local_mem(), i.e. [0x7F0000, 0x7F0200). Do not promote wider
    # two-byte offsets merely because the command field can physically hold them.
    if opcode in {0x53, 0x54} and _u16(args) > (BANK7F_LOCAL_LAST - BANK7F_START):
        return None
    if opcode in {0x58, 0x59} and _u16(args, 1) > (BANK7F_LOCAL_LAST - BANK7F_START):
        return None
    return opcode, args


def memory_field_specs(command: dict) -> list[dict] | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, _args_value = parsed
    script_address = lambda key, label: {
        "key": key, "label": label,
        "minimum": SCRIPT_MEM_START, "maximum": SCRIPT_MEM_LAST,
    }
    bank_local_address = lambda key, label: {
        "key": key, "label": label,
        "minimum": BANK7F_START, "maximum": BANK7F_LOCAL_LAST,
    }
    number = lambda key, label, maximum=U8: {
        "key": key, "label": label, "minimum": 0, "maximum": maximum,
    }

    if opcode == 0x19:
        return [script_address("storeAddress", "Store result at")]
    if opcode == 0x1C:
        return [{
            "key": "storeAddress", "label": "Store result at (bank 7F)",
            "minimum": BANK7F_START, "maximum": BANK7F_RESULT_LAST,
        }]
    if opcode == 0x1A:
        return [number("resultValue", "Expected result"), number("jumpOffset", "Jump bytes if result differs")]
    if opcode in {0x4F, 0x50}:
        return [
            number("value", "Value", U8 if opcode == 0x4F else U16),
            script_address("storeAddress", "Store at"),
        ]
    if opcode in {0x51, 0x52}:
        return [script_address("sourceAddress", "Source address"), script_address("storeAddress", "Destination address")]
    if opcode in {0x53, 0x54}:
        return [bank_local_address("sourceAddress", "Bank-7F source"), script_address("storeAddress", "Script-memory destination")]
    if opcode == 0x56:
        return [
            number("value", "Value"),
            {"key": "storeAddress", "label": "Bank-7F destination", "minimum": BANK7F_START, "maximum": BANK7F_LAST},
        ]
    if opcode in {0x58, 0x59}:
        return [script_address("sourceAddress", "Script-memory source"), bank_local_address("storeAddress", "Bank-7F destination")]
    if opcode in {0x5B, 0x5F}:
        return [number("value", "Value"), script_address("memoryAddress", "Memory address")]
    if opcode in {0x5D, 0x5E}:
        return [script_address("sourceAddress", "Add source address"), script_address("memoryAddress", "Add into address")]
    if opcode in {0x71, 0x72, 0x73}:
        return [script_address("memoryAddress", "Memory address")]
    return None


def memory_values(command: dict) -> dict | None:
    parsed = _layout(command)
    if parsed is None:
        return None
    opcode, args = parsed
    if opcode == 0x19:
        return {"storeAddress": _script_address(args[0])}
    if opcode == 0x1C:
        return {"storeAddress": _bank_address(args[0])}
    if opcode == 0x1A:
        return {"resultValue": args[0], "jumpOffset": args[1]}
    if opcode == 0x4F:
        return {"value": args[0], "storeAddress": _script_address(args[1])}
    if opcode == 0x50:
        return {"value": _u16(args), "storeAddress": _script_address(args[2])}
    if opcode in {0x51, 0x52}:
        return {"sourceAddress": _script_address(args[0]), "storeAddress": _script_address(args[1])}
    if opcode in {0x53, 0x54}:
        return {"sourceAddress": _bank_address(_u16(args)), "storeAddress": _script_address(args[2])}
    if opcode == 0x56:
        return {"value": args[0], "storeAddress": _bank_address(_u16(args, 1))}
    if opcode in {0x58, 0x59}:
        return {"sourceAddress": _script_address(args[0]), "storeAddress": _bank_address(_u16(args, 1))}
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
    elif opcode == 0x1C:
        if "storeAddress" in values:
            args[0] = _bank_offset(values["storeAddress"], BANK7F_RESULT_LAST, "Bank-7F result address")
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
    elif opcode in {0x53, 0x54}:
        if "sourceAddress" in values:
            offset = _bank_offset(values["sourceAddress"], BANK7F_LOCAL_LAST, "Bank-7F source")
            args[:2] = offset.to_bytes(2, "little")
        if "storeAddress" in values:
            args[2] = _script_offset(values["storeAddress"], "Script-memory destination")
    elif opcode == 0x56:
        if "value" in values:
            args[0] = _int(values["value"], 0, U8, "Value")
        if "storeAddress" in values:
            offset = _bank_offset(values["storeAddress"], BANK7F_LAST, "Bank-7F destination")
            args[1:3] = offset.to_bytes(2, "little")
    elif opcode in {0x58, 0x59}:
        if "sourceAddress" in values:
            args[0] = _script_offset(values["sourceAddress"], "Script-memory source")
        if "storeAddress" in values:
            offset = _bank_offset(values["storeAddress"], BANK7F_LOCAL_LAST, "Bank-7F destination")
            args[1:3] = offset.to_bytes(2, "little")
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
    if opcode == 0x1C:
        address = _bank_address(args[0])
        return {
            "summary": f"Result → 0x{address:06X} (bank 7F)",
            "storeAddress": address,
            "addressMode": "bank7f-byte-offset",
        }
    if opcode == 0x1A:
        return {
            "summary": f"Result must equal {args[0]} · mismatch → jump +{args[1]}",
            "resultValue": args[0], "jumpOffset": args[1], "jumpOnMismatch": True,
        }
    if opcode in {0x4F, 0x50}:
        width = 1 if opcode == 0x4F else 2
        value = args[0] if width == 1 else _u16(args)
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
    if opcode in {0x53, 0x54}:
        width = 1 if opcode == 0x53 else 2
        source, dest = _bank_address(_u16(args)), _script_address(args[2])
        return {
            "summary": f"Copy {width * 8}-bit bank-7F 0x{source:06X} → script 0x{dest:06X}",
            "widthBytes": width, "sourceAddress": source, "storeAddress": dest,
            "sourceMode": "bank7f-local-offset",
        }
    if opcode == 0x56:
        dest = _bank_address(_u16(args, 1))
        return {
            "summary": f"Store 8-bit {args[0]} → bank-7F 0x{dest:06X}",
            "widthBytes": 1, "value": args[0], "storeAddress": dest,
            "addressMode": "bank7f-u16-offset",
        }
    if opcode in {0x58, 0x59}:
        width = 1 if opcode == 0x58 else 2
        source, dest = _script_address(args[0]), _bank_address(_u16(args, 1))
        return {
            "summary": f"Copy {width * 8}-bit script 0x{source:06X} → bank-7F 0x{dest:06X}",
            "widthBytes": width, "sourceAddress": source, "storeAddress": dest,
            "destinationMode": "bank7f-local-offset",
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
