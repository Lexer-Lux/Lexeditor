"""Named fixed-width editors for unconditional Chrono Trigger field jumps."""

from __future__ import annotations


JUMP_OPCODES = frozenset({0x10, 0x11})


def _args(command: dict) -> bytearray | None:
    try:
        data = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    if int(command["opcode"]) not in JUMP_OPCODES or len(data) != 1:
        return None
    return data


def jump_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    return [{"key": "jumpOffset", "label": "Jump bytes", "minimum": 0, "maximum": 0xFF}]


def jump_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    return {"jumpOffset": args[0]}


def apply_jump(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    unknown = set(values) - {"jumpOffset"}
    if unknown:
        opcode = int(command["opcode"])
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if "jumpOffset" in values:
        try:
            value = int(values["jumpOffset"])
        except (TypeError, ValueError) as error:
            raise ValueError("Jump bytes must be an integer") from error
        if not 0 <= value <= 0xFF:
            raise ValueError("Jump bytes must be between 0 and 255")
        args[0] = value
    return bytes(args)


def jump_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    direction = "forward" if opcode == 0x10 else "backward"
    sign = "+" if opcode == 0x10 else "-"
    return {
        "summary": f"Jump {direction} {sign}{args[0]}",
        "jumpOffset": args[0],
        "direction": direction,
    }


def decorate_jump_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = jump_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
