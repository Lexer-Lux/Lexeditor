"""Execute the native GF row index calculation and its patched bounds check."""
from pathlib import Path
import hashlib
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8 import menu_qol_issue_61 as source
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def row_is_accepted(native, page, row, count, patched):
    emu = Uc(UC_ARCH_X86, UC_MODE_32)
    emu.mem_map(0x004FD000, 0x1000)
    emu.mem_write(0x004FD4F0, native)
    if patched:
        emu.mem_write(source.ABILITY_ROW_BOUNDS_BRANCH, source.ABILITY_ROW_BOUNDS_SAFE)
    emu.mem_map(0x01D8D000, 0x1000)
    emu.mem_write(0x01D8DDE8, struct.pack('<I', count))
    emu.mem_map(0x03000000, 0x1000)
    stack = 0x03000800
    sentinel = 0x004FD600
    # Return address, argument 1, native fallback result, page, row.
    emu.mem_write(stack, struct.pack('<5I', sentinel, 0, 0x12345678,
                                   page & 0xFFFFFFFF, row & 0xFFFFFFFF))
    emu.reg_write(UC_X86_REG_ESP, stack)
    accepted = []
    def stop(machine, address, size, data):
        if address in (0x004FD50F, sentinel):
            accepted.append(address == 0x004FD50F)
            machine.emu_stop()
    emu.hook_add(UC_HOOK_CODE, stop)
    emu.emu_start(0x004FD4F0, sentinel + 1, count=100)
    assert len(accepted) == 1
    if not accepted[0]:
        assert emu.reg_read(UC_X86_REG_EAX) == 0x12345678
        assert emu.reg_read(UC_X86_REG_ESP) == stack + 4
    return accepted[0]


def main():
    executable = EXE.read_bytes()
    assert hashlib.sha256(executable).hexdigest() == source.SUPPORTED_EXE_SHA256
    offset = source.ABILITY_ROW_BOUNDS_BRANCH - 0x400000
    assert executable[offset:offset + 2] == source.ABILITY_ROW_BOUNDS_ORIGINAL
    native = executable[0xFD4F0:0xFD50F]
    # The original executable enters record access for a previous-page index
    # of -1. This reproduces the missing lower bound, not the reported crash.
    assert row_is_accepted(native, -1, 0, 22, False)
    cases = 0
    for count in range(23):
        for page in (-2, -1, 0, 1, 2, 3):
            for row in range(11):
                index = page * 11 + row
                assert row_is_accepted(native, page, row, count, True) == (0 <= index < count)
                cases += 1
    assert source.build_enhanced_ability_menu_hext(False) == ''
    assert '4FD508 = 72 05' in source.build_enhanced_ability_menu_hext(True)
    for gf in range(16):
        for count in (0, 1, 11, 12, 22):
            for output in (0, 0x01D8DD30):
                results = []
                for patched in (False, True):
                    emu = Uc(UC_ARCH_X86, UC_MODE_32)
                    emu.mem_map(0x004AC000, 0x1000)
                    emu.mem_write(0x004ACB70, executable[0xACB70:0xACE46])
                    emu.mem_map(0x027A1000, 0x1000)
                    if patched:
                        emu.mem_write(source.ENHANCED_ABILITY_ALPHA_CAVE,
                                      source.build_enhanced_ability_order_code_cave())
                        emu.mem_write(source.ABILITY_LIST_RETURN_HOOK,
                                      source.relative_branch(b'\xE9', source.ABILITY_LIST_RETURN_HOOK,
                                                             source.ENHANCED_ABILITY_ALPHA_CAVE))
                    emu.mem_map(0x01CF0000, 0xA0000)
                    bits = sum(1 << i for i in range(1, count + 1))
                    emu.mem_write(0x01CFDCBC + gf * 0x44, bits.to_bytes(16, 'little'))
                    emu.mem_map(0x03000000, 0x2000)
                    stack = 0x03001000
                    emu.mem_write(stack, struct.pack('<4I', 0x004ACE46, gf, output, 0))
                    emu.reg_write(UC_X86_REG_ESP, stack)
                    emu.emu_start(0x004ACB70, 0x004ACE46, count=20000)
                    assert emu.reg_read(UC_X86_REG_EAX) == count
                    assert emu.reg_read(UC_X86_REG_ESP) == stack + 4
                    rows = bytes(emu.mem_read(0x01D8DD30, 22 * 8))
                    results.append([rows[n:n+8] for n in range(0, count * 8, 8)])
                assert results[1] == (source.stable_ability_order(results[0]) if output else results[0])
    print('Full native GF builder + injected sorter: 160 state pairs passed, including count-only calls')
    print(f'GF row bounds: {cases} native x86 execution cases passed')


if __name__ == '__main__':
    main()
