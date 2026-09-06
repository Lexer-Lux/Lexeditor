"""Verify the narrow Mug/drop patch; --exe executes the real reward builder.

Only native RNG is stubbed to make probabilities and slot selection repeatable.
No game executable bytes, save files or generated game assets are published.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.ff8 import mug_drops
EXPECTED='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'


def run(exe: Path|None) -> None:
    assert mug_drops.build_hext(False)==''
    patch=mug_drops.build_hext(True)
    assert patch.splitlines()[1:]==['486668 = 00']
    for invalid in (0,1,'true',None):
        try:mug_drops.build_hext(invalid)
        except ValueError:pass
        else:raise AssertionError('Accepted non-boolean')
    print('PASS: one-byte drop-only patch, disabled output, strict setting validation.')
    if exe is None:return
    import pefile
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_EIP,UC_X86_REG_ESP,UC_X86_REG_ESI,UC_X86_REG_ECX
    raw=exe.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Unsupported private executable')
    with exe.open('rb') as stream:mug_drops.verify_executable(stream)
    pe=pefile.PE(data=raw);image=pe.get_memory_mapped_image()
    vm=Uc(UC_ARCH_X86,UC_MODE_32);vm.mem_map(0x400000,0x2600000);vm.mem_write(0x400000,image)
    stop,stack,info,ptr=0x2800000,0x2810000,0x2801000,0x2802000
    rolls=[];rolls_used=[]
    def rng(uc,address,size,data):
        if address!=0x48F020:return
        assert rolls,'Unexpected random roll'
        value=rolls.pop(0);rolls_used.append(value)
        sp=uc.reg_read(UC_X86_REG_ESP)
        uc.reg_write(UC_X86_REG_EAX,value)
        uc.reg_write(UC_X86_REG_EIP,struct.unpack('<I',uc.mem_read(sp,4))[0])
        uc.reg_write(UC_X86_REG_ESP,sp+4)
    vm.hook_add(UC_HOOK_CODE,rng)
    def put(address,value,fmt='I'):vm.mem_write(address,struct.pack('<'+fmt,value))
    def invoke(actor):
        put(stack,stop);put(stack+4,actor);vm.reg_write(UC_X86_REG_ESP,stack)
        vm.emu_start(0x486650,stop,count=250)
        assert vm.reg_read(UC_X86_REG_EIP)==stop
    for enabled in (False,True):
        vm.mem_write(mug_drops.DROP_SUPPRESSION_MASK,mug_drops.PATCHED if enabled else mug_drops.ORIGINAL)
        vm.ctl_remove_cache(0x486650,0x48674a)
        for actor in range(3,11):
            put(0x1D27B10+actor*0xD0,ptr);put(ptr,info)
            for tier in range(3):
                put(0x1D28E89+actor*71,tier,'B')
                for slot,roll in enumerate((0,178,229,245)):
                    put(info+0x134+tier*8+slot*2,20+tier*4+slot,'B')
                    put(info+0x135+tier*8+slot*2,2+slot,'B')
                    for stolen in (False,True):
                        flags=0x800 if stolen else 0
                        put(0x1D27B8C+actor*0xD0,flags)
                        for chance,first_roll,full in ((255,0,False),(0,1,False),(255,0,True)):
                            put(info+0x14D,chance,'B');put(0x1D28DFA,24 if full else 0,'B')
                            put(0x1CFF6D8,0,'B');vm.mem_write(0x1CFF5E0,b'\xEE'*48)
                            rolls[:]=[first_roll,roll];rolls_used.clear();invoke(actor)
                            expected=(not stolen or enabled) and first_roll<=chance and not full
                            count=vm.mem_read(0x1D28DFA,1)[0]
                            assert count==(24 if full else int(expected))
                            if expected:
                                assert vm.mem_read(0x1CFF5E0,2)==bytes((20+tier*4+slot,2+slot))
                            else:assert vm.mem_read(0x1CFF5E0,2)==b'\xEE\xEE'
                            assert struct.unpack('<I',vm.mem_read(0x1D27B8C+actor*0xD0,4))[0]==flags
    # The real Mug-already-stolen and death-reward-once guards still branch.
    put(0x1D27B8C+3*0xD0,0x800);vm.reg_write(UC_X86_REG_EAX,0x800)
    vm.emu_start(0x4906CB,0x4906D0,count=2);assert vm.reg_read(UC_X86_REG_EIP)==0x4906D0
    put(0x1D27B8C+3*0xD0,0x40000);vm.reg_write(UC_X86_REG_ESI,3*0xD0)
    vm.emu_start(0x494903,0x494972,count=2);assert vm.reg_read(UC_X86_REG_EIP)==0x494972
    print('PASS: actual reward builder: 8 enemy slots x 3 tiers x 4 reward slots; stolen/unstolen, failed drop roll, full reward list, unchanged flags, Mug-once and death-reward-once.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--exe',type=Path)
    run(parser.parse_args().exe)
