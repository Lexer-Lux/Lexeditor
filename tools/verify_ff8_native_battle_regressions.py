"""Execute FF8's model retirement/loading and GF HUD seams in Unicorn.

Pass a LOCAL, legally obtained Steam English FF8_EN.exe. Never publish the
executable or fixtures containing it. These tests execute native state-machine
bytes, but stub resource I/O; they are not a live-game/visual acceptance test.
Requires: pefile, unicorn. Example:
    python tools/verify_ff8_native_battle_regressions.py --exe C:/Games/FF8/FF8_EN.exe
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct

EXPECTED = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
BASE, STOP, STACK = 0x400000, 0x2800000, 0x2908000
TASK, EVENT = 0x2801000, 0x2802000
MODELS, ACTORS = 0x1D972C0, 0x1D27B10


def run(executable: Path) -> None:
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_EIP,
        UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI)

    data = executable.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED:
        raise ValueError('Unsupported FF8 executable: SHA-256 does not match the verified Steam English version')
    image = pefile.PE(data=data).get_memory_mapped_image()

    def put(u, a, value, fmt='I'):
        u.mem_write(a, struct.pack('<'+fmt, value))

    def get(u, a, fmt='I'):
        return struct.unpack('<'+fmt, u.mem_read(a, struct.calcsize('<'+fmt)))[0]

    def invoke(u, a, *args, end=STOP):
        u.reg_write(UC_X86_REG_ESP, STACK)
        u.mem_write(STACK, struct.pack('<'+'I'*(len(args)+1), STOP, *args))
        u.emu_start(a, end, count=10000)
        assert u.reg_read(UC_X86_REG_EIP) == end, f'Native function did not return: {a:08X}'
        return u.reg_read(UC_X86_REG_EAX)

    def machine():
        u = Uc(UC_ARCH_X86, UC_MODE_32)
        u.mem_map(BASE, 0x2600000)
        u.mem_write(BASE, image)
        return u

    for call, target in ((0x4B17D5,0x4B0F10),(0x4B1100,0x4A7210),(0x4B127B,0x4A7210)):
        assert image[call-BASE:call-BASE+5] == b'\xe8'+struct.pack('<i',target-call-5)

    # Execute the actual name resolver, width measurer and text parser. The
    # old 03/ID control sequence produced a blank row; ordinary saved/kernel
    # names must emit all glyphs, at the same widths used by menu layout.
    for character in range(8):
        u = machine()
        name = bytes((0x50, 0x51, 0x52, 0))
        if character in (0, 4):
            name_address = 0x1CFDC70 if character == 0 else 0x1CFDC7C
        else:
            put(u, 0x1CF3EE0, 0x1000)
            offset = 0x200 + character * 16
            put(u, 0x1CF75EC + character * 36, offset, 'H')
            name_address = 0x1CF3E48 + 0x1000 + offset
        u.mem_write(name_address, name)
        # Even glyphs use the low nibble; odd glyphs the high nibble.
        u.mem_write(0x1D2B818 + (0x50 - 0x20) // 2, bytes((0x65, 0x65)))
        assert invoke(u, 0x47EB50, character) == name_address
        assert invoke(u, 0x4B1850, name_address) == 16  # 5 + 6 + 5
        assert invoke(u, 0x4B1850, 0) == 0
        glyphs = []
        ordering, primitives, menu = 0x2803000, 0x2804000, 0x2805000
        def draw_stub(uc, address, size, user):
            if address not in (0x49B080, 0x403E00, 0x49C8F0):
                return
            sp = uc.reg_read(UC_X86_REG_ESP)
            if address == 0x403E00:
                uc.reg_write(UC_X86_REG_EAX, menu)
            elif address == 0x49C8F0:
                primitive = get(uc, sp + 8)
                glyphs.append((get(uc, primitive + 12, 'h'),
                               get(uc, primitive + 14, 'h')))
                uc.reg_write(UC_X86_REG_EAX, get(uc, sp + 4))
            uc.reg_write(UC_X86_REG_EIP, get(uc, sp))
            uc.reg_write(UC_X86_REG_ESP, sp + 4)
        u.hook_add(UC_HOOK_CODE, draw_stub)
        result = invoke(u, 0x4A7250, ordering, primitives, 38, 32,
                        name_address, 7)
        assert result == primitives + 3 * 24
        assert glyphs == [(38, 32), (43, 32), (49, 32)]
        # Keep the failing old representation as a negative control.
        u.mem_write(name_address, bytes((3, 0x30 + character, 0)))
        glyphs.clear()
        assert invoke(u, 0x4B1850, name_address) == 0
        assert invoke(u, 0x4A7250, ordering, primitives, 38, 32,
                      name_address, 7) == primitives
        assert not glyphs

    for slot in range(3):
        u = machine()
        calls = []
        model, actor = MODELS+slot*0x9C, ACTORS+slot*0xD0
        resource = 0x123400+slot
        # Only external task allocation/resource operations are replaced.
        # The dispatcher, retirement task, effect, actor-removal writes and
        # loader ownership checks execute from the supplied executable.
        stubbed = {0x500DD0: TASK, 0x507080: 0, 0x507070: 0,
                   0x5080D0: 0, 0x501190: 0, 0x485FF0: 0}
        def stub(uc, address, size, user):
            if address not in stubbed:
                return
            sp = uc.reg_read(UC_X86_REG_ESP)
            calls.append((address, get(uc,sp+4), get(uc,sp+8), get(uc,sp+12)))
            uc.reg_write(UC_X86_REG_EAX,stubbed[address])
            uc.reg_write(UC_X86_REG_EIP,get(uc,sp))
            uc.reg_write(UC_X86_REG_ESP,sp+4)
        u.hook_add(UC_HOOK_CODE,stub)
        for other in range(3):
            put(u, MODELS+other*0x9C, 3, 'H')
        put(u,model+4,slot,'B')
        put(u,model+5,0,'B')
        put(u,model+6,0,'B')
        put(u,model+0x64,resource)
        put(u,actor+0x80,0x20,'H')  # existing non-KO status
        put(u,actor+0x7C,1)
        put(u,0x1D97718,0,'B')
        put(u,TASK+0x10,EVENT)
        put(u,TASK+0xD,0,'B')
        put(u,EVENT+4,0)
        put(u,EVENT+8,slot,'H')
        put(u,EVENT+10,4,'H')
        # Regression reproduction: the old code repeatedly loads into an
        # occupied model slot. Every call returns without starting any I/O.
        for _ in range(60):
            assert invoke(u,0x502670,TASK) == 0
        assert get(u,TASK+0xD,'B') == 0
        assert not calls

        put(u,EVENT+2,0x69,'H')
        assert invoke(u,0x502380,EVENT) == 8
        assert calls[-1][:2] == (0x500DD0,0x502ED0)
        assert get(u,model,'H') & 0x10
        assert invoke(u,0x502ED0,TASK) == 0
        assert get(u,model+5,'B') == 5
        assert get(u,TASK+0xD,'B') == 1
        invoke(u,0x50C5F0,model)
        assert get(u,actor+0x80,'H') == 0x21  # why save status before retirement
        invoke(u,0x50C5F0,model)
        assert any(c[:2] == (0x5080D0,resource) for c in calls)
        assert get(u,model,'H') == 0
        assert get(u,model+5,'B') == 0
        assert invoke(u,0x502ED0,TASK) == 2
        assert get(u,EVENT+1,'B') == 0xFF
        for other in range(3):
            if other != slot:
                assert get(u,MODELS+other*0x9C,'H') == 3

        # Dispatch the new load only after native retirement freed ownership.
        put(u,EVENT+2,0x66,'H')
        put(u,EVENT+1,0x80,'B')
        assert invoke(u,0x502380,EVENT) == 8
        assert calls[-1][:2] == (0x500DD0,0x502670)
        invoke(u,0x502670,TASK)
        assert get(u,TASK+0xD,'B') == 2
        assert any(c[:3] == (0x507080,4,slot) for c in calls)
        assert invoke(u,0x502670,TASK) == 2
        assert get(u,model+0x61,'B') == 2

        # Execute the native GF charge-state constructor for a high GF ID:
        # saved HP, computed max, live summoning flag and GF ID must agree.
        stats = 0x1CFF000+slot*0x1D0
        gf = 15-slot
        put(u,0x1CFDCBA+gf*0x44,711,'H')
        put(u,0x1CFF61A+gf*12,1234,'H')
        put(u,stats+0x1C,0,'B')
        u.reg_write(UC_X86_REG_ESI,stats)
        u.reg_write(UC_X86_REG_EDI,slot*0xD0)
        u.reg_write(UC_X86_REG_EBX,gf+0x40)
        invoke(u,0x48D977,end=0x48D9C0)
        assert get(u,stats+0x18,'H') == 711
        assert get(u,stats+0x1A,'H') == 1234
        assert get(u,stats+0x1C,'B') & 1
        assert get(u,stats+0x1D,'B') == gf+0x40

    print('PASS: 8-character native name/glyph/width regression; 3-slot soft-lock reproduction, retirement/resource-release sequence, '
          'new loader completion, isolation of other slots, and GF charge-state ownership.')
    print('Resource I/O was stubbed. No live-game or visual acceptance claimed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    run(parser.parse_args().exe)
