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
