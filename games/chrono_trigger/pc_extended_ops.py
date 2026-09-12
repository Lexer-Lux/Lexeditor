"""PC-only fixed-width extended-memory event editors for Chrono Trigger Steam.

Temporal Redux supplies explicit PC factories and PC width overrides for these
opcodes. Their one-byte local/extended operands are kept as raw slot numbers:
the upstream PC factories do not translate them through the regular 0x7F0200
script-memory /2 address helper, so Lexeditor does not invent that mapping.
"""

from __future__ import annotations

from .comparisons import OPERATION_NAMES


U8 = 0xFF
PC_EXTENDED_OPCODES = frozenset({0x3A, 0x3D, 0x3E, 0x45, 0x46, 0x6E, 0x70, 0x74, 0x78})


def _args(command: dict) -> bytearray | None:
    opcode = int(command["opcode"])
    if opcode not in PC_EXTENDED_OPCODES:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    expected = 4 if opcode == 0x6E else 2
    if len(args) != expected:
        return None
    if opcode == 0x6E and args[2] >= len(OPERATION_NAMES):
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


def pc_extended_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    opcode = int(command["opcode"])
    number = lambda key, label, maximum=U8: {"key": key, "label": label, "minimum": 0, "maximum": maximum}
    if opcode == 0x3A:
        return [number("value", "Immediate value"), number("extendedSlot", "Extended-memory slot (raw)")]
    if opcode in {0x3D, 0x78}:
        return [number("localSlot", "Local-memory slot (raw)"), number("extendedSlot", "Extended-memory slot (raw)")]
    if opcode in {0x3E, 0x74}:
        return [number("extendedSlot", "Extended-memory slot (raw)"), number("localSlot", "Local-memory slot (raw)")]
    if opcode in {0x45, 0x46}:
        return [number("bit", "Bit operand (raw)"), number("extendedSlot", "Extended-memory slot (raw)")]
    if opcode == 0x6E:
        return [
            number("extendedSlot", "Extended-memory slot (raw)"),
            number("value", "Comparison value"),
            number("operation", "Comparison operation (0–7)", 7),
            number("jumpOffset", "Jump bytes if false"),
        ]
    return [number("partySlot", "Party slot (raw)"), number("localSlot", "Local-memory slot (raw)")]


def pc_extended_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0x3A:
        return {"value": args[0], "extendedSlot": args[1]}
    if opcode in {0x3D, 0x78}:
        return {"localSlot": args[0], "extendedSlot": args[1]}
    if opcode in {0x3E, 0x74}:
        return {"extendedSlot": args[0], "localSlot": args[1]}
    if opcode in {0x45, 0x46}:
        return {"bit": args[0], "extendedSlot": args[1]}
    if opcode == 0x6E:
        return {
            "extendedSlot": args[0],
            "value": args[1],
            "operation": args[2],
            "jumpOffset": args[3],
        }
    return {"partySlot": args[0], "localSlot": args[1]}


def apply_pc_extended_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = pc_extended_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    for index, spec in enumerate(specs):
        key = spec["key"]
        if key in values:
            args[index] = _int(values[key], int(spec.get("minimum", 0)), int(spec.get("maximum", U8)), spec["label"])
    return bytes(args)


def pc_extended_semantics(command: dict) -> dict | None:
    values = pc_extended_values(command)
    if values is None:
        return None
    opcode = int(command["opcode"])
    if opcode == 0x3A:
        summary = f"PC Copy8 immediate {values['value']} → extended slot {values['extendedSlot']} (raw slots)"
        width = 1
    elif opcode == 0x3D:
        summary = f"PC Copy8 local slot {values['localSlot']} → extended slot {values['extendedSlot']} (raw slots)"
        width = 1
    elif opcode == 0x3E:
        summary = f"PC Copy8 extended slot {values['extendedSlot']} → local slot {values['localSlot']} (raw slots)"
        width = 1
    elif opcode == 0x45:
        summary = f"PC BitSet operand {values['bit']} on extended slot {values['extendedSlot']} (raw)"
        width = None
    elif opcode == 0x46:
        summary = f"PC BitClear operand {values['bit']} on extended slot {values['extendedSlot']} (raw)"
        width = None
    elif opcode == 0x6E:
        operation_name = OPERATION_NAMES[values["operation"]]
        summary = (
            f"PC Compare8 extended slot {values['extendedSlot']} {operation_name} {values['value']} "
            f"· false → jump +{values['jumpOffset']} (raw slot)"
        )
        return {
            "summary": summary,
            "widthBytes": 1,
            "pcOnly": True,
            "rawSlots": True,
            "operationName": operation_name,
            "jumpOnFalse": True,
            **values,
        }
    elif opcode == 0x70:
        summary = f"PC Copy8 party slot {values['partySlot']} → local slot {values['localSlot']} (raw slots)"
        width = 1
    elif opcode == 0x74:
        summary = f"PC Copy16 extended slot {values['extendedSlot']} → local slot {values['localSlot']} (raw slots)"
        width = 2
    else:
        summary = f"PC Copy16 local slot {values['localSlot']} → extended slot {values['extendedSlot']} (raw slots)"
        width = 2
    return {"summary": summary, "widthBytes": width, "pcOnly": True, "rawSlots": True, **values}


def decorate_pc_extended_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = pc_extended_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
