"""Execute the generated command source builder against per-GF learned bits."""
import hashlib
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8 import fixed_command_menu as menu
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import *


def run(gf, learned, mask=None):
    emu = Uc(UC_ARCH_X86, UC_MODE_32)
    emu.mem_map(0x0279F000, 0x2000)
    emu.mem_write(menu.BUILDER_CAVE, menu._builder_payload())
    emu.mem_write(menu.LEARNED_COMMAND_CAVE, menu._learned_command_payload())
    emu.mem_map(0x00495000, 0x1000)
    emu.mem_map(0x01CFD000, 0x3000)
    emu.mem_map(0x03000000, 0x2000)
    actor = 0x03000000
    emu.mem_write(actor + menu.CHARACTER_ID_OFFSET, bytes([3]))
    emu.mem_write(0x01CFE140 + 3 * menu.CHARACTER_STRIDE,
                  struct.pack('<H', (1 << gf) if mask is None else mask))
    # All other GFs know everything: their bits must not unlock this GF.
    for other in range(16):
        bits = ((1 << 128) - 1) if other != gf else sum(1 << a for a in learned)
        emu.mem_write(menu.GF_LEARNED_BITS + other * menu.GF_SAVE_STRIDE,
                      bits.to_bytes(16, 'little'))
    emu.reg_write(UC_X86_REG_ESI, actor)
    emu.reg_write(UC_X86_REG_EDI, 3 * menu.CHARACTER_STRIDE)
    emu.reg_write(UC_X86_REG_ESP, 0x03001800)
    emu.emu_start(menu.BUILDER_CAVE, menu.COMMAND_DESCRIPTOR_BUILD + 6, count=300)
    assert emu.reg_read(UC_X86_REG_ESP) == 0x03001800
    assert emu.reg_read(UC_X86_REG_ESI) == actor
    return tuple(emu.mem_read(emu.reg_read(UC_X86_REG_EDI), 4))


def main():
    exe = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe').read_bytes()
    assert hashlib.sha256(exe).hexdigest() == menu.SUPPORTED_EXE_SHA256
    # Native GF list tests the learned bitmap at GF * 0x44 + 0x1CFDCBC.
    assert exe[0xACBD0:0xACBD7] == bytes.fromhex('85 94 81 BC DC CF 01')
    cases = 0
    for gf in range(16):
        primary = menu.GF_SOURCE_TABLE[gf]
        alternate = menu.GF_ALTERNATE_SOURCE_TABLE[gf]
        for known in (set(), {primary} - {255}, {alternate} - {255},
                      {primary, alternate} - {255}):
            result = run(gf, known)
            assert result == (0x14, 0x16,
                              primary if primary in known else 255,
                              alternate if alternate in known else 255), (gf, known, result)
            cases += 1
    assert run(3, {0x1C}, mask=0) == (0x14, 0x16, 255, 255)
    assert run(3, {0x1C}, mask=9) == (0x14, 0x16, 255, 255)
    print(f'Command learning gate: {cases + 2} x86 builder cases passed')


if __name__ == '__main__':
    main()
