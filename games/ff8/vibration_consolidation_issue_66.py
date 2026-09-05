"""Remove FFNx's extra one-item vibration pause screen."""

from __future__ import annotations


DEFAULT_VIBRATION_CONSOLIDATION = False

# FFNx replaces FIELD_PATCHED_CALL and BATTLE_PATCHED_CALL after Hext loading.
# These hooks are earlier in each native control flow and do not overlap those
# later writes. They call the original game pause routines directly.
FIELD_HOOK = 0x0049A61E
FIELD_HOOK_ORIGINAL = bytes.fromhex("E8 2D 0B 00 00")
FIELD_PATCHED_CALL = 0x0049A628
FIELD_NATIVE_PREPARE = 0x0049B150
FIELD_NATIVE_PAUSE = 0x0049A350
FIELD_RETURN = 0x0049A62D

BATTLE_HOOK = 0x004C8D8F
BATTLE_HOOK_ORIGINAL = bytes.fromhex("83 C4 28 5F 50")
BATTLE_PATCHED_CALL = 0x004C8D95
BATTLE_NATIVE_PAUSE = 0x004C8DC0
BATTLE_RETURN = 0x004C8D9A

CODE_CAVE = 0x0279EEAC
FIELD_CAVE = CODE_CAVE
BATTLE_CAVE = CODE_CAVE + 0x20


def _rel32(opcode: int, source: int, target: int) -> bytes:
    displacement = (target - (source + 5)) & 0xFFFFFFFF
    return bytes((opcode,)) + displacement.to_bytes(4, "little")


def build_field_cave() -> bytes:
    payload = bytearray()
    payload += _rel32(0xE8, FIELD_CAVE + len(payload), FIELD_NATIVE_PREPARE)
    payload += bytes.fromhex("8B 44 24 08 50")
    payload += _rel32(0xE8, FIELD_CAVE + len(payload), FIELD_NATIVE_PAUSE)
    payload += _rel32(0xE9, FIELD_CAVE + len(payload), FIELD_RETURN)
    return bytes(payload)


def build_battle_cave() -> bytes:
    payload = bytearray.fromhex("83 C4 28 5F 50 55")
    payload += _rel32(0xE8, BATTLE_CAVE + len(payload), BATTLE_NATIVE_PAUSE)
    payload += _rel32(0xE9, BATTLE_CAVE + len(payload), BATTLE_RETURN)
    return bytes(payload)


CODE_CAVE_LENGTH = 0x20 + len(build_battle_cave())


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("Vibration Rationalization must be true or false")
    if not enabled:
        return ""
    field = build_field_cave()
    battle = build_battle_cave()
    field_hook = _rel32(0xE9, FIELD_HOOK, FIELD_CAVE)
    battle_hook = _rel32(0xE9, BATTLE_HOOK, BATTLE_CAVE)
    return "\n".join((
        "# Vibration Rationalization: bypass FFNx's extra field and battle pause screens.",
        "# The normal Config-menu vibration setting remains available.",
        f"{CODE_CAVE:X}:{CODE_CAVE_LENGTH:X}",
        f"{FIELD_HOOK:X} = {field_hook.hex(' ').upper()}",
        f"{BATTLE_HOOK:X} = {battle_hook.hex(' ').upper()}",
        f"{FIELD_CAVE:X} = {field.hex(' ').upper()}",
        f"{BATTLE_CAVE:X} = {battle.hex(' ').upper()}",
        "",
    ))
