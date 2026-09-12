"""Target-only editors for Chrono Trigger Steam event commands.

Some fixed-width opcodes have an explicitly documented /2 script-memory target
but unresolved operation details.  Lexeditor may safely retarget that operand
without claiming or rewriting the uncertain semantics:

- 0x67 has a raw mask byte whose reset/keep polarity conflicts upstream; only
  its second target byte is writable and the mask is preserved exactly.
- 0x75/0x76/0x77 have an explicit one-byte /2 target, while their set/reset
  value/width descriptions contain upstream question marks.  Only the target
  is exposed; the immutable opcode continues to define the unresolved action.
"""

from __future__ import annotations


U8 = 0xFF
SCRIPT_MEM_START = 0x7F0200
SCRIPT_MEM_LAST = SCRIPT_MEM_START + U8 * 2
TARGET_ONLY_OPCODES = frozenset({0x67, 0x75, 0x76, 0x77})


def _args(command: dict) -> bytearray | None:
    opcode = int(command["opcode"])
    if opcode not in TARGET_ONLY_OPCODES:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    expected = 2 if opcode == 0x67 else 1
    return args if len(args) == expected else None


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


def _script_offset(value) -> int:
    address = _int(value, SCRIPT_MEM_START, SCRIPT_MEM_LAST, "Target script-memory address")
    if (address - SCRIPT_MEM_START) % 2:
        raise ValueError("Target script-memory address must be an even script-memory address")
    return (address - SCRIPT_MEM_START) // 2


def _target_index(opcode: int) -> int:
    return 1 if opcode == 0x67 else 0


def target_only_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    return [{
        "key": "memoryAddress",
        "label": "Target script-memory address",
        "minimum": SCRIPT_MEM_START,
        "maximum": SCRIPT_MEM_LAST,
    }]


def target_only_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    return {"memoryAddress": _script_address(args[_target_index(opcode)])}


def apply_target_only_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    unknown = set(values) - {"memoryAddress"}
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if "memoryAddress" in values:
        args[_target_index(opcode)] = _script_offset(values["memoryAddress"])
    return bytes(args)


def target_only_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    address = _script_address(args[_target_index(opcode)])
    if opcode == 0x67:
        return {
            "summary": f"Reset-bits target 0x{address:06X} · raw mask 0x{args[0]:02X} preserved · mask polarity unresolved",
            "memoryAddress": address,
            "rawMask": args[0],
            "operationDetailsResolved": False,
            "targetOnly": True,
        }
    labels = {
        0x75: "Set-byte-8",
        0x76: "Set-byte-16",
        0x77: "Reset-byte",
    }
    return {
        "summary": f"{labels[opcode]} target 0x{address:06X} · action value semantics unresolved",
        "memoryAddress": address,
        "operationDetailsResolved": False,
        "targetOnly": True,
    }


def decorate_target_only_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = target_only_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
