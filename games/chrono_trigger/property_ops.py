"""Constructor-evidenced movement/destination property bits for Steam events.

Temporal Redux exposes two named low bits for 0x0D and 0x0E.  Lexeditor edits
only those bits and preserves every other raw flag bit unchanged; the upstream
command table itself still labels the remaining details unknown.
"""

from __future__ import annotations


PROPERTY_OPCODES = frozenset({0x0D, 0x0E})
_KNOWN_MASK = 0x03


def _args(command: dict) -> bytearray | None:
    if int(command["opcode"]) not in PROPERTY_OPCODES:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    return args if len(args) == 1 else None


def _bool(value, label: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{label} must be true or false")


def property_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    if int(command["opcode"]) == 0x0D:
        return [
            {"key": "throughWalls", "label": "Move through walls", "minimum": 0, "maximum": 1, "kind": "boolean"},
            {"key": "throughPCs", "label": "Move through PCs", "minimum": 0, "maximum": 1, "kind": "boolean"},
        ]
    return [
        {"key": "ontoTile", "label": "Destination onto tile", "minimum": 0, "maximum": 1, "kind": "boolean"},
        {"key": "ontoObject", "label": "Destination onto object", "minimum": 0, "maximum": 1, "kind": "boolean"},
    ]


def property_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    raw = args[0]
    if int(command["opcode"]) == 0x0D:
        return {"throughWalls": bool(raw & 0x01), "throughPCs": bool(raw & 0x02)}
    return {"ontoTile": bool(raw & 0x01), "ontoObject": bool(raw & 0x02)}


def apply_property_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    opcode = int(command["opcode"])
    specs = property_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0x{opcode:02X}: {', '.join(sorted(unknown))}")

    raw = args[0]
    if opcode == 0x0D:
        mapping = (("throughWalls", 0x01, "Move through walls"), ("throughPCs", 0x02, "Move through PCs"))
    else:
        mapping = (("ontoTile", 0x01, "Destination onto tile"), ("ontoObject", 0x02, "Destination onto object"))
    for key, bit, label in mapping:
        if key not in values:
            continue
        if _bool(values[key], label):
            raw |= bit
        else:
            raw &= ~bit
    args[0] = raw
    return bytes(args)


def property_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    raw = args[0]
    unknown = raw & ~_KNOWN_MASK
    if int(command["opcode"]) == 0x0D:
        enabled = []
        if raw & 0x01:
            enabled.append("through walls")
        if raw & 0x02:
            enabled.append("through PCs")
        base = "Movement properties" + (" · " + ", ".join(enabled) if enabled else " · known flags off")
        values = {"throughWalls": bool(raw & 0x01), "throughPCs": bool(raw & 0x02)}
    else:
        enabled = []
        if raw & 0x01:
            enabled.append("onto tile")
        if raw & 0x02:
            enabled.append("onto object")
        base = "Destination properties" + (" · " + ", ".join(enabled) if enabled else " · known flags off")
        values = {"ontoTile": bool(raw & 0x01), "ontoObject": bool(raw & 0x02)}
    if unknown:
        base += f" · unknown bits 0x{unknown:02X} preserved"
    return {"summary": base, "raw": raw, "unknownBits": unknown, **values}


def decorate_property_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = property_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
