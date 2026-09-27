"""Execute the supported game's hand builder to prove CARDGAME level-mask bits.

Reads the private installed EXE; replaces only RNG with deterministic values.
No game process, installation, or save is modified.
"""
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
        print("SKIP: installed supported FF8_EN.exe required for native hand-builder proof")
        return
    data = EXE.read_bytes()
    assert sha256(data).hexdigest() == EXPECTED
    pe = pefile.PE(data=data, fast_load=True)
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    # The opcode pops argument 7 into the level mask, then argument 4 into
    # the adjacent rare-card chance byte. This establishes script provenance.
    assert image[0x5225D7-base:0x5225DD-base] == bytes.fromhex("88 0D B0 D7 DC 01")
    assert image[0x522613-base:0x522619-base] == bytes.fromhex("88 0D B1 D7 DC 01")
    engine = Uc(UC_ARCH_X86, UC_MODE_32)
    engine.mem_map(0x530000, 0x10000)
    engine.mem_write(0x530000, image[0x530000-base:0x540000-base])
    engine.mem_map(0x1DCD000, 0x3000)
    engine.mem_map(0x30000000, 0x10000)
    counter = [0]

    def random_stub(uc, address, size, _):
        if address != 0x534AA0:
            return
        # A deterministic sequence covers level/card combinations without
        # replacing the hand builder's division, filtering or duplicate logic.
        counter[0] = (counter[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        uc.reg_write(UC_X86_REG_EAX, counter[0] >> 16)
        stack = uc.reg_read(UC_X86_REG_ESP)
        target, = struct.unpack("<I", uc.mem_read(stack, 4))
        uc.reg_write(UC_X86_REG_ESP, stack + 4)
        uc.reg_write(UC_X86_REG_EIP, target)

    engine.hook_add(UC_HOOK_CODE, random_stub)
    for mask in range(128):
        engine.mem_write(0x1DCD7B0, struct.pack("<I", mask))
        engine.mem_write(0x1DCD76C, bytes(10))
        stack = 0x3000FF00
        engine.mem_write(stack, struct.pack("<III", 0x30000000, 1, 0))
        engine.reg_write(UC_X86_REG_ESP, stack)
        engine.emu_start(0x537640, 0x30000000, count=100000)
        assert engine.reg_read(UC_X86_REG_EIP) == 0x30000000
        hand = list(engine.mem_read(0x1DCD771, 5))
        effective = mask or 1
        assert len(set(hand)) == 5, (mask, hand)
        assert all(card != 47 and card < 77 and effective & (1 << (card // 11)) for card in hand), (mask, hand)
    print("PASS native hand generation: all 128 level masks, zero fallback, five distinct cards, PuPu excluded")


if __name__ == "__main__":
    run()
