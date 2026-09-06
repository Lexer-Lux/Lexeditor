"""Execute production no-consumption assembly and native cast debit seams.

The test-only assembler translates the production MASM block mechanically to
GNU Intel syntax. --exe tests the original supported game instructions; --driver
also executes the actual exported hook compiled into the delivered PE32 DLL.
No game installation, save or running process is changed. Requires Unicorn,
pefile, and (without --driver) GNU binutils as/objcopy.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from games.ff8 import max_spell

EXPECTED='064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
SOURCE=ROOT/'games/ff8/ffnx_gameplay_extensions/ffnx-src/lexeditor_ff8_stock_tweaks.cpp'
HOOK=0x2800000
DATA=0x2810000


def hook_bytes() -> bytes:
    source=SOURCE.read_text(encoding='utf-8')
    asm=source.split('__asm {',1)[1].split('}',1)[0]
    asm=re.sub(r'\b([0-9][0-9A-Fa-f]*)h\b',lambda m:'0x'+m[1],asm)
    asm=asm.replace('ds:','').replace('g_nonnegative','0x2810000').replace('g_underflow','0x2810004')
    with tempfile.TemporaryDirectory(prefix='ff8-debit-asm-') as directory:
        root=Path(directory);(root/'hook.s').write_text('.intel_syntax noprefix\n.text\n'+asm,encoding='utf-8')
        subprocess.run(['as','--32',str(root/'hook.s'),'-o',str(root/'hook.o')],check=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',str(root/'hook.o'),str(root/'hook.bin')],check=True)
        return (root/'hook.bin').read_bytes()


def run(exe: Path|None, driver: Path|None) -> None:
    import pefile
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
    from unicorn.x86_const import (UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_EBP,
        UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_EDI,UC_X86_REG_ESI,UC_X86_REG_ESP,UC_X86_REG_EIP)
    # Originals are the separately guarded reviewed instructions. A supplied
    # executable must confirm these exact seams before it is used for testing.
    battle=bytes.fromhex('0F BE 01 2B C7 79 04 33 C0 EB 04 3B C5 75 04 C6 41 FF 00 88 01')
    field=bytes.fromhex('8A 1C 45 F9 E0 CF 01 FE CB 88 1C 45 F9 E0 CF 01')
    if exe:
        raw=exe.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=EXPECTED: raise ValueError('Unsupported private executable')
        pe=pefile.PE(data=raw)
        assert pe.get_data(0x4FE706-pe.OPTIONAL_HEADER.ImageBase,len(battle))==battle
        assert pe.get_data(0x4F3020-pe.OPTIONAL_HEADER.ImageBase,len(field))==field
        with exe.open('rb') as stream: max_spell.verify_executable(stream)
    vm=Uc(UC_ARCH_X86,UC_MODE_32)
    vm.mem_map(0x400000,0x100000)
    vm.mem_map(0x1CF0000,0x90000)
    vm.mem_map(HOOK,0x20000)
    vm.mem_write(DATA,struct.pack('<II',0x4FE711,0x4FE70F))
    entry=HOOK
    if driver:
        pe=pefile.PE(str(driver));base=pe.OPTIONAL_HEADER.ImageBase
        assert pe.FILE_HEADER.Machine==0x14c
        size=(pe.OPTIONAL_HEADER.SizeOfImage+0xfff)&~0xfff
        vm.mem_map(base,size);vm.mem_write(base,pe.get_memory_mapped_image())
        exported=[item for item in pe.DIRECTORY_ENTRY_EXPORT.symbols
                  if item.name==b'lexeditor_ff8_no_consume_battle_debit']
        assert len(exported)==1,'Delivered DLL lacks verified cast-debit hook'
        entry=base+exported[0].address
    else:
        vm.mem_write(HOOK,hook_bytes())
    for enabled in (False,True):
        for magic in (False,True):
            for stock in range(256):
                for amount in (0,1,2,3):
                    vm.mem_write(0x4FE706,battle)
                    # Existing Max Spell unsigned-stock repair, valid for
                    # both controllers; no-consumption must coexist with it.
                    vm.mem_write(0x4FE706,bytes.fromhex('0F B6 01'))
                    if enabled:
                        vm.mem_write(0x4FE709,b'\xe9'+struct.pack('<i',entry-0x4FE709-5)+b'\x90')
                    vm.ctl_remove_cache(0x4FE706,0x4FE71B)
                    vm.mem_write(0x1D768D0,struct.pack('<I',0x4C8820 if magic else 0x4C8B30))
                    vm.mem_write(DATA+0x100,bytes((1,stock,0xA5,0xB6,0xC7)))
                    vm.reg_write(UC_X86_REG_ECX,DATA+0x101);vm.reg_write(UC_X86_REG_EDI,amount)
                    vm.reg_write(UC_X86_REG_EBP,0);vm.reg_write(UC_X86_REG_ESP,DATA+0x800)
                    for register,value in ((UC_X86_REG_EDX,7),(UC_X86_REG_EBX,0xABCDEF),(UC_X86_REG_ESI,32)):
                        vm.reg_write(register,value)
                    vm.emu_start(0x4FE706,0x4FE71B,count=30)
                    assert vm.reg_read(UC_X86_REG_EIP)==0x4FE71B
                    expected=stock if (enabled and magic) else max(0,stock-amount)
                    actual=vm.mem_read(DATA+0x100,5)
                    assert actual[1]==expected,(enabled,magic,stock,amount,actual)
                    assert actual[0]==(1 if expected else 0)
                    assert actual[2:]==b'\xA5\xB6\xC7'
                    assert vm.reg_read(UC_X86_REG_EDX)==7 and vm.reg_read(UC_X86_REG_ESI)==32
                    assert vm.reg_read(UC_X86_REG_EBX)==0xABCDEF and vm.reg_read(UC_X86_REG_EDI)==amount
        for stock in range(1,256):
            vm.mem_write(0x4F3020,field)
            if enabled:vm.mem_write(0x4F3027,b'\x90\x90')
            vm.ctl_remove_cache(0x4F3020,0x4F3030)
            vm.reg_write(UC_X86_REG_EAX,0);vm.reg_write(UC_X86_REG_EBX,0x123400)
            vm.mem_write(0x1CFE0F9,bytes((stock,)))
            vm.emu_start(0x4F3020,0x4F3030,count=5)
            assert vm.mem_read(0x1CFE0F9,1)[0]==(stock if enabled else stock-1)
    print('PASS: production cast-debit assembly: 256 stock values, 4 charges, Magic/Item separation, enabled/disabled, field casts and native register/metadata preservation.')
    if exe: print('PASS: cast seams and Max Spell byte guards confirmed against the supplied private executable.')
    if driver: print('PASS: executed the actual no-consumption hook from the linked Windows DLL.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path);parser.add_argument('--driver',type=Path)
    args=parser.parse_args();run(args.exe,args.driver)
