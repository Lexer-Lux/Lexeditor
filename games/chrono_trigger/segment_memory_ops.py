"""Fixed-width PC segment-memory operands for Chrono Trigger Steam events.

Temporal Redux's Platform.PC width overrides replace the SNES 24-bit address
in opcodes 0x48-0x4D with a two-byte segment address.  The public evidence does
not establish a reversible full PC RAM address mapping, so Lexeditor exposes
that u16 segment value and the one-byte local operand as raw fields only.
"""

from __future__ import annotations


U8 = 0xFF
U16 = 0xFFFF
SEGMENT_MEMORY_OPCODES = frozenset({0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D})


def _args(command: dict) -> bytearray | None:
    opcode = int(command["opcode"])
    if opcode not in SEGMENT_MEMORY_OPCODES:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    expected = 4 if opcode == 0x4B else 3
    return args if len(args) == expected else None


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _segment(args: bytes) -> int:
    return int.from_bytes(args[:2], "little")


def segment_memory_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    opcode = int(command["opcode"])
    segment_label = "PC segment source (raw)" if opcode in {0x48, 0x49} else "PC segment destination (raw)"
    segment = {"key": "segment", "label": segment_label, "minimum": 0, "maximum": U16}
    if opcode in {0x48, 0x49}:
        return [segment, {"key": "localSlot", "label": "Local destination slot (raw)", "minimum": 0, "maximum": U8}]
    if opcode == 0x4A:
        return [segment, {"key": "value", "label": "8-bit value", "minimum": 0, "maximum": U8}]
    if opcode == 0x4B:
        return [segment, {"key": "value", "label": "16-bit value", "minimum": 0, "maximum": U16}]
    return [segment, {"key": "localSlot", "label": "Local source slot (raw)", "minimum": 0, "maximum": U8}]


def segment_memory_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    values = {"segment": _segment(args)}
    if opcode == 0x4B:
        values["value"] = int.from_bytes(args[2:4], "little")
    elif opcode == 0x4A:
        values["value"] = args[2]
    else:
        values["localSlot"] = args[2]
    return values


def apply_segment_memory_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = segment_memory_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")
    if "segment" in values:
        args[:2] = _int(values["segment"], 0, U16, "PC segment").to_bytes(2, "little")
    if opcode == 0x4B:
        if "value" in values:
            args[2:4] = _int(values["value"], 0, U16, "16-bit value").to_bytes(2, "little")
    elif opcode == 0x4A:
        if "value" in values:
            args[2] = _int(values["value"], 0, U8, "8-bit value")
    elif "localSlot" in values:
        args[2] = _int(values["localSlot"], 0, U8, "Local slot")
    return bytes(args)


def segment_memory_semantics(command: dict) -> dict | None:
    values = segment_memory_values(command)
    if values is None:
        return None
    opcode = int(command["opcode"])
    width = 2 if opcode in {0x49, 0x4B, 0x4D} else 1
    segment = values["segment"]
    if opcode in {0x48, 0x49}:
        summary = f"PC Copy{width * 8} raw segment 0x{segment:04X} → local slot {values['localSlot']} (raw)"
    elif opcode in {0x4A, 0x4B}:
        summary = f"PC Store{width * 8} value {values['value']} → raw segment 0x{segment:04X}"
    else:
        summary = f"PC Copy{width * 8} local slot {values['localSlot']} → raw segment 0x{segment:04X}"
    return {
        "summary": summary,
        "widthBytes": width,
        "pcSegmentRaw": True,
        "fullAddressKnown": False,
        **values,
    }


def decorate_segment_memory_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = segment_memory_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
