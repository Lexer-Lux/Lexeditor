"""Exercise the native weapon flag producer before the Flying EVA consumer."""
from pathlib import Path
import hashlib
import struct
import sys
import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import unicorn
except ImportError:
    sys.path.insert(0, str(ROOT/'_scratch/gf-spellbooks-test-deps'))
    import unicorn
from unicorn.x86_const import *
from plugins.ff8 import flying_eva

data = Path(r'D:/SteamLibrary/steamapps/common/FINAL FANTASY VIII/FF8_EN.exe').read_bytes()
assert hashlib.sha256(data).hexdigest() == '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
image = pefile.PE(data=data).get_memory_mapped_image()
for melee in (False, True):
    for character_flag in (False, True):
        for hit in (75, 255):
            u = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
            u.mem_map(0x400000, 0x2600000)
            u.mem_write(0x400000, image)
            u.reg_write(UC_X86_REG_ESI, 0)
            u.reg_write(UC_X86_REG_EBX, 0x1cff000)
            u.mem_write(0x1cff1ba, b'\0')
            u.mem_write(0x1d27bcb, b'\0')
            u.mem_write(0x1cf740b, bytes([melee]))
            u.mem_write(0x1cf75ef, bytes([character_flag]))
            u.emu_start(0x48b64a, 0x48b69c, count=100)
            flags = struct.unpack('<I', u.mem_read(0x1d27b8c, 4))[0]
            assert bool(flags & 0x1000) == melee
            assert bool(flags & 0x100) == character_flag
            u.mem_write(0x1d27b10+0x270, struct.pack('<I', 0x2700000))
            u.mem_write(0x2700000, struct.pack('<I', 0x2710000))
            u.mem_write(0x27100f7, b'\2')
            u.mem_write(0x1d27b18, b'\0'*4)
            u.mem_write(0x1d2a238, bytes([hit]))
            u.mem_write(0x1d27bd2+0x270, b'\0')
            u.mem_write(flying_eva.CAVE, flying_eva.build_payload(100))
            u.reg_write(UC_X86_REG_EBP, 0x270)
            u.reg_write(UC_X86_REG_EAX, 0)
            u.reg_write(UC_X86_REG_ECX, 0)
            u.emu_start(flying_eva.CAVE, 0x492f29, count=100)
            threshold = u.reg_read(UC_X86_REG_EDI)
            assert threshold == (0 if melee else hit*255//100), (melee, character_flag, hit, threshold)
            # Native zero-chance guard must reject every possible RNG result.
            if melee:
                for roll in range(256):
                    u.reg_write(UC_X86_REG_EAX, roll)
                    u.emu_start(0x492f2e, 0x4930cb, count=5)
                    assert u.reg_read(UC_X86_REG_EIP) == 0x4930cb
print('Native weapon flags: melee misses at +100 EVA for HIT 75 and 255, all RNG rolls; ranged and character-flag isolation pass.')
