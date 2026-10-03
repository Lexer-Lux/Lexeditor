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
    engine.mem_map(0x8D0000, 0x10000)
    engine.mem_write(0x8D0000, image[0x8D0000-base:0x8E0000-base])
    engine.mem_map(0x1DCD000, 0x3000)
    engine.mem_map(0x1CFE000, 0x2000)
    engine.mem_map(0x30000000, 0x10000)
    counter = [0]
    forced_random = []

    def random_stub(uc, address, size, _):
        if address != 0x534AA0:
            return
        # A deterministic sequence covers level/card combinations without
        # replacing the hand builder's division, filtering or duplicate logic.
        counter[0] = (counter[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        uc.reg_write(UC_X86_REG_EAX, forced_random.pop(0) if forced_random else counter[0] >> 16)
        stack = uc.reg_read(UC_X86_REG_ESP)
        target, = struct.unpack("<I", uc.mem_read(stack, 4))
        uc.reg_write(UC_X86_REG_ESP, stack + 4)
        uc.reg_write(UC_X86_REG_EIP, target)

    engine.hook_add(UC_HOOK_CODE, random_stub)
    def hand(mask, chance=0, owner=0):
        engine.mem_write(0x1DCD7B0, struct.pack("<I", mask | chance << 8))
        engine.mem_write(0x1DCD76C, bytes(10))
        stack = 0x3000FF00
        engine.mem_write(stack, struct.pack("<III", 0x30000000, 1, owner))
        engine.reg_write(UC_X86_REG_ESP, stack)
        engine.emu_start(0x537640, 0x30000000, count=100000)
        assert engine.reg_read(UC_X86_REG_EIP) == 0x30000000
        return list(engine.mem_read(0x1DCD771, 5))

    for mask in range(128):
        cards = hand(mask)
        effective = mask or 1
        assert len(set(cards)) == 5, (mask, cards)
        assert all(card != 47 and card < 77 and effective & (1 << (card // 11)) for card in cards), (mask, cards)
    print("PASS native hand generation: all 128 level masks, zero fallback, five distinct cards, PuPu excluded")

    # These are controlled match-time ownership bytes, not a claimed static
    # deck table. Execute the game's actual comparison for every rare card
    # and every byte-valued owner; keep the source and ownership state intact.
    for owner in range(256):
        for rare in range(33):
            ownership = bytearray([owner ^ 1] * 33)
            ownership[rare] = owner
            engine.mem_write(0x1CFEF85, bytes(ownership))
            cards = hand(1, 100, owner)
            if owner:
                assert cards[0] == rare + 77, (owner, rare, cards)
                assert len(set(cards)) == 5 and all(card < 11 for card in cards[1:]), cards
            else:
                assert all(card < 11 for card in cards), cards
            assert bytes(engine.mem_read(0x1CFEF85, 33)) == bytes(ownership)
        assert all(card < 11 for card in hand(1, 0, owner))
        assert all(card < 11 for card in hand(1, 100, 0))
        assert all(card < 11 for card in hand(1, 100, owner ^ 2))
    print("PASS native rare-card selection: all 33 cards and 256 ownership values; zero chance, deck zero and mismatched ownership excluded")

    engine.mem_write(0x1CFEF85, bytes([7] * 33))
    forced_random[:] = [99, 49, 50, 0, 0, 0]
    assert hand(1, 100, 7) == [77, 78, 80, 81, 82]
    assert not forced_random
    assert bytes(engine.mem_read(0x1CFEF85, 33)) == bytes([7] * 33)
    print("PASS native rare-card order and probability: ascending IDs, strict percentage boundary, half the original chance after the first success, at most five cards")

    # init.out loads into the GF records, then calls this separate card
    # initializer. Execute it rather than treating nearby data as a table.
    assert image[0xC78C90-base:0xC78C99-base] == b"init.out\0"
    assert image[0x56DA75-base:0x56DA7A-base] == bytes.fromhex("E8 A6 24 37 00")
    engine.mem_write(0x1CFEF37, b"\xA5" * 130)
    stack = 0x3000FF00
    engine.mem_write(stack, struct.pack("<I", 0x30000000))
    engine.reg_write(UC_X86_REG_ESP, stack)
    engine.emu_start(0x8DFF20, 0x30000000, count=10000)
    assert engine.reg_read(UC_X86_REG_EIP) == 0x30000000
    assert engine.reg_read(UC_X86_REG_ESP) == stack + 4
    assert bytes(engine.mem_read(0x1CFEF38, 77)) == bytes(77)
    assert bytes(engine.mem_read(0x1CFEF85, 33)) == bytes(range(200, 233))
    assert bytes(engine.mem_read(0x1CFEF37, 1)) == b"\xA5"
    assert bytes(engine.mem_read(0x1CFEFB8, 1)) == b"\xA5"
    print("PASS native card initialization after init.out: rare cards 77-109 start with owners 200-232; adjacent state preserved")


if __name__ == "__main__":
    run()
