"""True ATB Wait for the supported FF8 2013 Steam English executable."""

from __future__ import annotations


DEFAULT_TRUE_ATB_WAIT = False

# FF8_EN.exe SHA-256 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570.
# The native ATB updater calls WAIT_PREDICATE before it advances any gauges.
# The replacement keeps that predicate and adds a three-party-member ready test.
ATB_WAIT_HOOK = 0x004842D1
ATB_WAIT_HOOK_ORIGINAL = bytes.fromhex("E8 7A 51 02 00")
WAIT_PREDICATE = 0x004A9450
CONFIG_ACCESSOR = 0x00403E00
CONFIG_FLAGS_OFFSET = 0x3AE
# The one configuration bit WAIT_PREDICATE itself consults; it treats the bit
# being clear as the waiting state.
ATB_WAIT_CONFIG_MASK = 0x10
PARTY_FLAGS = 0x01D27B8C
PARTICIPANT_STRIDE = 0xD0
PARTY_COUNT = 3
ACTIVE_AND_READY = 0x09
CODE_CAVE = 0x0279EF75


def _rel32(opcode: int, source: int, target: int) -> bytes:
    displacement = (target - (source + 5)) & 0xFFFFFFFF
    return bytes((opcode,)) + displacement.to_bytes(4, "little")


def build_code_cave() -> bytes:
    # Preserve every native stop condition, then add the requested stronger
    # rule. True ATB Wait is a Tweak, not a modification to the player's
    # Active/Wait configuration choice, so party readiness must stop gauges in
    # either configuration mode.
    #
    # if native_wait_predicate(): return 1
    # for the three party battle records:
    #     if active and ready: return 1
    # return 0
    payload = bytearray()
    payload += _rel32(0xE8, CODE_CAVE + len(payload), WAIT_PREDICATE)
    payload += bytes.fromhex("85 C0 75 1E")                # native stop -> return 1
    payload += b"\xB9" + PARTY_FLAGS.to_bytes(4, "little")
    payload += b"\xBA" + PARTY_COUNT.to_bytes(4, "little")
    payload += bytes.fromhex("8A 01 24 09 3C 09 74 0C")
    payload += bytes.fromhex("81 C1") + PARTICIPANT_STRIDE.to_bytes(4, "little")
    payload += bytes.fromhex("4A 75 EF 31 C0 C3 B8 01 00 00 00 C3")
    return bytes(payload)

CODE_CAVE_LENGTH = len(build_code_cave())


def build_hext(enabled: bool) -> str:
    if not isinstance(enabled, bool):
        raise ValueError("True ATB Wait must be true or false")
    if not enabled:
        return ""
    payload = build_code_cave()
    hook = _rel32(0xE8, ATB_WAIT_HOOK, CODE_CAVE)
    return "\n".join((
        "# True ATB Wait: extend the native Wait predicate with party readiness.",
        f"{CODE_CAVE:X}:{len(payload):X}",
        f"{ATB_WAIT_HOOK:X} = {hook.hex(' ').upper()}",
        f"{CODE_CAVE:X} = {payload.hex(' ').upper()}",
        "",
    ))
