"""Static and mutation contract for FF8 Fast Start."""

from __future__ import annotations

# Dev caches and outputs live in the temp folder, never in the checkout.
DEV_CACHE = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / "lexeditor-dev"
from hashlib import sha256
from pathlib import Path
import struct
import sys

import pefile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import fast_start  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == EXPECTED_EXE
pe = pefile.PE(str(EXE), fast_load=True)

# Prove the exact credits-completion call and the unchanged native transition
# that follows it. Fast Start must not replace the initial mode callbacks.
assert image_bytes(
    pe, fast_start.CREDITS_COMPLETION_CALL,
    len(fast_start.CREDITS_COMPLETION_ORIGINAL),
) == fast_start.CREDITS_COMPLETION_ORIGINAL
native_transition = bytes.fromhex(
    "85 C0 74 2E 8D 44 24 08 56 50 C7 44 24 18 40 04 47 00 "
    "C7 44 24 1C 70 D9 56 00 C7 44 24 20 20 05 47 00"
)
assert image_bytes(pe, 0x0052DAE4, len(native_transition)) == native_transition
# The intro loop plays the logo movie while 0209A798 is set, then schedules
# the credits with its own callbacks, which stay untouched.
intro_loop = bytes.fromhex("8B 0D 98 A7 09 02 3B C8 75 33")
assert image_bytes(pe, 0x004703F9, len(intro_loop)) == intro_loop
assert image_bytes(pe, fast_start.INTRO_MOVIE_BRANCH, 2) == fast_start.INTRO_MOVIE_BRANCH_ORIGINAL
intro_schedule = bytes.fromhex("C7 44 24 24 70 D9 52 00 C7 44 24 28 90 DB 52 00 C7 44 24 2C 20 DA 52 00")
assert image_bytes(pe, 0x00470409, len(intro_schedule)) == intro_schedule

# Derive stop_movie from the real movie-update call, the same symbol chain
# used by FFNx src/ff8_data.cpp (c056db2783f376a340fcefa6a48cc33618998876).
# This checks the installed EXE, without depending on a discarded source clone.
def call_target(address, instruction):
    assert instruction[0] == 0xE8
    return address + 5 + struct.unpack("<i", instruction[1:])[0]

assert image_bytes(pe, fast_start.INTRO_MOVIE_UPDATE_CALL, 5) == fast_start.INTRO_MOVIE_UPDATE_ORIGINAL
update = call_target(fast_start.INTRO_MOVIE_UPDATE_CALL, fast_start.INTRO_MOVIE_UPDATE_ORIGINAL)
stop = call_target(update + 0x3E2, image_bytes(pe, update + 0x3E2, 5))
assert call_target(fast_start.INTRO_MOVIE_UPDATE_CALL, fast_start.INTRO_MOVIE_STOP) == stop
assert image_bytes(pe, stop + 0x47, 10) == bytes.fromhex("C7 05 70 D9 B6 00 01 00 00 00")

assert fast_start.build_hext(False) == ""
patch = fast_start.build_hext(True)
assert f"{fast_start.CREDITS_COMPLETION_CALL:X} = B8 01 00 00 00" in patch
assert f"{fast_start.INTRO_MOVIE_BRANCH:X} = 75 33" in patch
assert f"{fast_start.INTRO_MOVIE_UPDATE_CALL:X} = E8 85 A1 0E 00" in patch
for retired in ("47040D =", "470415 =", "47041D ="):
    assert retired not in patch
for invalid in (0, 1, "true", None):
    try:
        fast_start.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Fast Start accepted {invalid!r}")

# Execute the actual publisher-intro branch and native movie-stop code. Stub
# only OS/rendering cleanup calls; the movie flag, handle and timer writes are
# real executable instructions. The old branch bypass must fail this contract.
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP

def run_intro(fragment):
    emu = Uc(UC_ARCH_X86, UC_MODE_32)
    mapped = pe.get_memory_mapped_image()
    emu.mem_map(0x400000, (len(mapped) + 0xFFF) & ~0xFFF)
    emu.mem_write(0x400000, mapped)
    emu.mem_map(0x3000000, 0x10000)
    emu.mem_map(0x3100000, 0x10000)
    for line in fragment.splitlines():
        if " = " in line:
            address, value = line.split(" = ")
            emu.mem_write(int(address, 16), bytes.fromhex(value))
    def put(address, value):
        emu.mem_write(address, struct.pack("<I", value))
    def get(address):
        return struct.unpack("<I", emu.mem_read(address, 4))[0]
    put(0x209A798, 1)  # Publisher movie is playing, timer disabled by start.
    put(0xB6D970, 0)
    put(0x204E2F8, 1)  # Native movie handle.
    put(0xB693A8, 0x3000000)
    emu.mem_write(0x3000000, bytes.fromhex("C2 04 00"))
    for address in (0x55ABD0, 0x403D99, 0x55A510, 0x409A57):
        emu.mem_write(address, b"\xc3")
    scheduled = []
    def observe(uc, address, size, data):
        if address == 0x409A57:
            scheduled.append(get(0xB6D970))
    emu.hook_add(UC_HOOK_CODE, observe)
    for _ in range(2):
        stack = 0x3108000
        emu.reg_write(UC_X86_REG_ESP, stack)
        put(stack + 0x30, 0x3001000)
        emu.emu_start(0x4703F7, 0x3001000, count=200)
    return get(0xB6D970), get(0x209A798), get(0x204E2F8), scheduled

assert run_intro(patch) == (1, 0, 0, [1])
assert run_intro("470401 = 90 90") == (0, 1, 1, [0, 0])
print("FF8 Fast Start EXE contract and movie-stop timing regression passed")
