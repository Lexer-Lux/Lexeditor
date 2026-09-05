"""Native HUD visibility, row arguments and glyph metadata evidence; no game launch."""
from verify_ff8_scan_draw_execution import machine, run, put32, read32, pe, STACK, STOP
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
import struct
for address,target in ((0x4B17D5,0x4B0F10),(0x4B1100,0x4A7210),(0x4B127B,0x4A7210)):
    assert pe.get_data(address-0x400000,5)==b'\xe8'+struct.pack('<i',target-address-5)
# Three native row records are selected only when both active and visible.
for visible in (False,True):
    u=machine(); context=0x2801000
    put32(u,0x1D6D490,context)
    u.mem_write(0x1D7686C,struct.pack('<H',0x1000))
    put32(u,STACK+4,0);put32(u,STACK+8,0x2802000);put32(u,STACK+12,0);put32(u,STACK+16,0)
    for i in range(3):
        u.mem_write(0x1D76971+i*0x6C,b'\x01')
        u.mem_write(0x1D76978+i*0x6C,bytes((int(visible and i!=1),)))
    u.mem_write(context+0x21,b'\x00')
    rows=[]
    def stub(uc,address,size,_):
        if address==0x4B0F10:
            sp=uc.reg_read(UC_X86_REG_ESP);rows.append(read32(uc,sp+4))
            uc.reg_write(UC_X86_REG_EIP,read32(uc,sp));uc.reg_write(UC_X86_REG_ESP,sp+4)
    u.hook_add(UC_HOOK_CODE,stub);run(u,0x4B1740)
    assert rows==([0x1D76928,0x1D76A00] if visible else [])
# Native glyph decoder uses width/height bytes and signed offsets, not fixed font size.
assert pe.get_data(0xB786A,16)==bytes.fromhex('8B C8 8B D0 81 E1 FF 00 FF 00 C1 E2 10 89 4E 14')
assert pe.get_data(0xB787E,14)==bytes.fromhex('C1 FA 18 03 D1 8B 4C 24 24 C1 F8 18 03 C1')
print('PASS: native HUD per-row visibility and exact glyph extent decoder')




