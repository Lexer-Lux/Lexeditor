"""Formulae Rework, spell damage: the cave under unicorn."""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import formulae_rework
from plugins.ff8 import magic_damage_rework as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
RETURN = 0x00D00000
PROBE = 0x00D00F00


def _machine():
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00200000), (0x00D00000, 0x00200000),
                       (0x01D27000, 0x2000), (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(m.CAVE, m.CODE)
    emu.mem_write(RETURN, b"\xF4")
    return emu


def _run(emu, start, end, registers=(), stack=(), flag=0):
    esp = STACK + 0x1000
    emu.mem_write(m.FLAG, bytes((flag,)))
    emu.mem_write(esp, struct.pack(f"<{len(stack) + 1}I", RETURN, *stack))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    for register, value in registers:
        emu.reg_write(register, value)
    emu.emu_start(start, end + 1, count=5000)
    assert emu.reg_read(x86.UC_X86_REG_EIP) in (end, end + 1)
    return esp


@pytest.mark.parametrize("power,mag,spr", [(12, 40, 0), (12, 40, 25), (12, 40, 200), (255, 255, 75), (0, 99, 10)])
def test_reworked_core_matches_the_formula(power, mag, spr):
    emu = _machine()
    caster = 4
    emu.mem_write(m.CASTER_MAG + caster * 0xD0, bytes((mag,)))
    emu.mem_write(m.CORE_RESULT_RESUME, b"\xF4")
    _run(emu, m.ENTRY["core"], m.CORE_RESULT_RESUME, flag=1, registers=(
        (x86.UC_X86_REG_EBX, caster), (x86.UC_X86_REG_EBP, power), (x86.UC_X86_REG_EDI, spr)))
    assert emu.reg_read(x86.UC_X86_REG_ESI) == formulae_rework.magic_damage(power, mag, spr)
    assert (emu.reg_read(x86.UC_X86_REG_EBX), emu.reg_read(x86.UC_X86_REG_EBP)) == (caster, power)


def test_core_is_vanilla_outside_a_spell():
    emu = _machine()
    emu.mem_write(m.RANDOM, b"\xB8\x2A\x00\x00\x00\xC3")  # mov eax,42; ret
    emu.mem_write(m.CORE_VANILLA_RESUME, b"\xF4")
    _run(emu, m.ENTRY["core"], m.CORE_VANILLA_RESUME, flag=0,
         registers=((x86.UC_X86_REG_ESI, 0x5151),))
    assert emu.reg_read(x86.UC_X86_REG_EAX) == 42, "the vanilla random call ran"
    assert emu.reg_read(x86.UC_X86_REG_ESI) == 0x5151


def test_magic_call_flags_only_its_own_call():
    emu = _machine()
    # The damage routine records the flag and its four arguments, returns 7.
    emu.mem_write(m.DAMAGE_ROUTINE, bytes.fromhex(
        "A0 00 B1 7A 02"          # mov al,[FLAG]
        "A2 00 0F D0 00"          # mov [PROBE],al
        "8B 44 24 04 A3 04 0F D0 00"
        "8B 44 24 08 A3 08 0F D0 00"
        "8B 44 24 0C A3 0C 0F D0 00"
        "8B 44 24 10 A3 10 0F D0 00"
        "B8 07 00 00 00 C3"))
    esp = _run(emu, m.ENTRY["magic_call"], RETURN, stack=(11, 22, 33, 0))
    assert emu.mem_read(PROBE, 1)[0] == 1, "flag raised during the spell's damage"
    assert struct.unpack("<4I", emu.mem_read(PROBE + 4, 16)) == (11, 22, 33, 0)
    assert emu.mem_read(m.FLAG, 1)[0] == 0, "and lowered afterwards"
    assert emu.reg_read(x86.UC_X86_REG_EAX) == 7
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp + 4


def test_hext_and_hooks():
    assert m.build_hext(False) == ""
    text = m.build_hext(True)
    assert f"{m.MAGIC_CALL:X} = E8" in text and f"{m.CORE_HOOK:X} = E9" in text
    assert [site for site, _ in m.verified_hooks()] == [m.MAGIC_CALL, m.CORE_HOOK]


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    assert m._assemble() == (m.CODE, m.ENTRY)
