"""Hit-frame diagnostic (#482/#483): the cave logs each opcode and resumes intact.

The cave is run under unicorn with the three kernel32 imports stubbed. It
must open the log once, append one well-formed line per instruction, and then
leave the handler exactly as the replaced instructions would have: AL holds
the opcode, ESP is 8 lower, every other register is unchanged, and execution
continues at 00504BB7.
"""
from __future__ import annotations

import re
import struct

import pytest

from plugins.ff8 import hit_frame_log as h

unicorn = pytest.importorskip("unicorn")
from unicorn import x86_const as x86  # noqa: E402

STUBS = {h.IAT_CREATE_FILE_A: (0x00F00000, 0x1C), h.IAT_SET_FILE_POINTER: (0x00F00010, 0x10),
         h.IAT_WRITE_FILE: (0x00F00020, 0x14)}
STACK = 0x00E00000
CURSOR_SLOT = 0x00D00000
SEQUENCE = 0x00D00100


def _machine():
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00800000), (0x00D00000, 0x00300000),
                       (0x01D98000, 0x1000), (0x027A9000, 0x1000)):
        emu.mem_map(base, size)
    emu.mem_write(h.CAVE, h.CODE)
    emu.mem_write(h.DATA, h.DATA_BYTES)
    emu.mem_write(h.SEQUENCE_OWNER, struct.pack("<I", 0x01D973A0))
    for slot, (stub, pop) in STUBS.items():
        emu.mem_write(slot, struct.pack("<I", stub))
        emu.mem_write(stub, b"\xC2" + struct.pack("<H", pop))  # ret N
    emu.mem_write(h.HOOK_RESUME, b"\xF4")  # hlt: resume point reached
    return emu


def _run(emu, opcode, cursor, calls):
    def on_code(uc, address, _size, _data):
        if address in {stub for stub, _ in STUBS.values()}:
            esp = uc.reg_read(x86.UC_X86_REG_ESP)
            args = struct.unpack("<5I", uc.mem_read(esp + 4, 20))
            if address == STUBS[h.IAT_CREATE_FILE_A][0]:
                name = bytes(uc.mem_read(args[0], 64)).split(b"\0")[0].decode()
                calls.append(("open", name, args[1], args[4]))
                uc.reg_write(x86.UC_X86_REG_EAX, 0x1234)
            elif address == STUBS[h.IAT_WRITE_FILE][0]:
                calls.append(("write", args[0], bytes(uc.mem_read(args[1], args[2]))))
                uc.reg_write(x86.UC_X86_REG_EAX, 1)
            else:
                calls.append(("seek", args[0], args[3]))
    hook = emu.hook_add(unicorn.UC_HOOK_CODE, on_code)
    emu.mem_write(CURSOR_SLOT, struct.pack("<I", cursor))
    esp = STACK + 0x1000
    emu.mem_write(esp, struct.pack("<3I", 0xCAFEBABE, opcode | 0x11223300, CURSOR_SLOT))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    for reg, value in ((x86.UC_X86_REG_EAX, 0xAAAAAAAA), (x86.UC_X86_REG_EBX, 0xBBBBBBBB),
                       (x86.UC_X86_REG_ECX, 0xCCCCCCCC), (x86.UC_X86_REG_EDX, 0xDDDDDDDD),
                       (x86.UC_X86_REG_ESI, 0x51515151), (x86.UC_X86_REG_EDI, 0xD1D1D1D1),
                       (x86.UC_X86_REG_EBP, 0xB0B0B0B0)):
        emu.reg_write(reg, value)
    emu.emu_start(h.CAVE, h.HOOK_RESUME + 1, count=5000)
    emu.hook_del(hook)
    assert emu.reg_read(x86.UC_X86_REG_EIP) in (h.HOOK_RESUME, h.HOOK_RESUME + 1)
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 8
    assert emu.reg_read(x86.UC_X86_REG_EAX) & 0xFF == opcode
    assert emu.reg_read(x86.UC_X86_REG_EAX) >> 8 == 0xAAAAAA
    for reg, value in ((x86.UC_X86_REG_EBX, 0xBBBBBBBB), (x86.UC_X86_REG_ECX, 0xCCCCCCCC),
                       (x86.UC_X86_REG_EDX, 0xDDDDDDDD), (x86.UC_X86_REG_ESI, 0x51515151),
                       (x86.UC_X86_REG_EDI, 0xD1D1D1D1), (x86.UC_X86_REG_EBP, 0xB0B0B0B0)):
        assert emu.reg_read(reg) == value


def test_logs_each_opcode_once_opened_and_resumes_intact():
    emu = _machine()
    calls = []
    _run(emu, 0xAB, SEQUENCE + 1, calls)
    _run(emu, 0x91, SEQUENCE + 9, calls)
    opens = [call for call in calls if call[0] == "open"]
    assert opens == [("open", h.LOG_NAME, 0x40000000, 4)], "the log opens once, appending"
    assert [call for call in calls if call[0] == "seek"] == [("seek", 0x1234, 2)]
    writes = [call[2].decode() for call in calls if call[0] == "write"]
    assert len(writes) == 2
    pattern = re.compile(r"^[0-9A-F]{16} 01D973A0 ([0-9A-F]{8}) ([0-9A-F]{2})\r\n$")
    first, second = (pattern.match(line) for line in writes)
    assert first and first.groups() == (f"{SEQUENCE:08X}", "AB")
    assert second and second.groups() == (f"{SEQUENCE + 8:08X}", "91")


def test_off_writes_nothing_and_on_hooks_the_verified_bytes():
    assert h.build_hext(False) == ""
    text = h.build_hext(True)
    assert f"{h.HOOK:X} = E9" in text
    assert h.hook_bytes()[:1] == b"\xE9" and len(h.hook_bytes()) == len(h.HOOK_ORIGINAL)
    assert h.CAVE + len(h.CODE) <= h.DATA
    with pytest.raises(ValueError):
        h.build_hext("yes")


def test_cave_bytes_match_their_source():
    keystone = pytest.importorskip("keystone")
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    assert bytes(ks.asm(h.ASSEMBLY, h.CAVE)[0]) == h.CODE
