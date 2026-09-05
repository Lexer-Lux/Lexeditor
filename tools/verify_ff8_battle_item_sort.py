"""Execute sorted native battle cache construction and descriptor flags."""
from pathlib import Path
import hashlib
import random
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.ff8 import inventory_auto_sort as source
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP


def main():
    exe = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe').read_bytes()
    assert hashlib.sha256(exe).hexdigest() == source.SUPPORTED_EXE_SHA256
    assert exe[0x8C6E0:0x8C6E5] == source.BATTLE_CACHE_ORIGINAL
    rng = random.Random(308)
    for case in range(40):
        m = Uc(UC_ARCH_X86, UC_MODE_32)
        m.mem_map(0x48C000, 0x1000)
        m.mem_write(0x48C670, exe[0x8C670:0x8C731])
        m.mem_map(0x27A0000, 0x1000)
        m.mem_write(source.BATTLE_SORT_CAVE, source.build_battle_sort_cave())
        m.mem_write(source.BATTLE_CACHE_HOOK, source.relative_branch(b'\xE9', source.BATTLE_CACHE_HOOK, source.BATTLE_SORT_CAVE))
        m.mem_map(0x1CF0000, 0x50000)
        m.mem_map(0x3000000, 0x1000)
        ids = list(range(1,199)); rng.shuffle(ids)
        pairs = [(i, rng.choice((0,1,9,99))) for i in ids]
        inventory = bytes(v for pair in pairs for v in pair)
        m.mem_write(source.SAVED_ITEMS, inventory)
        permutation = list(range(32)); rng.shuffle(permutation)
        m.mem_write(source.BATTLE_ORDER, bytes(permutation))
        for item in range(33):
            m.mem_write(0x1CF7780 + item*24, bytes((item+1, item+2, (0x80 if item%2 else 0) | (0x20 if item%3 else 0))))
        expected = sorted(i for i,q in pairs if 1<=i<=32 and q)
        previous = None
        for repeat in range(2):
            m.reg_write(UC_X86_REG_ESP, 0x3000800)
            m.mem_write(0x3000800, struct.pack('<I',0x48CF00))
            m.emu_start(source.BATTLE_CACHE_HOOK, 0x48CF00, count=10000)
            assert m.reg_read(UC_X86_REG_ESP) == 0x3000804
            assert bytes(m.mem_read(source.SAVED_ITEMS,396)) == inventory
            order = bytes(m.mem_read(source.BATTLE_ORDER,32))
            assert sorted(order) == list(range(32))
            cache = bytes(m.mem_read(0x1D28E78,160))
            rows = [cache[n:n+5] for n in range(0,160,5)]
            assert [row[0] for row in rows if row[1]] == expected
            for row in rows:
                i,q,a,b,flags = row
                assert a == i+1 and b == i+2
                assert flags == ((1 if i%2 else 0) | (0 if i%3 else 2))
                if i: assert q == dict(pairs)[i]
            if previous is not None: assert previous == (order,cache)
            previous = order,cache
    assert source.build_hext(False) == ''
    print('Battle item sort: 80 full native cache builds passed; quantities and descriptor flags preserved')


if __name__ == '__main__': main()
