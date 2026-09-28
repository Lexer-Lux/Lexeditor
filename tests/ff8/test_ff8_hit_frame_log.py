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
HP = (0x03E7, 0x0200, 0, 0x1234, 0x0001FFFF, 0x10, 0x270F)
MOTION = 0x0A05  # objects 0, 2, 9 and 11 are on a motion path


def _machine():
    emu = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
    for base, size in ((0x00400000, 0x00800000), (0x00D00000, 0x00300000),
                       (0x01D27000, 0x2000), (0x01D97000, 0x2000), (0x027A9000, 0x1000)):
        emu.mem_map(base, size)
    for index, hp in enumerate(HP):
        emu.mem_write(h.PARTICIPANT_HP + index * 0xD0, struct.pack("<I", hp))
    emu.mem_write(h.MOTION_PATHS, struct.pack("<H", MOTION))
    emu.mem_write(h.CAVE, h.CODE)
    emu.mem_write(h.DATA, h.DATA_BYTES)
    emu.mem_write(h.SEQUENCE_OWNER, struct.pack("<I", 0x01D973A0))
    for slot, (stub, pop) in STUBS.items():
        emu.mem_write(slot, struct.pack("<I", stub))
        emu.mem_write(stub, b"\xC2" + struct.pack("<H", pop))  # ret N
    emu.mem_write(h.HOOK_RESUME, b"\xF4")  # hlt: resume point reached
    emu.mem_write(h.DAMAGE_RESUME, b"\xF4")
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
    pattern = re.compile(r"^[0-9A-F]{16} 01D973A0 ([0-9A-F]{8}) ([0-9A-F]{2})((?: [0-9A-F]{8}){7}) ([0-9A-F]{4})\r\n$")
    first, second = (pattern.match(line) for line in writes)
    hp = " " + " ".join(f"{value:08X}" for value in HP)
    assert first and first.groups() == (f"{SEQUENCE:08X}", "AB", hp, f"{MOTION:04X}")
    assert second and second.groups() == (f"{SEQUENCE + 8:08X}", "91", hp, f"{MOTION:04X}")


def test_damage_entry_logs_the_target_and_resumes_the_damage_routine():
    emu = _machine()
    calls = []

    def on_code(uc, address, _size, _data):
        if address == STUBS[h.IAT_CREATE_FILE_A][0]:
            uc.reg_write(x86.UC_X86_REG_EAX, 0x1234)
        elif address == STUBS[h.IAT_WRITE_FILE][0]:
            esp = uc.reg_read(x86.UC_X86_REG_ESP)
            args = struct.unpack("<5I", uc.mem_read(esp + 4, 20))
            calls.append(bytes(uc.mem_read(args[1], args[2])).decode())
            uc.reg_write(x86.UC_X86_REG_EAX, 1)
    emu.hook_add(unicorn.UC_HOOK_CODE, on_code)
    esp = STACK + 0x1000
    caller = 0x0048F451
    emu.mem_write(esp, struct.pack("<2I", caller, 4))  # return address, target 4
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    for reg, value in ((x86.UC_X86_REG_EBX, 0xBBBBBBBB), (x86.UC_X86_REG_ESI, 0x51515151),
                       (x86.UC_X86_REG_EDI, 0xD1D1D1D1), (x86.UC_X86_REG_EBP, 0xB0B0B0B0)):
        emu.reg_write(reg, value)
    emu.emu_start(h.CAVE + h.ENTRY["damage"], h.DAMAGE_RESUME + 1, count=5000)
    assert emu.reg_read(x86.UC_X86_REG_EIP) in (h.DAMAGE_RESUME, h.DAMAGE_RESUME + 1)
    # The replaced instructions: sub esp, 0x10; mov eax, [esp + 0x14] (the target).
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 0x10
    assert emu.reg_read(x86.UC_X86_REG_EAX) == 4
    for reg, value in ((x86.UC_X86_REG_EBX, 0xBBBBBBBB), (x86.UC_X86_REG_ESI, 0x51515151),
                       (x86.UC_X86_REG_EDI, 0xD1D1D1D1), (x86.UC_X86_REG_EBP, 0xB0B0B0B0)):
        assert emu.reg_read(reg) == value
    hp = " " + " ".join(f"{value:08X}" for value in HP)
    assert len(calls) == 1
    assert calls[0][16:] == f" FFFFFFFF {caller:08X} 04{hp} {MOTION:04X}\r\n"


def _writes(emu):
    calls = []

    def on_code(uc, address, _size, _data):
        if address == STUBS[h.IAT_CREATE_FILE_A][0]:
            uc.reg_write(x86.UC_X86_REG_EAX, 0x1234)
        elif address == STUBS[h.IAT_WRITE_FILE][0]:
            esp = uc.reg_read(x86.UC_X86_REG_ESP)
            args = struct.unpack("<5I", uc.mem_read(esp + 4, 20))
            calls.append(bytes(uc.mem_read(args[1], args[2])).decode())
            uc.reg_write(x86.UC_X86_REG_EAX, 1)
    emu.hook_add(unicorn.UC_HOOK_CODE, on_code)
    return calls


TASK_LIST = 0x01D96D78
NODE = 0x00D00400
STEPS = {  # task functions: [esp+4] is the node
    "advance": (0x00D00500, "8B 44 24 04 FE 40 0D 31 C0 C3"),   # inc byte [node+0xD]; return 0
    "wait": (0x00D00520, "31 C0 C3"),                          # nothing changes
    "finish": (0x00D00540, "B8 02 00 00 00 C3"),               # return 2: the task is done
}


def _run_task(emu, step: str):
    function, code = STEPS[step]
    emu.mem_write(function, bytes.fromhex(code))
    emu.mem_write(NODE, bytes(0x14))
    emu.mem_write(NODE + 8, struct.pack("<I", function))
    emu.mem_write(NODE + 0xD, bytes((3,)))
    emu.mem_write(h.TASK_RESUME, b"\xF4")
    esp = STACK + 0x1000
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_ESI, NODE)
    emu.reg_write(x86.UC_X86_REG_EBP, TASK_LIST)
    emu.reg_write(x86.UC_X86_REG_EDI, 0xD1D1D1D1)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xBBBBBBBB)
    emu.emu_start(h.CAVE + h.ENTRY["task"], h.TASK_RESUME + 1, count=5000)
    # The replaced call ran and its result reached the runner unchanged.
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp
    assert emu.reg_read(x86.UC_X86_REG_ESI) == NODE
    assert emu.reg_read(x86.UC_X86_REG_EBP) == TASK_LIST
    assert emu.reg_read(x86.UC_X86_REG_EDI) == 0xD1D1D1D1
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0xBBBBBBBB
    return emu.reg_read(x86.UC_X86_REG_EAX)


def test_a_task_line_marks_each_state_change_and_the_finish():
    hp = " " + " ".join(f"{value:08X}" for value in HP)
    emu = _machine()
    calls = _writes(emu)
    assert _run_task(emu, "advance") == 0
    assert calls[-1][16:] == f" {STEPS['advance'][0]:08X} {TASK_LIST:08X} 04{hp} {MOTION:04X}\r\n"
    assert _run_task(emu, "wait") == 0
    assert len(calls) == 1, "a task that stays in its state writes nothing"
    assert _run_task(emu, "finish") == 2
    assert calls[-1][16:] == f" {STEPS['finish'][0]:08X} {TASK_LIST:08X} FF{hp} {MOTION:04X}\r\n"


def test_a_script_line_names_the_script_and_its_model():
    hp = " " + " ".join(f"{value:08X}" for value in HP)
    emu = _machine()
    calls = _writes(emu)
    emu.mem_write(h.SCRIPT_RESUME, b"\xF4")
    esp = STACK + 0x1000
    emu.mem_write(esp, struct.pack("<4I", 0xCAFEBABE, 0x1014, 2, 0))  # return, id, model, 0
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xBBBBBBBB)
    emu.emu_start(h.CAVE + h.ENTRY["script"], h.SCRIPT_RESUME + 1, count=5000)
    # The replaced pushes ran: ebx, 1, 0x14.
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 12
    assert struct.unpack("<3I", emu.mem_read(esp - 12, 12)) == (0x14, 1, 0xBBBBBBBB)
    assert calls == [calls[0]] and calls[0][16:] == f" {h.SCRIPT_OWNER:08X} 00001014 02{hp} {MOTION:04X}\r\n"


def test_a_sequence_line_names_the_model_the_caller_and_the_sequence():
    hp = " " + " ".join(f"{value:08X}" for value in HP)
    emu = _machine()
    calls = _writes(emu)
    emu.mem_write(h.SEQUENCE_RESUME, b"\xF4")
    esp = STACK + 0x1000
    caller, model = 0x00504441, 0x01D973F8
    emu.mem_write(esp, struct.pack("<3I", caller, model, 0x0B))
    emu.reg_write(x86.UC_X86_REG_ESP, esp)
    emu.reg_write(x86.UC_X86_REG_EBX, 0xBBBBBBBB)
    emu.emu_start(h.CAVE + h.ENTRY["sequence"], h.SEQUENCE_RESUME + 1, count=5000)
    # The replaced instructions ran: push ebx; mov ebx, [esp + 0xc] (the sequence).
    assert emu.reg_read(x86.UC_X86_REG_ESP) == esp - 4
    assert struct.unpack("<I", emu.mem_read(esp - 4, 4))[0] == 0xBBBBBBBB
    assert emu.reg_read(x86.UC_X86_REG_EBX) == 0x0B
    assert calls == [f"{calls[0][:16]} {model:08X} {caller:08X} 0B{hp} {MOTION:04X}\r\n"]


def test_off_writes_nothing_and_on_hooks_the_verified_bytes():
    assert h.build_hext(False) == ""
    text = h.build_hext(True)
    assert f"{h.HOOK:X} = E9" in text
    assert f"{h.DAMAGE_HOOK:X} = E9" in text
    assert f"{h.TASK_HOOK:X} = E9" in text and f"{h.SCRIPT_HOOK:X} = E9" in text
    assert len(h.task_hook_bytes()) == len(h.TASK_ORIGINAL)
    assert len(h.script_hook_bytes()) == len(h.SCRIPT_ORIGINAL)
    assert len(h.sequence_hook_bytes()) == len(h.SEQUENCE_ORIGINAL)
    assert f"{h.SEQUENCE_HOOK:X} = E9" in text
    assert len(h.damage_hook_bytes()) == len(h.DAMAGE_ORIGINAL)
    assert h.hook_bytes()[:1] == b"\xE9" and len(h.hook_bytes()) == len(h.HOOK_ORIGINAL)
    assert h.CAVE + len(h.CODE) <= h.DATA
    with pytest.raises(ValueError):
        h.build_hext("yes")


def test_cave_bytes_match_their_source():
    keystone = pytest.importorskip("keystone")
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    assert bytes(ks.asm(h.ASSEMBLY, h.CAVE)[0]) == h.CODE
    probe = h.ASSEMBLY.split("\ndamage:")[0] + "\ndamage:\n nop\nwrite_line:\n nop"
    assert len(ks.asm(probe, h.CAVE)[0]) - 2 == h.ENTRY["damage"]
