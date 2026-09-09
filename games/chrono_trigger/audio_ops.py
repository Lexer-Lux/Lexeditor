"""Proven fixed-width Chrono Trigger Steam audio command editors.

Only 0xEB is handled here. Temporal Redux's command table and Sound menu agree
that it stores two one-byte operands: duration/speed-of-change, then volume.
0xEC remains intentionally excluded because its fixed table width conflicts
with subcommand-specific constructor argument counts.
"""

from __future__ import annotations


U8 = 0xFF
AUDIO_OPCODES = frozenset({0xEB})


def _args(command: dict) -> bytearray | None:
    if int(command["opcode"]) != 0xEB:
        return None
    try:
        args = bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None
    return args if len(args) == 2 else None


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def audio_field_specs(command: dict) -> list[dict] | None:
    if _args(command) is None:
        return None
    return [
        {"key": "duration", "label": "Volume change duration", "minimum": 0, "maximum": U8},
        {"key": "volume", "label": "Song volume (0xFF normal)", "minimum": 0, "maximum": U8},
    ]


def audio_values(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    return {"duration": args[0], "volume": args[1]}


def apply_audio_op(command: dict, values: dict) -> bytes | None:
    args = _args(command)
    if args is None:
        return None
    unknown = set(values) - {"duration", "volume"}
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0xEB: {', '.join(sorted(unknown))}")
    if "duration" in values:
        args[0] = _int(values["duration"], 0, U8, "Volume change duration")
    if "volume" in values:
        args[1] = _int(values["volume"], 0, U8, "Song volume")
    return bytes(args)


def audio_semantics(command: dict) -> dict | None:
    args = _args(command)
    if args is None:
        return None
    return {
        "summary": f"Song volume {args[1]} · change duration {args[0]}",
        "duration": args[0],
        "volume": args[1],
        "normalVolume": args[1] == 0xFF,
    }


def decorate_audio_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = audio_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
