"""Width-stable Mode 7 event editors for Chrono Trigger Steam.

Temporal Redux's live Mode7Menu establishes two shapes that can be edited
without moving command boundaries:
- scene mode: one scene byte in 0x00-0x89;
- specials 0x90 and 0x97: immutable special byte + three raw parameter bytes.

Other one-byte specials (0x91-0x96, 0x98) have no payload beyond the mode byte.
Lexeditor leaves those read-only rather than allowing a mode change that could
switch the command to a different encoded width.
"""

from __future__ import annotations


U8 = 0xFF
MODE7_OPCODE = 0xFF
_SPECIAL_NAMES = {
    0x90: "Black Circle",
    0x91: "Mode 91",
    0x92: "Left-Right Swipe Open",
    0x93: "Right-Left Swipe Open",
    0x94: "Left-Right Swipe Close",
    0x95: "Right-Left Swipe Close",
    0x96: "Reset",
    0x97: "Mode 97",
    0x98: "Mode 98",
}
_PARAM_SPECIALS = frozenset({0x90, 0x97})
_SIMPLE_SPECIALS = frozenset(set(_SPECIAL_NAMES) - set(_PARAM_SPECIALS))


def _raw_args(command: dict) -> bytearray | None:
    if int(command.get("opcode", -1)) != MODE7_OPCODE:
        return None
    try:
        return bytearray.fromhex(command.get("argumentsHex", ""))
    except ValueError:
        return None


def _editable_layout(command: dict) -> tuple[str, bytearray] | None:
    args = _raw_args(command)
    if args is None or not args:
        return None
    mode = args[0]
    if mode <= 0x89 and len(args) == 1:
        return "scene", args
    if mode in _PARAM_SPECIALS and len(args) == 4:
        return "special-params", args
    return None


def _int(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def mode7_field_specs(command: dict) -> list[dict] | None:
    parsed = _editable_layout(command)
    if parsed is None:
        return None
    kind, _args = parsed
    if kind == "scene":
        return [{"key": "sceneId", "label": "Mode 7 scene", "minimum": 0, "maximum": 0x89}]
    return [
        {"key": "param1", "label": "Special parameter 1", "minimum": 0, "maximum": U8},
        {"key": "param2", "label": "Special parameter 2", "minimum": 0, "maximum": U8},
        {"key": "param3", "label": "Special parameter 3", "minimum": 0, "maximum": U8},
    ]


def mode7_values(command: dict) -> dict | None:
    parsed = _editable_layout(command)
    if parsed is None:
        return None
    kind, args = parsed
    if kind == "scene":
        return {"sceneId": args[0]}
    return {"param1": args[1], "param2": args[2], "param3": args[3]}


def apply_mode7_op(command: dict, values: dict) -> bytes | None:
    parsed = _editable_layout(command)
    if parsed is None:
        return None
    kind, args = parsed
    specs = mode7_field_specs(command) or []
    allowed = {spec["key"] for spec in specs}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown fields for opcode 0xFF: {', '.join(sorted(unknown))}")

    if kind == "scene":
        if "sceneId" in values:
            args[0] = _int(values["sceneId"], 0, 0x89, "Mode 7 scene")
    else:
        for index, key in enumerate(("param1", "param2", "param3"), start=1):
            if key in values:
                args[index] = _int(values[key], 0, U8, f"Special parameter {index}")
    return bytes(args)


def mode7_semantics(command: dict) -> dict | None:
    args = _raw_args(command)
    if args is None or not args:
        return None
    mode = args[0]
    if mode <= 0x89 and len(args) == 1:
        return {"summary": f"Mode 7 scene {mode}", "mode": "scene", "sceneId": mode}
    if mode in _PARAM_SPECIALS and len(args) == 4:
        return {
            "summary": f"Mode 7 special {_SPECIAL_NAMES[mode]} (0x{mode:02X}) · params {args[1]}, {args[2]}, {args[3]}",
            "mode": "special", "specialCode": mode,
            "param1": args[1], "param2": args[2], "param3": args[3],
        }
    if mode in _SIMPLE_SPECIALS and len(args) == 1:
        return {
            "summary": f"Mode 7 special {_SPECIAL_NAMES[mode]} (0x{mode:02X})",
            "mode": "special", "specialCode": mode, "readOnlyMode": True,
        }
    return None


def decorate_mode7_semantics(payload: dict) -> dict:
    for obj in payload.get("objects", []):
        for function in obj.get("functions", []):
            for command in function.get("commands", []):
                semantic = mode7_semantics(command)
                if semantic is not None:
                    command["semantic"] = semantic
    return payload
