"""Formulae Rework, Mug chance: the cave under unicorn agrees with the formula."""
from __future__ import annotations

import struct

import pytest

from plugins.ff8 import formulae_rework
from plugins.ff8 import mug_chance_rework as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000


def _mug(roll: int, rate: int, target_spd: int, mugger_spd: int) -> bool:
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00200000), (0x00D00000, 0x00200000),
                       (0x01D27000, 0x2000), (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(m.CAVE, m.CODE)
    emu.mem_write(m.RANDOM, bytes((0xB8, roll, 0, 0, 0, 0xC3)))  # mov eax,roll; ret
    emu.mem_write(m.SUCCESS, b"\xF4")
    emu.mem_write(m.FAILURE, b"\xF4")
    target = 5
    emu.mem_write(m.TARGET_SPD + target * 0xD0, bytes((target_spd,)))
    esp = STACK + 0x1000
    emu.mem_write(esp + 0x1C, struct.pack("<I", mugger_spd))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, target)
    emu.reg_write(x86.UC_X86_REG_EDI, rate)
    emu.emu_start(m.CAVE, 0, count=500)
    eip = emu.reg_read(x86.UC_X86_REG_EIP)
    assert eip in (m.SUCCESS, m.SUCCESS + 1, m.FAILURE, m.FAILURE + 1)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp, "stack balanced"
    assert emu.reg_read(x86.UC_X86_REG_ESI) == target
    return eip in (m.SUCCESS, m.SUCCESS + 1)


@pytest.mark.parametrize("rate", [1, 30, 70, 100])
@pytest.mark.parametrize("target_spd,mugger_spd", [(0, 0), (20, 40), (40, 20), (255, 0), (0, 255)])
def test_success_matches_the_formula(rate, target_spd, mugger_spd):
    chance = formulae_rework.mug_stored_success_chance(rate, target_spd, mugger_spd)
    for roll in range(0, 256, 7):
        assert _mug(roll, rate, target_spd, mugger_spd) == ((roll % 100) < chance), (roll, chance)


def test_hext_and_hooks():
    assert m.build_hext(False) == ""
    assert f"{m.HOOK:X} = E9" in m.build_hext(True)
    assert m.verified_hooks() == [(m.HOOK, m.HOOK_ORIGINAL)]


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    assert m._assemble() == m.CODE
