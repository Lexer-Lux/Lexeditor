"""Read-only native comparison of authored per-group encounter Hext behavior."""
from pathlib import Path
from collections import Counter
import struct
import sys

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_ESI,
    UC_X86_REG_EDI, UC_X86_REG_EIP,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff8 import encounter_chances as chances, paths


def rejects(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('Malformed encounter probability payload was accepted')


def run():
    for values in (None, {}, '256', [256], [32]*7, [32]*9,
                   [True]+[32]*7, [32.0]*8, ['32']*8, [None]*8,
                   [-1, 257, 0, 0, 0, 0, 0, 0], [257, 0, 0, 0, 0, 0, 0, -1],
                   [0]*8, [32]*7+[31], [32]*7+[33]):
        rejects(lambda: chances.encode_weights(values))
    rejects(lambda: chances.selector_patch(b'unsupported executable', 16))
    exe_path = paths.GAME_ROOT / 'FF8_EN.exe'
    if not exe_path.exists():
        print('SKIP native encounter patch comparison: supported installed executable required; schema checks passed')
        return
    exe = exe_path.read_bytes()
    patch = chances.selector_patch(exe, 0x100)
    hext = chances.build_hext(exe, 0x100)
    address, payload = hext.splitlines()[1].split(' = ')
    assert int(address, 16) == chances.SELECTOR_START
    assert bytes.fromhex(payload) == patch
    assert len(patch) == chances.SELECTOR_END - chances.SELECTOR_START == 178
    for offset in (None, True, 16.0, '16', -2, 0, 14, 17, 0x80000000):
        rejects(lambda: chances.selector_patch(exe, offset))
    for offset in (16, 128, 0x10000, 0x7FFFFFFE):
        assert len(chances.selector_patch(exe, offset)) == 178

    pe = pefile.PE(data=exe, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    original = image[chances.SELECTOR_START-base:chances.SELECTOR_END-base]

    def make_engine(code):
        engine = Uc(UC_ARCH_X86, UC_MODE_32)
        for address, size in ((0x540000, 0x10000), (0xC75000, 0x1000),
                              (0x2030000, 0x20000), (0x30000000, 0x10000)):
            engine.mem_map(address, size)
        engine.mem_write(0x540000, image[0x540000-base:0x550000-base])
        engine.mem_write(0xC75000, image[0xC75000-base:0xC76000-base])
        engine.mem_write(chances.SELECTOR_START, code)
        engine.mem_write(0x2036BE8, struct.pack('<I', 0x30000100))
        engine.mem_write(0x2040080, struct.pack('<I', 0x30001000))
        for group in range(4):
            engine.mem_write(0x30000100+group*16, struct.pack('<8H', *range(100+group*8, 108+group*8)))
        engine.mem_write(0x30001000, struct.pack('<8H', *range(200, 208)))
        for record in range(5):
            engine.mem_write(0x30000200+record*16, chances.encode_weights(chances.DEFAULT_OUTCOMES))
        engine.mem_write(0x3000FE08, struct.pack('<I', 0x30000300))
        return engine

    vanilla, modified = make_engine(original), make_engine(patch)

    def select(engine, counter, shift, previous=999, group=3, alternative=False):
        engine.mem_write(0x20400A0, struct.pack('<H', previous))
        engine.mem_write(0x2040A61, bytes([shift, counter]))
        engine.mem_write(0x2040A5E, b'\xff')
        engine.mem_write(0x3000FDFD, bytes([4 if alternative else 0]))
        engine.reg_write(UC_X86_REG_EBP, 0x3000FE00)
        engine.reg_write(UC_X86_REG_ESP, 0x3000FD00)
        engine.reg_write(UC_X86_REG_ESI, 80 if alternative else group)
        engine.reg_write(UC_X86_REG_EDI, 80 if alternative else group)
        engine.emu_start(chances.SELECTOR_START, chances.SELECTOR_END, count=500)
        assert engine.reg_read(UC_X86_REG_EIP) == chances.SELECTOR_END
        assert engine.reg_read(UC_X86_REG_EBP) == 0x3000FE00
        assert engine.reg_read(UC_X86_REG_ESP) == 0x3000FD00
        assert engine.reg_read(UC_X86_REG_ESI) == (80 if alternative else group)
        assert engine.reg_read(UC_X86_REG_EDI) == (80 if alternative else group)
        scene, = struct.unpack('<H', engine.mem_read(0x30000300, 2))
        assert bytes(engine.mem_read(0x2040A5E, 1)) == b'\0'
        assert bytes(engine.mem_read(0x3000FDF4, 4)) == struct.pack('<I', 1)
        return scene, bytes(engine.mem_read(0x2040A61, 2))

    # Two independent emulators keep the original and authored code fixed.
    # Neither random tables nor native instructions are mocked or stubbed.
    for counter in range(256):
        for shift in range(256):
            assert select(vanilla, counter, shift) == select(modified, counter, shift)
    for alternative in (False, True):
        for counter in range(256):
            first = select(vanilla, counter, 0, alternative=alternative)[0]
            assert select(vanilla, counter, 0, first, alternative=alternative) == select(
                modified, counter, 0, first, alternative=alternative)
    for weights in ([256, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 256],
                    [0, 1, 2, 3, 4, 5, 6, 235], [32]*8):
        modified.mem_write(0x30000240, chances.encode_weights(weights))
        counts = Counter(select(modified, 0, shift)[0]-124 for shift in range(256))
        assert [counts[index] for index in range(8)] == weights, counts
        for shift in range(256):
            assert select(vanilla, 0, shift, group=0) == select(modified, 0, shift, group=0)
            assert select(vanilla, 0, shift, alternative=True) == select(modified, 0, shift, alternative=True)
    # A 100% previous formation still gets exactly two draws, not an infinite retry.
    modified.mem_write(0x30000240, chances.encode_weights([256, 0, 0, 0, 0, 0, 0, 0]))
    for counter in (0, 254, 255):
        selected, state = select(modified, counter, 0, previous=124)
        assert selected == 124
        assert state == bytes([13 if counter >= 254 else 0, (counter+2) % 256])
    print('PASS encounter chance Hext builder: guarded 178-byte payload; 65,536 vanilla-state comparisons; '
          'native retry parity; 0-256 outcomes; group isolation; alternative fallback; 100% retry bounds')


if __name__ == '__main__':
    run()
