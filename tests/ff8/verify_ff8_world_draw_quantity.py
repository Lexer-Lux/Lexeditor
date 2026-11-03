"""Execute vanilla world draw quantity and stock-space clipping, read-only."""
from hashlib import sha256
from pathlib import Path
import struct

import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ESP, UC_X86_REG_EIP

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def run():
    if not EXE.exists():
        print("SKIP: supported installed FF8 executable required for native quantity proof")
        return
    data = EXE.read_bytes()
    assert sha256(data).hexdigest() == EXPECTED
    pe = pefile.PE(data=data, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    engine = Uc(UC_ARCH_X86, UC_MODE_32)
    engine.mem_map(0x540000, 0x10000)
    engine.mem_write(0x540000, image[0x540000-base:0x550000-base])
    engine.mem_map(0x2040000, 0x10000)
    engine.mem_map(0x30000000, 0x10000)
    random_value = [0]

    def rng(uc, address, size, _):
        if address == 0x541F10:
            uc.reg_write(UC_X86_REG_EAX, random_value[0])
            stack = uc.reg_read(UC_X86_REG_ESP)
            target, = struct.unpack("<I", uc.mem_read(stack, 4))
            uc.reg_write(UC_X86_REG_ESP, stack + 4)
            uc.reg_write(UC_X86_REG_EIP, target)

    engine.hook_add(UC_HOOK_CODE, rng)
    ranges = {False: set(), True: set()}
    for packed in range(256):
        high = bool(packed & 128)
        for random in range(256):
            random_value[0] = random
            engine.reg_write(UC_X86_REG_EAX, packed)
            engine.reg_write(UC_X86_REG_ESP, 0x3000FF00)
            engine.emu_start(0x54EAED, 0x54EB33, count=100)
            assert engine.reg_read(UC_X86_REG_EIP) == 0x54EB33
            assert engine.reg_read(UC_X86_REG_ESP) == 0x3000FF00
            quantity = engine.mem_read(0x2043DC0, 1)[0]
            assert quantity == ((random + 128) * (6 if high else 2)) // 512 + 1
            ranges[high].add(quantity)
    assert ranges == {False: {1, 2}, True: {2, 3, 4, 5}}, ranges

    # The following production block caps the selected draw to the party
    # member's remaining stock space. It does not increase the random amount.
    engine.mem_write(0x2043140, struct.pack("<I", 0))
    for quantity in range(1, 6):
        for room in range(1, 101):
            engine.mem_write(0x2043DC0, struct.pack("<I", quantity))
            engine.mem_write(0x2043FF4, struct.pack("<I", room))
            engine.reg_write(UC_X86_REG_ESP, 0x3000FF00)
            engine.emu_start(0x54F07D, 0x54F0B8, count=100)
            assert engine.mem_read(0x2043DC0, 1)[0] == min(quantity, room)
    print("PASS native world draw quantity: all 256 point bytes × 256 RNG values; normal 1-2, high yield 2-5; all 1-100 stock-space limits")


if __name__ == "__main__":
    run()
