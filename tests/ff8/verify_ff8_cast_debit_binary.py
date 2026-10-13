"""Execute the linked driver's cast-debit seam without importing library tweaks.

This checks native driver infrastructure. Tweak generation and settings tests
remain in the mod library; no game installation or process is modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct


def run(driver: Path) -> None:
    import pefile
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (UC_X86_REG_EBX, UC_X86_REG_EBP,
        UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_EDI, UC_X86_REG_ESI,
        UC_X86_REG_ESP, UC_X86_REG_EIP)

    pe = pefile.PE(str(driver), fast_load=True)
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
    assert pe.FILE_HEADER.Machine == 0x14C, 'Cast-debit hook requires PE32'
    base = pe.OPTIONAL_HEADER.ImageBase
    exports = [item for item in pe.DIRECTORY_ENTRY_EXPORT.symbols
               if item.name == b'lexeditor_ff8_no_consume_battle_debit']
    assert len(exports) == 1, 'Delivered DLL lacks the cast-debit hook'
    entry = base + exports[0].address
    vm = Uc(UC_ARCH_X86, UC_MODE_32)
    vm.mem_map(0x400000, 0x100000)
    vm.mem_map(0x1CF0000, 0x90000)
    data = 0x2810000
    vm.mem_map(data, 0x10000)
    vm.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    vm.mem_write(base, pe.get_memory_mapped_image())
    # Reviewed native instructions with the independent unsigned-stock repair.
    battle = bytes.fromhex('0F B6 01 2B C7 79 04 33 C0 EB 04 3B C5 75 04 C6 41 FF 00 88 01')
    for enabled in (False, True):
        for magic in (False, True):
            for stock in range(256):
                for amount in (0, 1, 2, 3):
                    vm.mem_write(0x4FE706, battle)
                    if enabled:
                        vm.mem_write(0x4FE709, b'\xE9' + struct.pack('<i', entry - 0x4FE70E) + b'\x90')
                    vm.ctl_remove_cache(0x4FE706, 0x4FE71B)
                    vm.mem_write(0x1D768D0, struct.pack('<I', 0x4C8820 if magic else 0x4C8B30))
                    vm.mem_write(data + 0x100, bytes((1, stock, 0xA5, 0xB6, 0xC7)))
                    vm.reg_write(UC_X86_REG_ECX, data + 0x101)
                    vm.reg_write(UC_X86_REG_EDI, amount)
                    vm.reg_write(UC_X86_REG_EBP, 0)
                    vm.reg_write(UC_X86_REG_ESP, data + 0x800)
                    for register, value in ((UC_X86_REG_EDX, 7), (UC_X86_REG_EBX, 0xABCDEF), (UC_X86_REG_ESI, 32)):
                        vm.reg_write(register, value)
                    vm.emu_start(0x4FE706, 0x4FE71B, count=30)
                    assert vm.reg_read(UC_X86_REG_EIP) == 0x4FE71B
                    expected = stock if enabled and magic else max(0, stock - amount)
                    actual = vm.mem_read(data + 0x100, 5)
                    assert actual[1] == expected, (enabled, magic, stock, amount, actual)
                    assert actual[0] == (1 if expected else 0)
                    assert actual[2:] == b'\xA5\xB6\xC7'
                    for register, value in ((UC_X86_REG_EDX, 7), (UC_X86_REG_ESI, 32),
                                            (UC_X86_REG_EBX, 0xABCDEF), (UC_X86_REG_EDI, amount)):
                        assert vm.reg_read(register) == value
    print('PASS: linked cast-debit hook: all 256 stock values, four charges, Magic/Item separation, enabled/disabled behavior and register/metadata preservation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, required=True)
    run(parser.parse_args().driver)
