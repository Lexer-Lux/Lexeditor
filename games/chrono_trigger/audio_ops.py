"""Chrono Trigger Steam audio editors and read-only sound semantics.

0xEB is writable because Temporal Redux's command table and Sound menu agree
that it stores two one-byte operands: duration/speed-of-change, then volume.
0xEC remains intentionally read-only, but its live Sound-menu constructors
establish enough subcommand-specific boundaries/labels for safe diagnostics.
"""

from __future__ import annotations


U8 = 0xFF
AUDIO_OPCODES = frozenset({0xEB})
_EC_SPECS = {
    0x14: (2, "Interrupt and play song", ("songId",)),
    0x19: (2, "Play sound", ("soundId",)),
    0x82: (3, "Sound volume", ("duration", "volume")),
    0x83: (3, "Unknown sound operation", ("param1", "param2")),
    0x85: (3, "Song speed", ("duration", "speed")),
    0x86: (3, "Song speed", ("duration", "speed")),
    0x88: (1, "Change song state", ()),
    0xF0: (1, "Song to silence", ()),
    0xF2: (1, "Sound to silence", ()),
}


def _bytes(command: dict) -> bytearray | None:
    try:
        return bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None


def _eb_args(command: dict) -> bytearray | None:
    if int(command["opcode"]) != 0xEB:
        return None
    args = _bytes(command)
    return args if args is not None and len(args) == 2 else None


def _ec_args(command: dict) -> tuple[bytearray, tuple[int, str, tuple[str, ...]]] | None:
    if int(command["opcode"]) != 0xEC:
        return None
    args = _bytes(command)
    if not args:
        return None
    spec = _EC_SPECS.get(args[0])
    if spec is None or len(args) != spec[0]:
        return None
    return args, spec


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def audio_field_specs(command: dict) -> list[dict] | None:
    if _eb_args(command) is None:
        return None
    return [
        {"key": "duration", "label": "Volume change duration", "minimum": 0, "maximum": U8},
        {"key": "volume", "label": "Song volume (0xFF normal)", "minimum": 0, "maximum": U8},
    ]


def audio_values(command: dict) -> dict | None:
    args = _eb_args(command)
    if args is None:
        return None
    return {"duration": args[0], "volume": args[1]}


def apply_audio_op(command: dict, values: dict) -> bytes | None:
    args = _eb_args(command)
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
    eb = _eb_args(command)
    if eb is not None:
        return {
            "summary": f"Song volume {eb[1]} · change duration {eb[0]}",
            "duration": eb[0],
            "volume": eb[1],
            "normalVolume": eb[1] == 0xFF,
        }

    ec = _ec_args(command)
    if ec is None:
        return None
    args, spec = ec
    _width, label, param_names = spec
    subcommand = args[0]
    params = args[1:]
    values = {name: params[index] for index, name in enumerate(param_names)}
    suffix = ""
    if param_names:
        suffix = " · " + " · ".join(
            f"{name} {values[name]}" for name in param_names
        )
    return {
        "summary": f"EC/{subcommand:02X} {label}{suffix}",
        "subcommand": subcommand,
        "subcommandHex": f"0x{subcommand:02X}",
        "operation": label,
        "readOnly": True,
        **values,
    }


def decorate_audio_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = audio_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
