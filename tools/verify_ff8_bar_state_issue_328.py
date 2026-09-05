"""Execute FF8 result-state and page dispatch bytes; inspect overlay integration.

This is not an in-game or visual test. Requires pefile and Unicorn.
"""
from pathlib import Path
import hashlib
import struct
import sys
ROOT = Path(__file__).resolve().parents[1]
try:
    import unicorn
except ImportError:
    sys.path.insert(0, str(ROOT / '_scratch/gf-spellbooks-test-deps'))
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_ECX
import pefile

EXE = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe')
data = EXE.read_bytes()
assert hashlib.sha256(data).hexdigest() == '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
pe = pefile.PE(data=data)
image = pe.get_memory_mapped_image()
STACK = 0x2908000
STOP = 0x2800000
RESULT = 0x1A78C88

def machine():
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    u.mem_map(0x400000, 0x2600000)
    u.mem_write(0x400000, image)
    u.reg_write(UC_X86_REG_ESP, STACK)
    u.mem_write(STACK, struct.pack('<II', STOP, 0))
    return u

# Execute the native renderer prologue and its actual accessor. It must return
# the menu-state allocation in EDI, without calling graphics object accessors.
u = machine()
u.emu_start(0x4A4950, 0x4A4966, count=100)
assert u.reg_read(UC_X86_REG_EDI) == RESULT
assert image[0xA4957:0xA495E] == bytes.fromhex('6A 00 E8 A2 F4 F5 FF')

# Execute native page dispatch for all four valid result phases. Page zero
# alone enters the three-character renderer loop (call 004A5800).
for phase, target in enumerate((0x4A4BBA, 0x4A4C2A, 0x4A4D11, 0x4A4E2D)):
    u = machine()
    u.reg_write(UC_X86_REG_EDI, RESULT)
    u.mem_write(RESULT + 0x38, bytes([phase]))
    u.emu_start(0x4A4BA2, target, count=20)
    assert u.reg_read(UC_X86_REG_EAX) == phase
assert image[0xA4C0D:0xA4C12] == bytes.fromhex('E8 EE 0B 00 00')

# The animation function obtains the same state and forms +0x234 itself.
u = machine()
u.emu_start(0x4A4870, 0x4A488A, count=100)
assert u.reg_read(UC_X86_REG_EDI) == RESULT + 0x234
assert image[0xA443E:0xA4444] == bytes.fromhex('81 C7 34 02 00 00')

# Execute native total initialization and animation increment with distinct
# slot totals. Each update changes its own total, not a saved party EXP value.
for slot, total in enumerate((15390, 12064, 11171)):
    address = RESULT + 0x234 + slot * 4
    u = machine()
    u.reg_write(UC_X86_REG_EDI, address)
    u.reg_write(UC_X86_REG_ECX, total)
    u.emu_start(0x4A4485, 0x4A4487, count=1)
    u.reg_write(UC_X86_REG_EAX, 37)
    u.emu_start(0x4A48AD, 0x4A48B3, count=3)
    assert struct.unpack('<I', u.mem_read(address, 4))[0] == total + 37

# The active viewport is selected at runtime, not fixed to menu viewport 2.
for index in (0, 1, 2, 3):
    u = machine()
    u.mem_write(0xB86D38, struct.pack('<I', index))
    u.emu_start(0x4972D0, 0x4972E6, count=8)
    assert struct.unpack('<I', u.mem_read(0xB86E00, 4))[0] == 0xB86DA0 + 32 * index
assert image[0x972E1:0x972E6] == bytes.fromhex('A3 00 6E B8 00')

source = (ROOT / 'games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp').read_text()
after = source[source.index('void draw_after_battle_xp()'):source.index('void draw_battle_hp()')]
assert 'g_result_state(0)' in after
assert 'result_state[0x38] != 0' in after
assert 'result_state + 0x234 + slot * sizeof(std::uint32_t)' in after
assert 'common_externals.get_game_object' not in after
hp = source[source.index('void draw_battle_hp()'):source.index('} // namespace')]
assert 'getmode_cached()' in hp and 'mode->driver_mode != MODE_BATTLE' in hp
assert 'FF8_MODE_BATTLE' not in hp
upstream = ROOT / '_scratch/ffnx-upstream/src'
assert 'FF8_MODE_BATTLE = 999' in (upstream / 'ff8.h').read_text()
assert 'ff8_set_main_loop(MODE_BATTLE, ff8_externals.battle_main_loop);' in (upstream / 'ff8_data.cpp').read_text()
print('FF8 #328 native accessor, phase dispatch, and animated totals passed; overlay source contract passed. No visual acceptance.')

