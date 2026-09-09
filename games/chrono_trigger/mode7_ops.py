"""Read-only Mode 7 semantics for Chrono Trigger Steam field events.

Temporal Redux's live Mode7Menu establishes the current decoded shapes:
- scene mode: one scene byte in 0x00-0x89;
- specials 0x90 and 0x97: special byte + three raw parameter bytes;
- specials 0x91-0x96 and 0x98: special byte only.

Opcode 0xFF is dynamically sized in the PC command table. Lexeditor's shared
fixed-width writer deliberately rejects dynamic/unresolved opcodes, so this
module adds labels only and does not expose a writer even when a particular
current form has a known decoded size.
"""

from __future__ import annotations


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


def mode7_semantics(command: dict) -> dict | None:
    args = _raw_args(command)
    if args is None or not args:
        return None
    mode = args[0]
    if mode <= 0x89 and len(args) == 1:
        return {
            "summary": f"Mode 7 scene {mode}",
            "mode": "scene",
            "sceneId": mode,
            "readOnlyMode": True,
        }
    if mode in _PARAM_SPECIALS and len(args) == 4:
        return {
            "summary": f"Mode 7 special {_SPECIAL_NAMES[mode]} (0x{mode:02X}) · params {args[1]}, {args[2]}, {args[3]}",
            "mode": "special",
            "specialCode": mode,
            "param1": args[1],
            "param2": args[2],
            "param3": args[3],
            "readOnlyMode": True,
        }
    if mode in _SIMPLE_SPECIALS and len(args) == 1:
        return {
            "summary": f"Mode 7 special {_SPECIAL_NAMES[mode]} (0x{mode:02X})",
            "mode": "special",
            "specialCode": mode,
            "readOnlyMode": True,
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
