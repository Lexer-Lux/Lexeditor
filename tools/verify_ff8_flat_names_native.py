"""Regression for the captured GF page crash: compressed stat names as glyphs."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8 import kernel_text, flat_stat_abilities as flat, formats
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EDI, UC_X86_REG_ESP, UC_X86_REG_ECX

EXE = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe')


def native_glyphs(encoded):
    m = Uc(UC_ARCH_X86, UC_MODE_32)
    m.mem_map(0x4BD000, 0x2000)
    exe = EXE.read_bytes()
    m.mem_write(0x4BDE9E, exe[0xBDE9E:0xBDEA9])
    m.mem_write(0x4BDF3A, exe[0xBDF3A:0xBDF67])
    m.mem_map(0x3000000, 0x1000)
    m.mem_write(0x3000100, encoded)
    m.reg_write(UC_X86_REG_ESP, 0x3000800)
    glyphs = []
    for i in range(len(encoded)):
        m.mem_write(0x3000830, (0x3000100+i).to_bytes(4,'little'))
        m.emu_start(0x4BDE9E, 0x4BDEA9, count=20)
        m.emu_start(0x4BDF3A, 0x4BDF67, count=20)
        glyphs.append(m.reg_read(UC_X86_REG_EDI))
    return glyphs


def main():
    # Captured dump: Mag+20 encoded as 51 FF 31 23 21. FF was consumed as
    # glyph DF, not expanded to 'ag'; its missing texture caused the null read.
    old = bytes.fromhex('51 FF 31 23 21')
    assert native_glyphs(old)[1] == 0xDF
    for original in flat._VANILLA_NAMES:
        for name in (original, original[:-1]):
            encoded = kernel_text.encode(name, compress=False)
            assert all(byte < 0xE8 for byte in encoded)
            assert native_glyphs(encoded) == [byte-0x20 for byte in encoded]
            assert kernel_text.decode(encoded) == name
    print('38 stat names execute as plain native glyphs; captured compressed-name defect reproduced')


if __name__ == '__main__':
    main()
