"""Formulae Rework, melee damage: the cave under unicorn agrees with the formula."""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import formulae_rework
from plugins.ff8 import melee_damage_rework as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
TARGET = 4


def _machine(attacker, strength, *, weapon=0, bonus=0, character=2, dream=0,
             character_id=None, dream_weapon=0, trigger=0):
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00200000), (0x00D00000, 0x00200000),
                       (0x01CF0000, 0x10000), (0x01D27000, 0x3000),
                       (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(m.CAVE, m.CODE)
    for resume in (m.CORE_RESUME, m.GUNBLADE_RESUME):
        emu.mem_write(resume, b"\xF4")
    emu.mem_write(m.ATTACKER_STR + attacker * 0xD0, bytes((strength,)))
    if attacker < 3:
        emu.mem_write(m.PARTY_CHARACTER + attacker, bytes((character,)))
        block = m.CHARACTER_BLOCK + character * 0x98
        emu.mem_write(block, bytes((character if character_id is None else character_id, weapon)))
        emu.mem_write(m.DREAM_FLAG, bytes((dream,)))
        emu.mem_write(m.DREAM_WEAPON, bytes((dream_weapon,)) * 3)
        # The weapon in use holds the bonus; the other one holds a decoy.
        used, unused = (dream_weapon, weapon) if dream else (weapon, dream_weapon)
        if unused != used:
            emu.mem_write(m.WEAPON_STR_BONUS + unused * 12, bytes((99,)))
        emu.mem_write(m.WEAPON_STR_BONUS + used * 12, bytes((bonus,)))
    emu.mem_write(m.TRIGGER_VALUE, struct.pack("<h", trigger))
    return emu


def _core(emu, attacker, power, vit):
    esp = STACK + 0x1000
    # Four saved registers, the return address, then (attacker, target, power, subtype).
    emu.mem_write(esp, struct.pack("<9I", 0, 0, 0, 0, 0, attacker, TARGET, power, 0))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EDI, attacker)
    emu.reg_write(x86.UC_X86_REG_EBP, power)
    emu.reg_write(x86.UC_X86_REG_EBX, vit)
    emu.emu_start(m.ENTRY["core"], m.CORE_RESUME, count=500)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp, "stack balanced"
    assert emu.reg_read(x86.UC_X86_REG_ESI) == TARGET
    return emu.reg_read(x86.UC_X86_REG_EAX)


def _gunblade(emu, attacker, power, vit):
    esp = STACK + 0x1000
    emu.mem_write(esp, struct.pack("<8I", 0, 0, 0, 0, 0, attacker, TARGET, power))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBP, TARGET)
    emu.reg_write(x86.UC_X86_REG_EBX, vit)
    emu.emu_start(m.ENTRY["gunblade"], m.GUNBLADE_RESUME, count=500)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp, "stack balanced"
    assert emu.reg_read(x86.UC_X86_REG_ESI) == attacker
    assert emu.reg_read(x86.UC_X86_REG_EDI) == power
    assert emu.reg_read(x86.UC_X86_REG_EBP) == TARGET
    return struct.unpack("<i", struct.pack("<I", emu.reg_read(x86.UC_X86_REG_EAX)))[0]


@pytest.mark.parametrize("strength,bonus,power,vit", [
    (40, 20, 20, 0), (40, 20, 20, 50), (40, 20, 20, 255), (255, 255, 255, 0), (1, 3, 11, 10)])
def test_party_attack_uses_the_weapon_bonus(strength, bonus, power, vit):
    emu = _machine(1, strength, weapon=7, bonus=bonus)
    assert _core(emu, 1, power, vit) == formulae_rework.melee_damage(strength, bonus, power, vit)


@pytest.mark.parametrize("attacker", [3, 5, 7])
def test_enemy_attack_counts_its_bonus_as_one(attacker):
    emu = _machine(attacker, 90)
    assert _core(emu, attacker, 30, 20) == formulae_rework.melee_damage(90, 1, 30, 20)


@pytest.mark.parametrize("character_id", [8, 9, 10])
def test_dream_party_uses_the_dream_weapon(character_id):
    emu = _machine(0, 50, weapon=2, bonus=6, character=0, dream=1,
                   character_id=character_id, dream_weapon=5)
    assert _core(emu, 0, 20, 0) == formulae_rework.melee_damage(50, 6, 20, 0)


@pytest.mark.parametrize("trigger", [0, 19, 20, 60, 100, -20])
def test_gunblade_keeps_the_native_trigger_factor(trigger):
    emu = _machine(0, 60, weapon=3, bonus=4, trigger=trigger)
    melee = formulae_rework.melee_damage(60, 4, 25, 30)
    assert _gunblade(emu, 0, 25, 30) == m.gunblade_damage(melee, trigger)
    if trigger == 0:
        assert m.gunblade_damage(melee, trigger) == melee


def test_hext_and_hooks():
    assert m.build_hext(False) == ""
    text = m.build_hext(True)
    assert f"\n{m.CORE_HOOK:X} = E9" in text
    assert f"\n{m.GUNBLADE_HOOK:X} = E9" in text
    assert m.verified_hooks() == [(m.CORE_HOOK, m.CORE_HOOK_ORIGINAL),
                                  (m.GUNBLADE_HOOK, m.GUNBLADE_HOOK_ORIGINAL)]


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    assert m._assemble() == (m.CODE, m.ENTRY)
