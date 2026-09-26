"""Formulae Rework, status chances: the patched native arithmetic under unicorn.

The native segment is taken from the player's executable (LEXEDITOR_FF8_EXE),
never stored here; without it only the patch structure is checked.
"""
from __future__ import annotations

import hashlib
import os
import struct
from pathlib import Path

import pytest

from plugins.ff8 import formulae_rework
from plugins.ff8 import status_chance_rework as m

SUPPORTED = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
SEGMENT = (0x0048FA4E, 0x0048FA79)  # chance = accuracy + attacker - target - resistance


def _executable() -> bytes:
    value = os.environ.get("LEXEDITOR_FF8_EXE", "")
    if not value or not Path(value).is_file():
        pytest.skip("Set LEXEDITOR_FF8_EXE to the supported FF8_EN.exe to run the native segment")
    data = Path(value).read_bytes()
    if hashlib.sha256(data).hexdigest() != SUPPORTED:
        pytest.skip("LEXEDITOR_FF8_EXE is not the supported build")
    return data


def _chance(image: bytes, patched: bool, accuracy: int, attacker: int, target: int, resistance: int) -> int:
    unicorn = pytest.importorskip("unicorn")
    from unicorn import x86_const as x86
    start, end = SEGMENT
    code = bytearray(image[start - 0x400000:end - 0x400000])
    if patched:
        for site, original, replacement, _what in m.PATCHES:
            if start <= site < end:
                offset = site - start
                assert bytes(code[offset:offset + len(original)]) == original
                code[offset:offset + len(original)] = replacement
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    emu.mem_map(0x00400000, 0x00200000)
    emu.mem_map(0x00E00000, 0x00010000)
    emu.mem_write(start, bytes(code))
    esp = 0x00E08000
    # At the segment start (three registers saved): [esp+0x24] attacker stat,
    # [esp+0x28] target stat (read as +0x2C after the segment's own push).
    frame = bytearray(0x40)
    struct.pack_into("<I", frame, 0x24, attacker)
    struct.pack_into("<I", frame, 0x28, target)
    emu.mem_write(esp, bytes(frame))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EDI, accuracy)
    emu.reg_write(x86.UC_X86_REG_ECX, resistance)
    emu.emu_start(start, end)
    return struct.unpack("<i", struct.pack("<I", emu.reg_read(x86.UC_X86_REG_EAX)))[0]


@pytest.mark.parametrize("accuracy,attacker,target,resistance", [
    (200, 40, 20, 100), (150, 30, 10, 100), (200, 255, 0, 199), (100, 0, 255, 50)])
def test_patched_segment_is_one_percent_per_point(accuracy, attacker, target, resistance):
    image = _executable()
    vanilla = _chance(image, False, accuracy, attacker, target, resistance)
    assert vanilla == accuracy + attacker // 4 - target // 4 - resistance
    reworked = _chance(image, True, accuracy, attacker, target, resistance)
    assert reworked == accuracy - resistance + attacker - target
    if accuracy - resistance + attacker - target >= 0:
        assert min(100, reworked) == formulae_rework.status_infliction_chance(
            accuracy, resistance, attacker, target)


def test_patches_are_in_place_and_same_length():
    for site, original, replacement, _what in m.PATCHES:
        assert len(original) == len(replacement)
    assert m.build_hext(False) == ""
    text = m.build_hext(True)
    for site, *_ in m.PATCHES:
        assert f"\n{site:X} = " in text
