"""Timed Hits and Timed Blocks for every character (#482, #483), as Hext.

Lexer's rule (2026-09-27): one timing system for everyone, Squall included.
The hit moment is when the game applies a hit's damage. Press Square within the
window before it lands and a party member's hit on an enemy gets the bonus
multiplier; an enemy's hit on a party member is reduced instead. A press that
is too early plays the failure sound; a timed one plays the success sound.

Against FF8_EN.exe SHA-256 064d466b...9570 (see codex/ff8/timed-hits.md):

- Presses: the battle input routine 004A84E0 stores this frame's newly
  pressed buttons at [01D6D490] + 0x12 (FF8's own layout, after the
  translator 004A2D60 that Modern Controls hooks). The hook at 004A8554,
  after those calls, records timeGetTime (import 00B69378) when bit 0x80
  (Square) is newly pressed. It was R1 (0x08, the bit Squall's trigger
  tests), but R1 is also Look Right, which Universal Item turns into the
  Item menu, and Modern Controls feeds the right trigger into that bit.
- Hits: 0048FE20(target) works out and applies one hit, mid-animation. At
  00491124, just before the damage cap, ESI is the hit's damage, the attacker
  is byte 01D27AD8 and [esp+0x10] is the target x 0xD0. The hook scales ESI
  when the last press is inside the window, then lets the cap run as usual.
- A press counts for one hit: it is used up by the first hit it affects.
- Physical only (option, off by default): 004922B0(type, ...) works out one
  hit's damage by attack type and is called from 0048FE20 before the hook.
  Its entry records the type; the hit hook then ignores (without using up
  the press) every type but Physical Attack 1, % Physical Damage 7,
  Renzokuken Finisher 9, Squall Gunblade Attack 10 and Physical Attack
  (Ignore Target VIT) 36, the kernel's attack_type values.
- Squall's own gunblade trigger bonus is switched off so he uses the same
  window: the two stores to its quality word 01D28D94 (00485158, 004851D6)
  no longer write, so it stays 0 and the gunblade factor is 1.
- Sounds play through 0046B280(sound), the game's own sound-effect call that
  its menus use; the number is the audio.fmt index shown on the SFX tab.
"""

from __future__ import annotations

DEFAULT_TIMED_HITS = False
DEFAULT_WINDOW_MS = 250
MIN_WINDOW_MS = 50
MAX_WINDOW_MS = 600
DEFAULT_BONUS_PERCENT = 150
MIN_BONUS_PERCENT = 100
MAX_BONUS_PERCENT = 300
DEFAULT_BLOCK_PERCENT = 50  # share of the damage a timed block still takes
MIN_BLOCK_PERCENT = 0
MAX_BLOCK_PERCENT = 100
DEFAULT_SUCCESS_SOUND = 1   # the menu confirm sound (menu sounds 1 and 2)
DEFAULT_FAILURE_SOUND = 16  # the menu denied buzz (menu sound 5)
MAX_SOUND = 2790            # audio.fmt holds 2791 entries; 0 is blank
EARLY_FACTOR = 3            # a press up to 3 windows early counts as a miss
DEFAULT_PHYSICAL_ONLY = False  # Lexer: every damaging hit unless asked

INPUT_HOOK = 0x004A8554
INPUT_ORIGINAL = bytes.fromhex("66 8B 41 10 66 89 41 18")
INPUT_RESUME = 0x004A855C
BATTLE_INPUT = 0x01D6D490   # pointer; +0x12 newly pressed
SQUARE = 0x80  # FF8 function bits: L2 01 R2 02 L1 04 R1 08 Tri 10 O 20 X 40 Sq 80
HIT_HOOK = 0x00491124
HIT_ORIGINAL = bytes.fromhex("8A 0D 0E 8E D2 01")  # mov cl, [01D28E0E]
HIT_RESUME = 0x0049112A
TYPE_HOOK = 0x004922B0
TYPE_ORIGINAL = bytes.fromhex("A0 0E 8E D2 01")  # mov al, [01D28E0E]
TYPE_RESUME = 0x004922B5
PHYSICAL_TYPES = (1, 7, 9, 10, 36)
PHYSICAL_MASK = sum(1 << kind for kind in PHYSICAL_TYPES if kind < 32)
PHYSICAL_HIGH = tuple(kind for kind in PHYSICAL_TYPES if kind >= 32)
ATTACKER = 0x01D27AD8
PARTY_SIZE = 3
TIME_GET_TIME = 0x00B69378  # IAT slot
PLAY_SOUND = 0x0046B280
TRIGGER_STORES = (
    (0x00485158, bytes.fromhex("66 A3 94 8D D2 01"), bytes.fromhex("90 90 90 90 90 90")),
    (0x004851D6, bytes.fromhex("66 C7 05 94 8D D2 01 01 00"),
     bytes.fromhex("66 C7 05 94 8D D2 01 00 00")),
)

CAVE = 0x027AB900
# Settings live in data beside the code, so the code is fixed and embedded
# and a mod's settings only change these bytes.
DATA = 0x027ABAE0
WINDOW = DATA + 0x00
EARLY = DATA + 0x04
BONUS = DATA + 0x08
BLOCK = DATA + 0x0C
SOUND_SUCCESS = DATA + 0x10
SOUND_FAILURE = DATA + 0x14
PRESS_TIME = DATA + 0x18
PRESSED = DATA + 0x1C
PHYSICAL_ONLY = DATA + 0x20
HIT_TYPE = DATA + 0x24
DATA_SIZE = 0x28

ASSEMBLY = f"""
input:
    mov ax, word ptr [ecx + 0x10]
    mov word ptr [ecx + 0x18], ax
    test byte ptr [ecx + 0x12], {SQUARE:#x}
    jz input_done
    pushad
    call dword ptr [{TIME_GET_TIME:#x}]
    mov dword ptr [{PRESS_TIME:#x}], eax
    mov dword ptr [{PRESSED:#x}], 1
    popad
input_done:
    push {INPUT_RESUME:#x}
    ret
hit:
    pushad
    pushfd
    test esi, esi
    jle hit_done
    cmp dword ptr [{PRESSED:#x}], 0
    je hit_done
    cmp dword ptr [{PHYSICAL_ONLY:#x}], 0
    je typed
    movzx eax, byte ptr [{HIT_TYPE:#x}]
    cmp eax, {PHYSICAL_HIGH[0]}
    je typed
    cmp eax, 31
    ja hit_done
    mov ecx, {PHYSICAL_MASK:#x}
    bt ecx, eax
    jnc hit_done
typed:
    movzx ebx, byte ptr [{ATTACKER:#x}]
    mov eax, dword ptr [esp + 0x34]
    xor edx, edx
    mov ecx, 0xd0
    div ecx
    cmp ebx, {PARTY_SIZE}
    jae enemy_attacks
    cmp eax, {PARTY_SIZE}
    jb hit_done
    mov edi, dword ptr [{BONUS:#x}]
    jmp judged
enemy_attacks:
    cmp eax, {PARTY_SIZE}
    jae hit_done
    mov edi, dword ptr [{BLOCK:#x}]
judged:
    mov dword ptr [{PRESSED:#x}], 0
    call dword ptr [{TIME_GET_TIME:#x}]
    sub eax, dword ptr [{PRESS_TIME:#x}]
    cmp eax, dword ptr [{WINDOW:#x}]
    ja missed
    mov eax, dword ptr [esp + 8]
    imul eax, edi
    xor edx, edx
    mov ecx, 100
    div ecx
    mov dword ptr [esp + 8], eax
    push dword ptr [{SOUND_SUCCESS:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
    jmp hit_done
missed:
    cmp eax, dword ptr [{EARLY:#x}]
    ja hit_done
    push dword ptr [{SOUND_FAILURE:#x}]
    call {PLAY_SOUND:#x}
    add esp, 4
hit_done:
    popfd
    popad
    mov cl, byte ptr [0x1d28e0e]
    push {HIT_RESUME:#x}
    ret
hit_type:
    mov eax, dword ptr [esp + 4]
    mov byte ptr [{HIT_TYPE:#x}], al
    mov al, byte ptr [0x1d28e0e]
    push {TYPE_RESUME:#x}
    ret
"""

# Assembled at CAVE from ASSEMBLY; tests/ff8/test_ff8_timed_hits.py
# re-assembles it (keystone) and runs it under unicorn.
CODE = bytes.fromhex(
    "66 8B 41 10 66 89 41 18 F6 41 12 80 74 17 60 FF"
    "15 78 93 B6 00 A3 F8 BA 7A 02 C7 05 FC BA 7A 02"
    "01 00 00 00 61 68 5C 85 4A 00 C3 60 9C 85 F6 0F"
    "8E C2 00 00 00 83 3D FC BA 7A 02 00 0F 84 B5 00"
    "00 00 83 3D 00 BB 7A 02 00 74 23 0F B6 05 04 BB"
    "7A 02 83 F8 24 74 17 83 F8 1F 0F 87 97 00 00 00"
    "B9 82 06 00 00 0F A3 C1 0F 83 89 00 00 00 0F B6"
    "1D D8 7A D2 01 8B 44 24 34 31 D2 B9 D0 00 00 00"
    "F7 F1 83 FB 03 73 0D 83 F8 03 72 6B 8B 3D E8 BA"
    "7A 02 EB 0B 83 F8 03 73 5E 8B 3D EC BA 7A 02 C7"
    "05 FC BA 7A 02 00 00 00 00 FF 15 78 93 B6 00 2B"
    "05 F8 BA 7A 02 3B 05 E0 BA 7A 02 77 24 8B 44 24"
    "08 0F AF C7 31 D2 B9 64 00 00 00 F7 F1 89 44 24"
    "08 FF 35 F0 BA 7A 02 E8 A4 F8 CB FD 83 C4 04 EB"
    "16 3B 05 E4 BA 7A 02 77 0E FF 35 F4 BA 7A 02 E8"
    "8C F8 CB FD 83 C4 04 9D 61 8A 0D 0E 8E D2 01 68"
    "2A 11 49 00 C3 8B 44 24 04 A2 04 BB 7A 02 A0 0E"
    "8E D2 01 68 B5 22 49 00 C3"
)
HIT_ENTRY = 0x27ab92b
TYPE_ENTRY = 0x27aba05


def _assemble() -> tuple[bytes, int, int]:
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    code = bytes(ks.asm(ASSEMBLY, CAVE)[0])

    def entry(label: str) -> int:
        probe = ASSEMBLY.split(f"\n{label}:")[0] + f"\n{label}:\n nop"
        return CAVE + len(ks.asm(probe, CAVE)[0]) - 1
    return code, entry("hit"), entry("hit_type")


def _bounded(value, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number from {low} to {high}")
    if not low <= value <= high:
        raise ValueError(f"{label} must be from {low} to {high}")
    return value


def data_bytes(window_ms: int, bonus_percent: int, block_percent: int,
               success_sound: int, failure_sound: int, physical_only: bool = False) -> bytes:
    values = (window_ms, window_ms * EARLY_FACTOR, bonus_percent, block_percent,
              success_sound, failure_sound, 0, 0, int(physical_only), 0)
    return b"".join(value.to_bytes(4, "little") for value in values)


def _jump(site: int, target: int, length: int) -> bytes:
    rel = (target - (site + 5)).to_bytes(4, "little", signed=True)
    return b"\xE9" + rel + b"\x90" * (length - 5)


def build_hext(enabled: bool, *, window_ms: int = DEFAULT_WINDOW_MS,
               bonus_percent: int = DEFAULT_BONUS_PERCENT,
               block_percent: int = DEFAULT_BLOCK_PERCENT,
               success_sound: int = DEFAULT_SUCCESS_SOUND,
               failure_sound: int = DEFAULT_FAILURE_SOUND,
               physical_only: bool = DEFAULT_PHYSICAL_ONLY) -> str:
    """The patch with the chosen settings in its data, or nothing when off."""
    if not isinstance(enabled, bool):
        raise ValueError("Timed Hits must be true or false")
    if not isinstance(physical_only, bool):
        raise ValueError("Timed Hits physical only must be true or false")
    window_ms = _bounded(window_ms, MIN_WINDOW_MS, MAX_WINDOW_MS, "Timed Hits window")
    bonus_percent = _bounded(bonus_percent, MIN_BONUS_PERCENT, MAX_BONUS_PERCENT, "Timed Hits bonus")
    block_percent = _bounded(block_percent, MIN_BLOCK_PERCENT, MAX_BLOCK_PERCENT, "Timed Blocks damage")
    success_sound = _bounded(success_sound, 1, MAX_SOUND, "Timed Hits success sound")
    failure_sound = _bounded(failure_sound, 1, MAX_SOUND, "Timed Hits failure sound")
    if not enabled:
        return ""
    data = data_bytes(window_ms, bonus_percent, block_percent, success_sound, failure_sound, physical_only)
    lines = [
        f"# Timed Hits and Blocks: Square within {window_ms} ms before a hit lands; "
        f"hits x{bonus_percent}%, blocks take {block_percent}%"
        f"{', physical attacks only' if physical_only else ''}.",
        f"{CAVE:X}:{len(CODE):X}",
        f"{CAVE:X} = {CODE.hex(' ').upper()}",
        f"{DATA:X}:{DATA_SIZE:X}",
        f"{DATA:X} = {data.hex(' ').upper()}",
        f"{INPUT_HOOK:X} = {_jump(INPUT_HOOK, CAVE, len(INPUT_ORIGINAL)).hex(' ').upper()}",
        f"{HIT_HOOK:X} = {_jump(HIT_HOOK, HIT_ENTRY, len(HIT_ORIGINAL)).hex(' ').upper()}",
        f"{TYPE_HOOK:X} = {_jump(TYPE_HOOK, TYPE_ENTRY, len(TYPE_ORIGINAL)).hex(' ').upper()}",
        "# Squall's own trigger bonus is off; he uses the same window as everyone.",
    ]
    for site, _original, patched in TRIGGER_STORES:
        lines.append(f"{site:X} = {patched.hex(' ').upper()}")
    return "\n".join(lines + [""])


SETTING_KEYS = {
    # settings key: (build_hext argument, default, minimum, maximum, label)
    "timedHitsWindow": ("window_ms", DEFAULT_WINDOW_MS, MIN_WINDOW_MS, MAX_WINDOW_MS, "Timed Hits window"),
    "timedHitsBonus": ("bonus_percent", DEFAULT_BONUS_PERCENT, MIN_BONUS_PERCENT, MAX_BONUS_PERCENT, "Timed Hits bonus"),
    "timedBlocksDamage": ("block_percent", DEFAULT_BLOCK_PERCENT, MIN_BLOCK_PERCENT, MAX_BLOCK_PERCENT, "Timed Blocks damage"),
    "timedHitsSuccessSound": ("success_sound", DEFAULT_SUCCESS_SOUND, 1, MAX_SOUND, "Timed Hits success sound"),
    "timedHitsFailureSound": ("failure_sound", DEFAULT_FAILURE_SOUND, 1, MAX_SOUND, "Timed Hits failure sound"),
    "timedHitsPhysicalOnly": ("physical_only", DEFAULT_PHYSICAL_ONLY, False, True, "Timed Hits physical only"),
}


def options(data: dict, *, strict: bool) -> dict:
    """The settings from a settings document, as build_hext arguments.

    Loading is forgiving (a bad stored value falls back to its default);
    saving is strict and names the value that is out of range.
    """
    result = {}
    for key, (argument, default, low, high, label) in SETTING_KEYS.items():
        value = data.get(key, default)
        if isinstance(default, bool):
            if isinstance(value, bool):
                result[argument] = value
            elif strict:
                raise ValueError(f"{label} must be true or false")
            else:
                result[argument] = default
            continue
        try:
            result[argument] = _bounded(value, low, high, label)
        except ValueError:
            if strict:
                raise
            result[argument] = default
    return result


def limits() -> dict:
    """Defaults and bounds for the editor's controls."""
    return {key: {"default": default, "minimum": low, "maximum": high}
            for key, (_argument, default, low, high, _label) in SETTING_KEYS.items()
            if not isinstance(default, bool)}


def verified_hooks() -> list[tuple[int, bytes]]:
    return [(INPUT_HOOK, INPUT_ORIGINAL), (HIT_HOOK, HIT_ORIGINAL), (TYPE_HOOK, TYPE_ORIGINAL),
            *((site, original) for site, original, _ in TRIGGER_STORES)]
