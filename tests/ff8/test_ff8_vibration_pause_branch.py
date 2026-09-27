"""Pausing early in an enemy attack crashed at 004C8D99 (three crash dumps).

004C8CC2 jumps to 004C8D93, a byte inside the jump Vibration Consolidation
writes at 004C8D8F. The branch now has its own entry. Both ways into the
battle pause are run here under unicorn against the real executable bytes,
with the patch applied, and must reach 004C8D9A with the two arguments the
native path pushes.
"""
import re
import struct

import pytest

from plugins.ff8 import vibration_consolidation_issue_66 as v
from plugins.ff8 import paths

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

EXE = paths.GAME_ROOT / "FF8_EN.exe"


def _machine():
    if not EXE.is_file():
        pytest.skip("FF8_EN.exe is not installed")
    data = EXE.read_bytes()
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    emu.mem_map(0x0049A000, 0x1000)
    emu.mem_map(0x004C8000, 0x2000)
    emu.mem_map(0x0279E000, 0x2000)
    emu.mem_map(0x00100000, 0x10000)
    emu.mem_write(0x004C8000, data[0x004C8000 - 0x400000:0x004CA000 - 0x400000])
    for line in v.build_hext(True).splitlines():
        match = re.fullmatch(r"([0-9A-F]+) = ([0-9A-F ]+)", line)
        if match:
            emu.mem_write(int(match[1], 16), bytes.fromhex(match[2]))
    emu.mem_write(v.BATTLE_NATIVE_PAUSE, b"\xC3")  # the pause itself: return
    return emu


@pytest.mark.parametrize("start,extra", [(v.BATTLE_BRANCH, 0), (v.BATTLE_HOOK, 0x2C)])
def test_both_ways_into_the_battle_pause_reach_its_return(start, extra):
    emu = _machine()
    esp = 0x00108000
    # The fall-through path first drops 0x28 bytes and pops EDI.
    emu.mem_write(esp, b"\x00" * extra)
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EAX, 0xAAAA0001)
    emu.reg_write(x86.UC_X86_REG_EBP, 0xBBBB0002)
    emu.emu_start(start, v.BATTLE_RETURN, count=50)
    assert emu.reg_read(x86.UC_X86_REG_EIP) == v.BATTLE_RETURN
    top = emu.reg_read(x86.UC_X86_REG_ESP)
    assert top == esp + extra - 8
    assert struct.unpack("<II", emu.mem_read(top, 8)) == (0xBBBB0002, 0xAAAA0001)


def test_the_branch_is_verified_before_it_is_patched():
    assert EXE.is_file() or pytest.skip("FF8_EN.exe is not installed")
    data = EXE.read_bytes()
    at = v.BATTLE_BRANCH - 0x400000
    assert data[at:at + 5] == v.BATTLE_BRANCH_ORIGINAL
