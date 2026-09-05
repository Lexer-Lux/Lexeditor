"""Use Lexer's proved spell-healing formula for normal curative magic.

Only the arithmetic core for Damage_ComputeCurativeMagic mode 7 is replaced.
The native routine still owns target validity, Shell, Invincible, Zombie sign,
cure-status application, hit flags, and the later HP write. Other attack types
and the routine's mode-8 special path remain unchanged.
"""

from __future__ import annotations


DEFAULT_SPELL_HEALING_REWORK = False

# Supported FF8_EN.exe SHA-256:
# 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570
#
# Damage_ComputeCurativeMagic has already selected mode 7 at this point.
# EDI is the spell-power argument. [ESP+0x10] is the caster index after the
# routine's saved-EDI push. The battle record stride is 0xD0 and +0xBF is the
# effective MAG byte (absolute displacement 0x01D27BCF after index scaling).
HEALING_FORMULA_HOOK = 0x00493398
HEALING_FORMULA_ORIGINAL = bytes.fromhex("E8 83 BC FF FF")  # call random-byte
HEALING_FORMULA_CONTINUE = 0x004933E8
HEALING_FORMULA_CAVE = 0x027A1500


def _relative_jump(source: int, target: int) -> bytes:
    return b"\xE9" + (int(target) - (int(source) + 5)).to_bytes(
        4, "little", signed=True,
    )


def build_code_cave() -> bytes:
    """Return `healing = spell power * effective caster MAG`."""
    payload = bytearray()
    payload += bytes.fromhex("8B 44 24 10")       # mov eax,[esp+10] (caster)
    payload += bytes.fromhex("8D 14 40")          # lea edx,[eax+eax*2]
    payload += bytes.fromhex("8D 04 90")          # lea eax,[eax+edx*4]
    payload += bytes.fromhex("C1 E0 04")          # shl eax,4 (index * 0xD0)
    payload += bytes.fromhex("0F B6 80 CF 7B D2 01")  # movzx eax,[eax+MAG]
    payload += bytes.fromhex("0F AF C7")          # imul eax,edi (spell power)
    payload += _relative_jump(
        HEALING_FORMULA_CAVE + len(payload), HEALING_FORMULA_CONTINUE,
    )
    return bytes(payload)


HEALING_FORMULA_CAVE_LENGTH = len(build_code_cave())


def reworked_healing(spell_power: int, caster_magic: int) -> int:
    """Mirror the isolated arithmetic core for tests and UI explanations."""
    if isinstance(spell_power, bool) or isinstance(caster_magic, bool):
        raise ValueError("Spell power and caster MAG must be bytes")
    power = int(spell_power)
    magic = int(caster_magic)
    if not 0 <= power <= 255 or not 0 <= magic <= 255:
        raise ValueError("Spell power and caster MAG must be from 0 to 255")
    return power * magic


def apply_native_healing_modifiers(amount: int, *, shell: bool = False,
                                   invincible: bool = False,
                                   zombie: bool = False) -> int:
    """Model the downstream native branches that the cave deliberately keeps."""
    result = int(amount)
    if shell and result:
        result //= 2
    if invincible:
        result = 0
    if zombie:
        result = -result
    return result


def build_hext(enabled: bool) -> str:
    """Return the isolated Hext fragment, or no patch for vanilla behavior."""
    if not isinstance(enabled, bool):
        raise ValueError("Spell Healing Rework must be true or false")
    if not enabled:
        return ""
    payload = build_code_cave()
    return "\n".join((
        "# Spell Healing Rework: healing = spell power * effective caster MAG.",
        "# Native Shell, Invincible, Zombie, cure-status and HP-write paths remain.",
        f"{HEALING_FORMULA_CAVE:X}:{len(payload):X}",
        f"{HEALING_FORMULA_HOOK:X} = "
        f"{_relative_jump(HEALING_FORMULA_HOOK, HEALING_FORMULA_CAVE).hex(' ').upper()}",
        f"{HEALING_FORMULA_CAVE:X} = {payload.hex(' ').upper()}",
        "",
    ))
