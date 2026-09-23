"""Issue-local FF8 patch for the Single GF setting.

The add hook runs only on the Junction menu's verified add path. When Single GF
is enabled, it allows the first GF and refuses a different GF while the selected
character's proposed mask is nonzero. The field and world-map entry hooks also
normalize an existing save: a character with several GFs loses the complete GF
mask instead of keeping an invalid, arbitrary GF.
"""

from __future__ import annotations


SUPPORTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
DEFAULT_SINGLE_GF = False

ADD_GATE_HOOK = 0x004DF5D0
ADD_GATE_OR = 0x004DF5D8
ADD_GATE_SKIP = 0x004DF698
ADD_GATE_ORIGINAL = bytes.fromhex("85 D0 0F 85 C0 00 00 00")
ADD_GATE_HOOK_LENGTH = len(ADD_GATE_ORIGINAL)

DEFAULT_CODE_CAVE = 0x0279F000
CODE_CAVE_LENGTH = 0x15

# Official FFNx resolves these callbacks from the game's main mode dispatcher.
# They run on field and world-map transitions, after a loaded savemap is active.
FIELD_ENTER_HOOK = 0x0046FD70
FIELD_ENTER_ORIGINAL = bytes.fromhex("8B 44 24 04 53")
WORLDMAP_ENTER_HOOK = 0x0053EFC0
WORLDMAP_ENTER_ORIGINAL = bytes.fromhex("56 68 00 80 3E 40")
SAVEMAP_CHARACTER_BASE = 0x01CFE0E8
SAVEMAP_CHARACTER_STRIDE = 0x98
GF_MASK_OFFSET = 0x58
CHARACTER_COUNT = 8

# This range follows the issue-52 state block and does not overlap another
# registered FF8 gameplay component.
FIELD_ENTER_CAVE = 0x027A0520
WORLDMAP_ENTER_CAVE = 0x027A0540
NORMALIZE_CAVE = 0x027A0560
FIELD_ENTER_CAVE_LENGTH = 0x13
WORLDMAP_ENTER_CAVE_LENGTH = 0x14
NORMALIZE_CAVE_LENGTH = 0x27


def boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("Single GF must be true or false")
    return value


def allows_add(current_mask: int, gf_index: int, enabled: bool) -> bool:
    """Mirror the patch policy for UI explanations and mutation checks."""
    enabled = boolean(enabled)
    if not 0 <= int(gf_index) < 16:
        raise ValueError("GF index must be from 0 to 15")
    mask = int(current_mask) & 0xFFFF
    bit = 1 << int(gf_index)
    return not enabled or bool(mask & bit) or mask == 0


def normalize_masks(masks: list[int] | tuple[int, ...]) -> list[int]:
    """Clear each invalid multi-GF mask and preserve zero or one-hot masks."""
    if len(masks) != CHARACTER_COUNT:
        raise ValueError(f"Single GF needs exactly {CHARACTER_COUNT} character masks")
    normalized = []
    for value in masks:
        mask = int(value) & 0xFFFF
        normalized.append(0 if mask and mask & (mask - 1) else mask)
    return normalized


def _relative_branch(opcode: bytes, source: int, target: int) -> bytes:
    displacement = target - (source + len(opcode) + 4)
    return opcode + int(displacement).to_bytes(4, "little", signed=True)


def build_code_cave(code_cave: int = DEFAULT_CODE_CAVE) -> bytes:
    """Build the add-only Single GF gate for one assigned code cave."""
    cursor = int(code_cave)
    payload = bytearray()
    payload.extend(bytes.fromhex("85 D0"))
    payload.extend(_relative_branch(b"\x0F\x85", cursor + len(payload), ADD_GATE_SKIP))
    payload.extend(bytes.fromhex("85 D2"))
    payload.extend(_relative_branch(b"\x0F\x85", cursor + len(payload), ADD_GATE_SKIP))
    payload.extend(_relative_branch(b"\xE9", cursor + len(payload), ADD_GATE_OR))
    if len(payload) != CODE_CAVE_LENGTH:
        raise AssertionError("Single GF code-cave payload length changed")
    return bytes(payload)


def build_normalize_cave() -> bytes:
    """Build the transition-scoped existing-save mask normalizer."""
    payload = bytes.fromhex(
        "BF" + (SAVEMAP_CHARACTER_BASE + GF_MASK_OFFSET).to_bytes(4, "little").hex() +
        "B9" + CHARACTER_COUNT.to_bytes(4, "little").hex() +
        "0F B7 07"      # movzx eax, word ptr [edi]
        "85 C0"         # test eax, eax
        "74 0C"         # zero is valid
        "8D 50 FF"      # lea edx, [eax-1]
        "85 D0"         # test eax, edx
        "74 05"         # one-hot is valid
        "66 C7 07 00 00"  # clear the complete GF mask
        "81 C7 98 00 00 00"
        "49"
        "75 E4"
        "C3"
    )
    if len(payload) != NORMALIZE_CAVE_LENGTH:
        raise AssertionError("Single GF normalizer length changed")
    return payload


def build_entry_cave(address: int, hook: int, original: bytes) -> bytes:
    """Call the common normalizer, replay one verified callback prologue, return."""
    payload = bytearray(bytes.fromhex("9C 60"))  # pushfd; pushad
    payload.extend(_relative_branch(b"\xE8", address + len(payload), NORMALIZE_CAVE))
    payload.extend(bytes.fromhex("61 9D"))  # popad; popfd
    payload.extend(original)
    payload.extend(_relative_branch(b"\xE9", address + len(payload), hook + len(original)))
    return bytes(payload)


def build_hext(enabled: bool, code_cave: int = DEFAULT_CODE_CAVE) -> str:
    """Return this issue's FFNx Hext fragment, or nothing when disabled."""
    enabled = boolean(enabled)
    if not enabled:
        return ""
    cave = build_code_cave(code_cave)
    field_cave = build_entry_cave(FIELD_ENTER_CAVE, FIELD_ENTER_HOOK, FIELD_ENTER_ORIGINAL)
    world_cave = build_entry_cave(WORLDMAP_ENTER_CAVE, WORLDMAP_ENTER_HOOK, WORLDMAP_ENTER_ORIGINAL)
    if len(field_cave) != FIELD_ENTER_CAVE_LENGTH or len(world_cave) != WORLDMAP_ENTER_CAVE_LENGTH:
        raise AssertionError("Single GF entry-cave length changed")
    normalizer = build_normalize_cave()
    hook = _relative_branch(b"\xE9", ADD_GATE_HOOK, int(code_cave))
    hook += b"\x90" * (ADD_GATE_HOOK_LENGTH - len(hook))
    field_hook = _relative_branch(b"\xE9", FIELD_ENTER_HOOK, FIELD_ENTER_CAVE)
    world_hook = _relative_branch(b"\xE9", WORLDMAP_ENTER_HOOK, WORLDMAP_ENTER_CAVE)
    world_hook += b"\x90" * (len(WORLDMAP_ENTER_ORIGINAL) - len(world_hook))
    return "\n".join([
        "# Single GF: enabled",
        f"{int(code_cave):X}:{CODE_CAVE_LENGTH:X}",
        f"{FIELD_ENTER_CAVE:X}:{FIELD_ENTER_CAVE_LENGTH:X}",
        f"{WORLDMAP_ENTER_CAVE:X}:{WORLDMAP_ENTER_CAVE_LENGTH:X}",
        f"{NORMALIZE_CAVE:X}:{NORMALIZE_CAVE_LENGTH:X}",
        f"{ADD_GATE_HOOK:X} = {hook.hex(' ').upper()}",
        f"{FIELD_ENTER_HOOK:X} = {field_hook.hex(' ').upper()}",
        f"{WORLDMAP_ENTER_HOOK:X} = {world_hook.hex(' ').upper()}",
        f"{int(code_cave):X} = {cave.hex(' ').upper()}",
        f"{FIELD_ENTER_CAVE:X} = {field_cave.hex(' ').upper()}",
        f"{WORLDMAP_ENTER_CAVE:X} = {world_cave.hex(' ').upper()}",
        f"{NORMALIZE_CAVE:X} = {normalizer.hex(' ').upper()}",
        "",
    ])
