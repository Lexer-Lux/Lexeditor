"""Execute Party Switch single-slot engine primitives on a read-only fixture.

The fixture is local/private and is not part of the repository. Native model
presentation allocation is recorded, not rendered. This is not a game test.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'_scratch/gf-spellbooks-test-deps'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX
import pefile

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',type=Path,default=ROOT/'_scratch/party-fixture')
    args=parser.parse_args()
    raw=Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
    pe=pefile.PE(data=raw)
    assert pe.get_data(0xbb9e0,5)==bytes.fromhex('83 EC 14 53 55')
    STOP=0x2800000; STACK=0x2908000
    for slot in range(3):
        u=Uc(UC_ARCH_X86,UC_MODE_32)
        u.mem_map(0x400000,0x2600000);u.mem_write(0x400000,pe.get_memory_mapped_image())
        for addr,name in [(0x1cf4000,'battle-data.bin'),(0x1cfd000,'saved-stats.bin'),(0x1d27000,'participants.bin')]:
            u.mem_write(addr,(args.fixture/name).read_bytes())
        def get(a,n):return bytes(u.mem_read(a,n))
        def put(a,v):u.mem_write(a,v)
        party=list(get(0x1cfe74c,3));incoming=next(i for i in range(6) if i not in party)
        outgoing=party[slot]
        oldstats=[get(0x1cff000+i*0x1d0,0x1d0) for i in range(3)]
        oldactors=[get(0x1d27b10+i*0xd0,0xd0) for i in range(3)]
        oldsave=[get(0x1cfe0e8+i*0x98,0x98) for i in range(8)]
        events=[]
        def hook(uc,address,size,_):
            if address==0x500df0:
                sp=uc.reg_read(UC_X86_REG_ESP)
                values=struct.unpack('<4I',uc.mem_read(sp,16))
                events.append(values[1:])
                uc.reg_write(UC_X86_REG_EAX,0x2801000+len(events)*16)
                uc.reg_write(UC_X86_REG_ESP,sp+4)
                uc.reg_write(UC_X86_REG_EIP,values[0])
        u.hook_add(UC_HOOK_CODE,hook)
        def call(addr,*values):
            put(STACK,struct.pack('<'+'I'*(len(values)+1),STOP,*values))
            u.reg_write(UC_X86_REG_ESP,STACK);u.emu_start(addr,STOP,count=1000000)
            assert u.reg_read(UC_X86_REG_EIP)==STOP,hex(addr)
        # Execute the exact native saveback HP slice with this actor selected.
        # The native loop's EAX/EDX inputs choose the one slot, no unrelated
        # native teardown or all-party recomputation is called.
        from unicorn.x86_const import UC_X86_REG_EDX
        u.reg_write(UC_X86_REG_EAX,0x1d27b28+slot*0xd0)
        u.reg_write(UC_X86_REG_EDX,slot)
        u.emu_start(0x48b8c1,0x48b8da,count=100)
        saved=0x1cfe0e8+outgoing*0x98
        assert get(saved,2)==oldactors[slot][0x18:0x1a]
        # Execute native stock-copy loop for the selected actor only.
        from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESI
        u.reg_write(UC_X86_REG_EAX,0x1cff083+slot*0x1d0)
        u.reg_write(UC_X86_REG_ECX,saved+0x11)
        u.reg_write(UC_X86_REG_ESI,32)
        u.emu_start(0x486d1c,0x486d30,count=1000)
        assert get(saved+0x10,64)==b''.join(oldstats[slot][0x82+i*5:0x84+i*5] for i in range(32))
        put(0x1cfe74c+slot,bytes((incoming,)))
        for fn,params in [(0x495530,(incoming,slot)),(0x495960,(incoming,slot)),(0x495ec0,()),(0x48b5f0,(slot,)),(0x48b310,(slot,)),(0x484490,(slot,)),(0x47dd30,(slot,)),(0x47daf0,(slot,)),(0x485ff0,())]:call(fn,*params)
        assert get(0x1cff1c3+slot*0x1d0,1)==bytes((incoming,))
        assert get(0x1d27bcb+slot*0xd0,1)==bytes((incoming,))
        assert get(0x1d27b24+slot*0xd0,4)==b'\0'*4
        assert [e[0] for e in events][-2:]==[0x66,0x67]
        for other in range(3):
            if other==slot:continue
            assert get(0x1cff000+other*0x1d0,0x1d0)==oldstats[other],('stats',slot,other)
            assert get(0x1d27b10+other*0xd0,0xd0)==oldactors[other],('actor',slot,other)
        for character in range(8):
            # Junctions/abilities must remain unchanged for all eight records.
            assert get(0x1cfe0e8+character*0x98+0x50,0x48)==oldsave[character][0x50:]
        # Native ready-event consumer: removal spends only the chosen actor;
        # reinsertion on abort restores it without removing another actor.
        put(0x1d75410,b'\0'*4);put(0x1d75430,b'\0'*4)
        for i in range(3): put(0x1d753f0+i*8,struct.pack('<Ihh',0,i,0))
        record=0x2805000
        def queue_stub(uc,address,size,_):
            returns={0x503220:1,0x5032a0:record,0x5032e0:0,0x4bb840:0}
            if address in returns:
                sp=uc.reg_read(UC_X86_REG_ESP)
                ret=struct.unpack('<I',uc.mem_read(sp,4))[0]
                uc.reg_write(UC_X86_REG_EAX,returns[address])
                uc.reg_write(UC_X86_REG_ESP,sp+4);uc.reg_write(UC_X86_REG_EIP,ret)
        u.hook_add(UC_HOOK_CODE,queue_stub)
        def event(actor,kind):
            put(record,struct.pack('<BxHI',actor,kind,0));call(0x4ad400)
        for i in range(3):event(i,0x11)
        assert get(0x1d75410,4)==struct.pack('<I',7)
        event(slot,0x12)
        assert get(0x1d75410,4)==struct.pack('<I',7 & ~(1<<slot))
        event(slot,0x11)
        assert get(0x1d75410,4)==struct.pack('<I',7)
        print(f'PASS slot{slot}: native outgoing saveback; incoming parser, GF, participant, ATB, model events; other actors unchanged')
if __name__=='__main__':main()
