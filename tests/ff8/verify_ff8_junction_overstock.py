"""Native execution regression for old save stocks above the Max Spell cap."""
from pathlib import Path
from io import BytesIO
import re
import struct
import sys
import hashlib
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from plugins.ff8 import max_spell
raw=Path('D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/FF8_EN.exe').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
max_spell.verify_executable(BytesIO(raw))
registers=[UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EBX]

def machine(cap):
    vm=Uc(UC_ARCH_X86,UC_MODE_32);vm.mem_map(0,0x3000000)
    vm.mem_write(0x400000,raw)
    for address,payload in re.findall(r'(?m)^([0-9A-F]+) = ([0-9A-F ]+)$',max_spell.build_hext(True,cap)):
        vm.mem_write(int(address,16),bytes.fromhex(payload))
    return vm

cases=0
for cap in (1,10,100,255):
    vm=machine(cap)
    for address,original,register in max_spell.JUNCTION_STOCK_READS:
        index_register=UC_X86_REG_EAX if '45' in original.split() else UC_X86_REG_ECX
        for stock in range(256):
            for reg in registers: vm.reg_write(reg,0x12345600)
            vm.reg_write(index_register,0)
            before={reg:vm.reg_read(reg) for reg in registers}
            vm.reg_write(UC_X86_REG_ESP,0x2900000)
            vm.reg_write(UC_X86_REG_EFLAGS,0x246)
            vm.mem_write(0x1CFE0F9,bytes([stock]))
            vm.emu_start(address,address+7,count=30)
            for reg,value in before.items():
                expected=(value&~255)|min(stock,cap) if reg==registers[register] else value
                assert vm.reg_read(reg)==expected,(hex(address),cap,stock,reg)
            assert vm.reg_read(UC_X86_REG_EFLAGS)==0x246
            assert vm.mem_read(0x1CFE0F9,1)[0]==stock
            cases+=1

# Reproduce Squall's actual curve and 79 Thundaga stock: base 2 + 237 = 239.
# Run the native standard-stat branch, including the installed scale cave.
def squall(bounded):
    vm=machine(10);sp=0x2900000
    vm.reg_write(UC_X86_REG_ESP,sp);vm.reg_write(UC_X86_REG_ECX,0)
    vm.reg_write(UC_X86_REG_EDI,0x2800000);vm.reg_write(UC_X86_REG_EBP,0)
    vm.mem_write(0x2800000,bytes([6,13,0,251]))
    vm.mem_write(0x1CFE0F9,bytes([79]))
    for offset,value in ((0x10,30),(0x14,0),(0x1C,16)):
        vm.mem_write(sp+offset,struct.pack('<I',value))
    if not bounded: vm.mem_write(0x4966E5,bytes.fromhex('8A 14 4D F9 E0 CF 01'))
    vm.emu_start(0x4966E5,0x4966CA,count=150)
    return vm.reg_read(UC_X86_REG_EDX)
assert squall(False)==239
assert squall(True)==32
print(f'PASS: {cases} native stock-reader cases; registers, flags and save stock preserved; Squall MAG 239 -> 32')
