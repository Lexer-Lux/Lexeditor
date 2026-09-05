"""Execute Scan metadata and combined Draw eligibility against native FF8 bytes.

Requires Unicorn and pefile. Does not launch the game or change its files.
"""
from pathlib import Path
import hashlib
import struct
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import unicorn
except ImportError:
    sys.path.insert(0, str(ROOT / '_scratch/gf-spellbooks-test-deps'))
    import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
import pefile
from games.ff8 import battle_shortcuts as scan, battle_issue_54 as draw, streamlined_draw as stock
EXE = Path(r'D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe')
data = EXE.read_bytes()
assert hashlib.sha256(data).hexdigest() == '064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570'
pe = pefile.PE(data=data)
STOP = 0x2800000
STACK = 0x2908000

def machine():
    u = Uc(UC_ARCH_X86, UC_MODE_32)
    u.mem_map(0x400000, 0x2600000)
    u.mem_write(0x400000, pe.get_memory_mapped_image())
    u.reg_write(UC_X86_REG_ESP, STACK)
    u.mem_write(STACK, struct.pack('<I', STOP))
    return u

def read32(u, a): return struct.unpack('<I', u.mem_read(a, 4))[0]
def put32(u, a, v): u.mem_write(a, struct.pack('<I', v))
def run(u, a, stop=STOP): u.emu_start(a, stop, count=100000)

assert pe.get_data(draw.DRAW_CAPTURE_HOOK-0x400000,len(draw.DRAW_CAPTURE_ORIGINAL)) == draw.DRAW_CAPTURE_ORIGINAL
assert pe.get_data(0x8FD66,4) == bytes.fromhex('89 4C 24 18')

# Native metadata builder: kernel status byte9 -> list byte2;
# kernel target byte10 -> list byte3. Supply known Scan metadata, then execute
# the actual EXE builder rather than mirroring its assignment in Python.
u = machine()
u.mem_write(0x1CFF082, bytes((50, 1, 0, 0, 0)))
u.mem_write(0x1CF406D + 50*60, bytes((0x80, 0x54, 0x31)))
u.mem_write(0x47EEB0, bytes.fromhex('31 C0 C3')) # unrelated status restriction
put32(u, STACK+4, 0)
run(u, 0x4954B0)
assert bytes(u.mem_read(0x1CFF082, 5)) == scan.SCAN_LIST_BYTES
# Assert the native address/stride expression used by the Draw source builder.
assert pe.get_data(0xADFBA, 13) == bytes.fromhex('8D 04 C9 C1 E0 03 2B C1 05 18 8F D2 01')

# Run actual state8 through target-window setup; record native call arguments.
u = machine()
u.mem_write(scan.SCAN_LIST, scan.SCAN_LIST_BYTES)
u.mem_write(scan.SCAN_LIST_CALLBACK, b'\xB8'+struct.pack('<I',scan.SCAN_LIST)+b'\xC3')
put32(u, scan.MAGIC_LIST_CALLBACK, scan.SCAN_LIST_CALLBACK)
put32(u, 0x1D6D490, 0x2801000)
u.reg_write(UC_X86_REG_EBP, 0)
calls=[]
def stub(uc, address, size, _):
    if address in (0x4AB4F0, 0x4B9B90, 0x4A7160):
        sp=uc.reg_read(UC_X86_REG_ESP)
        if address == 0x4AB4F0:
            calls.append([read32(uc,sp+4+i*4)&255 for i in range(6)])
        uc.reg_write(UC_X86_REG_EIP,read32(uc,sp))
        uc.reg_write(UC_X86_REG_ESP,sp+4)
u.hook_add(UC_HOOK_CODE,stub)
run(u,0x4FEBC1,0x4FEF37)
assert calls[0][1:4] == [0x54,0x80,0], calls
assert bytes(u.mem_read(scan.MAGIC_MENU_STATE,1)) == b'\x09'
# Reopening restores the private entry after native stock debit cleared it.
u=machine()
u.mem_write(scan.SCAN_INIT_CAVE,scan._scan_init_payload())
u.mem_write(scan.SCAN_LIST,scan.SCAN_LIST_BYTES)
u.mem_write(scan.MAGIC_CONTROLLER,b'\xC3')
u.mem_write(scan.SCAN_ACTIVE,b'\x01')
run(u,scan.SCAN_INIT_CAVE)
assert bytes(u.mem_read(scan.SCAN_LIST,5)) == scan.SCAN_LIST_BYTES
u.mem_write(scan.SCAN_LIST,b'\0'*5)
u.reg_write(UC_X86_REG_ESP,STACK)
run(u,scan.SCAN_INIT_CAVE)
assert bytes(u.mem_read(scan.SCAN_LIST,5)) == scan.SCAN_LIST_BYTES

# Cancellation and completion enter native close states; normal Magic keeps
# its original path. This does not claim the later effect has retained ATB.
for address,payload,continuation in (
    (scan.SCAN_CANCEL_CAVE,scan._scan_cancel_payload(),scan.MAGIC_TARGET_CANCEL_CONTINUE),
    (scan.SCAN_FINISH_CAVE,scan._scan_finish_payload(),scan.MAGIC_ACTION_FINISH_CONTINUE),
):
    for active in (0,1):
        u=machine()
        u.mem_write(address,payload)
        u.mem_write(scan.SCAN_ACTIVE,bytes((active,)))
        u.mem_write(0x4B9B90,b'\xC3')
        run(u,address,scan.MAGIC_STATE_LOOP if active else continuation)
        if active:
            assert bytes(u.mem_read(scan.SCAN_ACTIVE,1)) == b'\x00'
            assert bytes(u.mem_read(STACK+0x10,1)) == b'\x06'
            assert bytes(u.mem_read(scan.MAGIC_MENU_STATE,1)) == b'\x06'

# Execute result-mask hook followed by the combined stock + used-enemy filter.
# Every enemy gets distinct data at the EXE-derived 71-byte stride.
for target in range(3,7):
    u=machine()
    put32(u,draw.DRAW_STATE,0)
    u.mem_write(draw.DRAW_RESULT_CAVE,draw._draw_result_payload())
    u.reg_write(UC_X86_REG_EAX,5)
    # Native 0048FD66 overwrites the second Draw argument with enemy level.
    # Capture before the call; the result hook must not read that argument.
    u.mem_write(draw.DRAW_CAPTURE_CAVE,draw._draw_capture_payload())
    u.reg_write(UC_X86_REG_EDX,target)
    run(u,draw.DRAW_CAPTURE_CAVE,draw.DRAW_CAPTURE_HOOK+len(draw.DRAW_CAPTURE_ORIGINAL))
    u.reg_write(UC_X86_REG_ESP,STACK)
    put32(u,STACK+4,40)
    run(u,draw.DRAW_RESULT_CAVE,draw.DRAW_RESULT_HOOK+len(draw.DRAW_RESULT_ORIGINAL))
    assert read32(u,draw.DRAW_STATE) == 1<<target
    u.mem_write(stock.STOCK_FILTER_CAVE,stock.build_stock_filter_code_cave())
    u.mem_write(stock.MAGIC_STOCK_LIMIT_VALUE,b'\x64')
    for actor in range(3,7):
        u.mem_write(stock.ENEMY_DRAW_BASE+(actor-3)*71,bytes((actor,0,0,0)))
    # No actor stock: each enemy must stay eligible on its own.
    for actor in range(3,7):
        u.reg_write(UC_X86_REG_ESP,STACK)
        put32(u,STACK,STOP)
        u.reg_write(UC_X86_REG_EAX,1<<actor)
        run(u,stock.STOCK_FILTER_CAVE)
        assert u.reg_read(UC_X86_REG_EAX)==1<<actor,(target,actor)
    # Full stock filters only that enemy, not its distinct neighbor.
    u.mem_write(stock.BATTLE_ACTOR_MAGIC_BASE,bytes((target,100,0,0,0)))
    u.reg_write(UC_X86_REG_ESP,STACK)
    u.reg_write(UC_X86_REG_EAX,0x78)
    run(u,stock.STOCK_FILTER_CAVE)
    assert u.reg_read(UC_X86_REG_EAX)==0x78 & ~(1<<target)
    # Restore below-cap stock: the next assertion must be caused by Draw Once,
    # independently of full-stock filtering.
    u.mem_write(stock.BATTLE_ACTOR_MAGIC_BASE,bytes((target,0,0,0,0)))
    # Actual shared target hook must preserve all unused, non-full enemies.
    u.mem_write(draw.DRAW_TARGET_MASK_CAVE,draw._draw_target_mask_payload(streamlined_draw=True))
    u.reg_write(UC_X86_REG_ESP,STACK)
    u.reg_write(UC_X86_REG_EAX,0x78)
    put32(u,STACK+0x20,0x2802000)
    u.mem_write(0x2802000,b'\x06')
    run(u,draw.DRAW_TARGET_MASK_CAVE,draw.DRAW_TARGET_MASK_RETURN)
    assert u.reg_read(UC_X86_REG_EDI)==0x78 & ~(1<<target)
print('PASS: native Scan metadata/target setup/reopen and all four Draw enemy slots')
