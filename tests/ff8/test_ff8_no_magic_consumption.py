"""No Magic Consumption as Hext: the battle cave under unicorn, and its wiring."""
from __future__ import annotations

import pytest

from plugins.ff8 import gameplay_settings
from plugins.ff8 import no_magic_consumption as m

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STACK = 0x00E00000
ENTRY = 0x00E0F000  # one list entry: [id][stock]


def _cast(callback: int, stock: int, spent: int) -> tuple[int, int]:
    """Run the cave; return (EAX, where it resumed)."""
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00200000), (0x00E00000, 0x00010000),
                       (0x01D76000, 0x1000), (0x027AB000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(m.CAVE, m.CODE)
    for resume in (m.BATTLE_KEPT, m.BATTLE_EMPTIED):
        emu.mem_write(resume, b"\xF4")
    emu.mem_write(m.LIST_CALLBACK, callback.to_bytes(4, "little"))
    emu.mem_write(ENTRY, bytes((0x05, stock)))
    esp = STACK + 0x8000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ECX, ENTRY + 1)
    emu.reg_write(x86.UC_X86_REG_EAX, stock)  # the native movsx load before the hook
    emu.reg_write(x86.UC_X86_REG_EDI, spent)
    emu.emu_start(m.CAVE, 0, count=100)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    return emu.reg_read(x86.UC_X86_REG_EAX), emu.reg_read(x86.UC_X86_REG_EIP) - 1


@pytest.mark.parametrize("stock", [1, 9, 100, 200])
def test_a_magic_cast_keeps_its_stock(stock):
    assert _cast(m.MAGIC_LIST, stock, 1) == (stock, m.BATTLE_KEPT)


def test_an_item_is_still_used_up():
    assert _cast(0x004C9999, 5, 1) == (4, m.BATTLE_KEPT)
    assert _cast(0x004C9999, 1, 2) == (0, m.BATTLE_EMPTIED)


def test_the_patch_and_its_wiring():
    assert m.build_hext(False) == ""
    text = m.build_hext(True)
    assert f"\n{m.BATTLE_HOOK:X} = E9" in text and f"\n{m.FIELD_DEBIT:X} = 90 90" in text
    assert m.verified_hooks() == [(m.BATTLE_HOOK, m.BATTLE_ORIGINAL), (m.FIELD_DEBIT, m.FIELD_ORIGINAL)]
    assert f"{m.FIELD_DEBIT:X} = 90 90" in gameplay_settings.build_hext(25, False, no_magic_consumption=True)
    assert f"{m.FIELD_DEBIT:X} =" not in gameplay_settings.build_hext(25, False)


def test_embedded_code_matches_its_source():
    pytest.importorskip("keystone")
    assert m._assemble() == m.CODE
