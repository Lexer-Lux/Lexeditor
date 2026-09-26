"""GF Acquisition Rework: the Draw-list capture and victory award under unicorn."""
from __future__ import annotations

import pytest

from plugins.ff8 import gf_acquisition_rework as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
AWARD_LOG = 0x00E0F000  # the stand-in for 0047E480 records each GF it is given


def _machine():
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00200000), (0x00E00000, 0x00010000),
                       (0x01CF0000, 0x10000), (0x01D20000, 0x10000),
                       (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(m.CAVE, m.CODE)
    for resume in (m.CAPTURE_RESUME, m.VICTORY_RESUME):
        emu.mem_write(resume, b"\xF4")
    # 0047E480 stand-in: log [esp+4] at AWARD_LOG[count], then set its exists bit.
    import keystone
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    stub = f"""
        mov eax, dword ptr [esp + 4]
        movzx ecx, byte ptr [{AWARD_LOG:#x}]
        mov byte ptr [ecx + {AWARD_LOG + 1:#x}], al
        inc byte ptr [{AWARD_LOG:#x}]
        imul eax, eax, {m.GF_STRIDE}
        or byte ptr [eax + {m.GF_EXISTS:#x}], 1
        ret
    """
    emu.mem_write(m.AWARD_GF, bytes(ks.asm(stub, m.AWARD_GF)[0]))
    return emu


def _run(emu, entry, resume, registers=()):
    esp = STACK + 0x8000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    for register, value in registers:
        emu.reg_write(register, value)
    emu.emu_start(entry, resume, count=20000)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp, "stack balanced"


def _draw(emu, enemy, entries):
    base = m.ENEMY_DRAW + enemy * m.ENEMY_DRAW_STRIDE
    for index, value in enumerate(entries):
        emu.mem_write(base + index * 4, bytes((value,)))


def _read_draw(emu, enemy):
    base = m.ENEMY_DRAW + enemy * m.ENEMY_DRAW_STRIDE
    return [emu.mem_read(base + index * 4, 1)[0] for index in range(4)]


def test_capture_blanks_gf_entries_and_keeps_spells():
    emu = _machine()
    emu.mem_write(m.ENEMY_PRESENT, bytes((1, 1, 0, 0, 0, 0, 0, 1)))
    _draw(emu, 0, (0x05, 0x43, 0x00, 0x12))  # Siren (3) beside two spells
    _draw(emu, 1, (0x2A, 0x2B, 0x2C, 0x2D))
    _draw(emu, 2, (0x4F, 0, 0, 0))  # absent enemy: left alone
    _draw(emu, 7, (0x4F, 0x06, 0, 0))  # Eden (15) on the last slot
    _run(emu, m.ENTRY["capture"], m.CAPTURE_RESUME, ((x86.UC_X86_REG_ESI, 0x1234),))
    assert _read_draw(emu, 0) == [0x05, 0x00, 0x00, 0x12]
    assert _read_draw(emu, 1) == [0x2A, 0x2B, 0x2C, 0x2D]
    assert _read_draw(emu, 2) == [0x4F, 0, 0, 0]
    assert _read_draw(emu, 7) == [0x00, 0x06, 0, 0]
    captured = int.from_bytes(emu.mem_read(m.CAPTURED, 4), "little")
    assert captured == (1 << 3) | (1 << 15)
    # The replaced instruction still runs.
    assert emu.reg_read(x86.UC_X86_REG_ESI) == 0x01D27DFC


def test_capture_starts_from_an_empty_record():
    emu = _machine()
    emu.mem_write(m.CAPTURED, (0xFFFF).to_bytes(4, "little"))
    _run(emu, m.ENTRY["capture"], m.CAPTURE_RESUME)
    assert int.from_bytes(emu.mem_read(m.CAPTURED, 4), "little") == 0


def test_victory_awards_missing_gfs_once_and_lists_them():
    emu = _machine()
    emu.mem_write(m.CAPTURED, ((1 << 3) | (1 << 7) | (1 << 15)).to_bytes(4, "little"))
    emu.mem_write(m.GF_EXISTS + 7 * m.GF_STRIDE, b"\x01")  # Leviathan already owned
    emu.mem_write(m.AWARD_LIST, b"\xFF\xFF\xFF")
    registers = ((x86.UC_X86_REG_EBX, 0x11), (x86.UC_X86_REG_EDI, 0x22))
    _run(emu, m.ENTRY["victory"], m.VICTORY_RESUME, registers)
    assert emu.mem_read(m.BATTLE_END, 1)[0] == 4, "the replaced write still happens"
    log = emu.mem_read(AWARD_LOG, 3)
    assert log[0] == 2 and list(log[1:3]) == [3, 15]
    assert list(emu.mem_read(m.AWARD_LIST, 3)) == [3, 15, 0xFF]
    assert emu.mem_read(m.AWARD_COUNT, 1)[0] == 2
    assert int.from_bytes(emu.mem_read(m.CAPTURED, 4), "little") == 0
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0x11 and emu.reg_read(x86.UC_X86_REG_EDI) == 0x22


def test_victory_never_overruns_the_three_entry_list():
    emu = _machine()
    emu.mem_write(m.CAPTURED, ((1 << 3) | (1 << 6)).to_bytes(4, "little"))
    emu.mem_write(m.AWARD_COUNT, b"\x03")
    _run(emu, m.ENTRY["victory"], m.VICTORY_RESUME)
    assert emu.mem_read(m.BATTLE_END, 1)[0] == 4
    assert emu.mem_read(AWARD_LOG, 1)[0] == 2, "still awarded"
    assert emu.mem_read(m.AWARD_COUNT, 1)[0] == 3


def test_nothing_captured_awards_nothing():
    emu = _machine()
    _run(emu, m.ENTRY["victory"], m.VICTORY_RESUME)
    assert emu.mem_read(AWARD_LOG, 1)[0] == 0


def test_hooks_and_embedded_code():
    assert m.verified_hooks() == [(m.CAPTURE_HOOK, m.CAPTURE_ORIGINAL),
                                  (m.VICTORY_HOOK, m.VICTORY_ORIGINAL)]
    pytest.importorskip("keystone")
    assert m._assemble() == (m.CODE, m.ENTRY)
