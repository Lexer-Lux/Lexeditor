"""Execute the installed vanilla world formation selector without running FF8."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import struct

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (
    UC_X86_REG_EBP, UC_X86_REG_EDI, UC_X86_REG_EIP,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def run():
    if not EXE.exists():
        print("SKIP: supported installed FF8 executable required for native encounter proof")
        return
    data = EXE.read_bytes()
    assert sha256(data).hexdigest() == EXPECTED
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    weights = list(image[0xC75F10-base:0xC75F18-base])
    random_table = image[0xC75D20-base:0xC75E20-base]
    assert weights == [37, 37, 37, 37, 36, 36, 24, 12]
    assert len(set(random_table)) == 256

    engine = Uc(UC_ARCH_X86, UC_MODE_32)
    for address, size in [(0x540000, 0x10000), (0xC75000, 0x1000),
                          (0x2030000, 0x20000), (0x30000000, 0x10000)]:
        engine.mem_map(address, size)
    # Execute original instructions and original random/weight tables. Only
    # surrounding world state and scene IDs are authored fixtures.
    engine.mem_write(0x540000, image[0x540000-base:0x550000-base])
    engine.mem_write(0xC75000, image[0xC75000-base:0xC76000-base])
    for pointer in (0x2036BE8, 0x2040080):
        engine.mem_write(pointer, struct.pack("<I", 0x30000100))
    engine.mem_write(0x3000FE08, struct.pack("<I", 0x30000200))

    def select(counter, shift, formations, previous=999, alternative=False):
        engine.mem_write(0x30000100, struct.pack("<8H", *formations))
        engine.mem_write(0x20400A0, struct.pack("<H", previous))
        engine.mem_write(0x2040A61, bytes([shift, counter]))
        engine.mem_write(0x3000FDFD, bytes([4 if alternative else 0]))
        engine.reg_write(UC_X86_REG_EBP, 0x3000FE00)
        engine.reg_write(UC_X86_REG_ESP, 0x3000FD00)
        engine.reg_write(UC_X86_REG_ESI, 80 if alternative else 0)
        engine.reg_write(UC_X86_REG_EDI, 80 if alternative else 0)
        engine.emu_start(0x541E2D, 0x541EDF, count=200)
        assert engine.reg_read(UC_X86_REG_EIP) == 0x541EDF
        selected, = struct.unpack("<H", engine.mem_read(0x30000200, 2))
        final_shift, final_counter = engine.mem_read(0x2040A61, 2)
        return selected, final_counter, final_shift

    # Full counter/shift state space avoids mistaking one 256-state slice for
    # a uniform random byte. The wrap advances the shift by 13.
    formations = tuple(range(100, 108))
    counts = Counter()
    for counter in range(256):
        for shift in range(256):
            selected, final_counter, final_shift = select(counter, shift, formations)
            assert final_counter == (counter + 1) % 256
            assert final_shift == (shift + (13 if counter == 255 else 0)) % 256
            counts[selected-100] += 1
    initial_counts = [38, 37, 37, 37, 36, 36, 24, 11]
    assert [counts[index] for index in range(8)] == [count*256 for count in initial_counts]

    for counter in range(256):
        first, next_counter, next_shift = select(counter, 0, formations)
        second, after_counter, after_shift = select(next_counter, next_shift, formations)
        for previous in formations:
            actual = select(counter, 0, formations, previous=previous)
            expected = ((second, after_counter, after_shift) if previous == first
                        else (first, next_counter, next_shift))
            assert actual == expected, (counter, previous, actual, expected)

    # A repeated scene gets exactly one retry, even when every slot repeats.
    # Both normal and alternative encounter-group pointers use the selector.
    for alternative in (False, True):
        for counter in range(256):
            for shift in (0, 255):
                selected, final_counter, final_shift = select(
                    counter, shift, (100,)*8, previous=100, alternative=alternative)
                assert selected == 100
                assert final_counter == (counter + 2) % 256
                assert final_shift == (shift + (13 if counter >= 254 else 0)) % 256
                # Eight different scenes remain valid, including rare slots.
                selected, _, _ = select(counter, shift, formations, alternative=alternative)
                assert selected in formations
    print("PASS native world encounter selector: 65,536 initial RNG states; "
          "slot counts 38,37,37,37,36,36,24,11 per 256; "
          "one retry of the previous scene; both group sources; eight distinct scenes")


if __name__ == "__main__":
    run()
