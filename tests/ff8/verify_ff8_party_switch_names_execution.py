"""Execute native name lookup and text parser used by the reserve selector."""
from verify_ff8_scan_draw_execution import machine, run, put32, read32, STACK
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
for text,expected in ((bytes((3,0x30,0)),0),(bytes((0x50,0x51,0x52,0)),3)):
    u=machine();u.mem_write(0x1CFDC70,text)
    put32(u,STACK+4,0);run(u,0x47EB50)
    assert u.reg_read(UC_X86_REG_EAX)==0x1CFDC70
    u.reg_write(UC_X86_REG_ESP,STACK)
    for i,value in enumerate((0x2802000,0x2803000,38,32,0x1CFDC70,7)):put32(u,STACK+4+i*4,value)
    glyphs=[]
    def stub(uc,address,size,_):
        if address in (0x49B080,0x403E00,0x49C8F0):
            sp=uc.reg_read(UC_X86_REG_ESP)
            if address==0x403E00:uc.reg_write(UC_X86_REG_EAX,0x2804000)
            if address==0x49C8F0:
                glyphs.append(read32(uc,sp+8));uc.reg_write(UC_X86_REG_EAX,read32(uc,sp+4))
            uc.reg_write(UC_X86_REG_EIP,read32(uc,sp));uc.reg_write(UC_X86_REG_ESP,sp+4)
    u.hook_add(UC_HOOK_CODE,stub);run(u,0x4A7250)
    assert len(glyphs)==expected
print('PASS: old name control produces zero glyphs; native saved name produces all three glyphs')

# Native battle menus submit the string before its panel. The ordering table
# renders these packets in reverse order; reversing this hides the names.
from pathlib import Path
u=machine()
assert bytes(u.mem_read(0x4AF589,5)) == bytes.fromhex("E8 C2 7C FF FF")
assert bytes(u.mem_read(0x4AF597,5)) == bytes.fromhex("E8 74 7F FF FF")
source=(Path(__file__).resolve().parents[2]/"plugins/ff8/ffnx_party_switch/ffnx-src/lexeditor_ff8_party_switch.cpp").read_text()
draw=source.split("std::uint32_t __cdecl draw(",1)[1].split("void abort_swap()",1)[0]
assert draw.rindex("0x4A7250") < draw.index("0x4A7510")
print("PASS: selector submits names and cursor before the background, matching native battle menus")
