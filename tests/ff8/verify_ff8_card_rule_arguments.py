"""Execute native CARDGAME initialization without launching or changing FF8."""
from hashlib import sha256
from pathlib import Path
import struct
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def run():
    if not EXE.exists():
        print("SKIP: installed supported FF8_EN.exe required for rule argument proof")
        return
    data = EXE.read_bytes()
    assert sha256(data).hexdigest() == EXPECTED
    pe = pefile.PE(data=data, fast_load=True)
    image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
    engine = Uc(UC_ARCH_X86, UC_MODE_32)
    engine.mem_map(0x530000, 0x10000)
    engine.mem_write(0x530000, image[0x530000-base:0x540000-base])
    engine.mem_map(0x1DCD000, 0x3000)
    engine.mem_map(0x30000000, 0x10000)
    for mask in range(256):
        for trade in range(5):
            engine.mem_write(0x1DCD7A8, struct.pack('<IB', mask, trade))
            engine.mem_write(0x3000FF00, struct.pack('<I', 0x30000000))
            engine.reg_write(UC_X86_REG_ESP, 0x3000FF00)
            engine.emu_start(0x534350, 0x30000000, count=100)
            assert engine.reg_read(UC_X86_REG_EIP) == 0x30000000
            assert bytes(engine.mem_read(0x1DCD794, 4)) == struct.pack('<I', mask)
            assert bytes(engine.mem_read(0x1DCD766, 1)) == bytes([trade])
    print('PASS native rule initialization: all 256 masks and five trade values retained independently')


if __name__ == '__main__':
    run()
