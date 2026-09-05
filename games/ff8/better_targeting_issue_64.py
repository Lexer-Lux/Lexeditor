"""Clear battle target indicators for the supported FF8 executable."""

from __future__ import annotations


DEFAULT_BETTER_TARGETING = False

# FF8_EN.exe SHA-256 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570.
# The native loop draws icon 15 (the red Target word) over each valid target.
# ESI is the candidate target index and SELECTED_TARGET is the current index.
# The wrapper skips every unselected candidate. For the selected candidate, it
# changes the icon argument to icon 0, marks that one call for the FFNx
# renderer, then tail-calls the original icon renderer entry.
TARGET_ICON_HOOK = 0x004AB0DC
TARGET_ICON_HOOK_ORIGINAL = bytes.fromhex("E8 CF C4 00 00")
ICON_RENDERER = 0x004B75B0
SELECTED_TARGET = 0x01D76844
OPAQUE_POINTER_ICON = 0
RED_TARGET_ICON = 15
# The marker made the selected-target wrapper eight bytes larger. Its old cave
# ended at 0279EF01 and collided with the shared reservation at 0279EF00. This
# free span ends before the next reservation at 0279F2F0.
CODE_CAVE = 0x0279F200
OPAQUE_TARGET_MARKER = 0x80000000

# FFNx replaces 004B75B0 at its entry with ff8_draw_icon_or_key1. Therefore,
# patching the native function body can never affect FFNx. Bit 31 of a6 is a
# safe call marker because FFNx masks a6 to 26 bits before it creates field_8.
# The derivative consumes the marker and suppresses the descriptor's bit-25
# contribution for this selected hand only.


def _rel32(opcode: int, source: int, target: int) -> bytes:
    displacement = (target - (source + 5)) & 0xFFFFFFFF
    return bytes((opcode,)) + displacement.to_bytes(4, "little")


def build_code_cave() -> bytes:
    payload = bytearray()
    payload += bytes.fromhex("0F B6 05") + SELECTED_TARGET.to_bytes(4, "little")
    payload += bytes.fromhex("39 F0 75 15")
    payload += bytes.fromhex("C7 44 24 10") + OPAQUE_POINTER_ICON.to_bytes(4, "little")
    payload += bytes.fromhex("81 4C 24 1C") + OPAQUE_TARGET_MARKER.to_bytes(4, "little")
    payload += _rel32(0xE9, CODE_CAVE + len(payload), ICON_RENDERER)
    payload += bytes.fromhex("8B 44 24 08 C3")
    return bytes(payload)


CODE_CAVE_LENGTH = len(build_code_cave())


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Better Targeting must be true or false")
    if not enabled:
        return ""
    payload = build_code_cave()
    hook = _rel32(0xE8, TARGET_ICON_HOOK, CODE_CAVE)
    return chr(10).join((
        "# Better Targeting: hide red Target words and draw one opaque hand pointer.",
        f"{CODE_CAVE:X}:{len(payload):X}",
        f"{TARGET_ICON_HOOK:X} = {hook.hex(' ').upper()}",
        f"{CODE_CAVE:X} = {payload.hex(' ').upper()}",
        "",
    ))
