"""Execute the native vehicle clamp and, on CI, the linked throttle hook.

The policy's production C++ is exercised by verify_ff8_vehicle_drive.py. Here
its cdecl call is intercepted so the compiled hook's stack, registers, flags,
and continuation into the original game instructions can be checked in isolation.
An optional private executable verifies the reviewed instruction seam read-only.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct

ENTRY = 0x55801D
RESUME = 0x558023
STOP = 0x558075
SPEED = 0x20409E8
EXPECTED = '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
CLAMP = bytes.fromhex('8B C6 F7 D8 3B D0 7D 04 8B D0 EB 42 3B D6 7E 44 8B D6 EB 3A')


def run(exe: Path | None, driver: Path | None) -> None:
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
        UC_X86_REG_ESP, UC_X86_REG_EIP)
    if exe:
        raw = exe.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == EXPECTED, 'Unsupported executable'
        game = pefile.PE(data=raw)
        assert game.get_data(ENTRY-game.OPTIONAL_HEADER.ImageBase,len(CLAMP)) == CLAMP
    vm = Uc(UC_ARCH_X86, UC_MODE_32)
    vm.mem_map(0x550000,0x10000)
    vm.mem_map(0x2040000,0x10000)
    vm.mem_map(0x2800000,0x10000)
    vm.mem_write(ENTRY, CLAMP)
    # Stop before subsequent movement code, at either native exit. The exact
    # original branch destinations above are retained, not a rewritten clamp.
    exits = (0x55806B,0x558071)
    entry = ENTRY
    helper = None
    if driver:
        pe = pefile.PE(str(driver))
        assert pe.FILE_HEADER.Machine == 0x14C
        base = pe.OPTIONAL_HEADER.ImageBase
        vm.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+0xfff)&~0xfff)
        vm.mem_write(base,pe.get_memory_mapped_image())
        exports = {symbol.name: base+symbol.address for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols}
        entry = exports[b'lexeditor_ff8_vehicle_cap_hook']
        helper = exports[b'lexeditor_ff8_vehicle_speed_limit']
    current = {}

    def intercept(machine,address,size,data):
        if address in exits:
            machine.emu_stop()
        elif address == helper:
            stack = machine.reg_read(UC_X86_REG_ESP)
            return_to, argument = struct.unpack('<II',machine.mem_read(stack,8))
            assert argument == current['native']
            # Deliberately clobber all caller-saved registers. The hook must
            # restore the native speed in EDX and preserve the surrounding ECX.
            machine.reg_write(UC_X86_REG_EAX,current['cap'])
            machine.reg_write(UC_X86_REG_ECX,0xBADCA11)
            machine.reg_write(UC_X86_REG_EDX,0xDEADBEEF)
            machine.reg_write(UC_X86_REG_ESP,stack+4)
            machine.reg_write(UC_X86_REG_EIP,return_to)
            current['called'] += 1

    vm.hook_add(UC_HOOK_CODE,intercept)
    count = 0
    for native in (16,32,64,200):
        for cap in (0,1,native//4,native//2,native):
            for speed in (-250,-native,-cap-1,-cap,0,cap,cap+1,native,250):
                current.update(native=native,cap=cap,called=0)
                registers = {UC_X86_REG_EAX:0xABCDEF,UC_X86_REG_EBX:0x21,
                    UC_X86_REG_ECX:0x123456,UC_X86_REG_EDX:speed&0xffffffff,
                    UC_X86_REG_ESI:native if driver else cap,UC_X86_REG_EDI:0x87654321,
                    UC_X86_REG_EBP:0x2800200,UC_X86_REG_ESP:0x2808000}
                for register,value in registers.items(): vm.reg_write(register,value)
                vm.emu_start(entry,STOP,count=100)
                assert vm.reg_read(UC_X86_REG_EIP) in exits
                result = vm.reg_read(UC_X86_REG_EDX)
                if result & 0x80000000: result -= 0x100000000
                assert result == max(-cap,min(cap,speed)), (native,cap,speed,result)
                for register in (UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP):
                    assert vm.reg_read(register) == registers[register], (register,native,cap,speed)
                assert vm.reg_read(UC_X86_REG_ESI) == cap
                assert current['called'] == int(driver is not None)
                count += 1
    print(f'PASS: {count} signed native clamp cases; terrain caps, both directions, stack/register preservation.')
    if exe: print('PASS: guarded clamp bytes match the supported private executable.')
    if driver: print('PASS: actual linked vehicle hook executes through the original clamp branches.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path)
    parser.add_argument('--driver',type=Path)
    args = parser.parse_args()
    run(args.exe,args.driver)
