"""Static contract for FF8 True ATB Wait, GitHub issue #63."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import gameplay_settings, true_atb_wait_issue_63 as atb  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def target(code: bytes, offset: int, address: int) -> int:
    displacement = int.from_bytes(code[offset + 1:offset + 5], "little", signed=True)
    return address + offset + 5 + displacement


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)
assert image_bytes(pe, atb.ATB_WAIT_HOOK, 5) == atb.ATB_WAIT_HOOK_ORIGINAL
assert atb.build_hext(False) == ""
code = atb.build_code_cave()

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX
assert target(code, 0, atb.CODE_CAVE) == atb.WAIT_PREDICATE
assert image_bytes(pe, 0x4842D6, 8) == bytes.fromhex("85 C0 0F 84 9E 01 00 00")
assert image_bytes(pe, atb.WAIT_PREDICATE, 7) == bytes.fromhex("F6 05 3C E7 CF 01 01")
for native in (0, 1):
    for wait_mode in (0, 1):
        for ready_slot in (-1, 0, 1, 2):
            vm = Uc(UC_ARCH_X86, UC_MODE_32)
            for base, size in ((0x400000, 0x100000), (0x1CF0000, 0x10000),
                               (0x1D20000, 0x10000), (0x2790000, 0x10000),
                               (0x3000000, 0x10000)):
                vm.mem_map(base, size)
            vm.mem_write(atb.CODE_CAVE, code)
            vm.mem_write(atb.WAIT_PREDICATE, b"\xB8" + native.to_bytes(4,"little") + b"\xC3")
            vm.mem_write(atb.CONFIG_FLAGS, bytes((wait_mode,)))
            for slot in range(3):
                vm.mem_write(atb.PARTY_FLAGS + slot * atb.PARTICIPANT_STRIDE,
                             bytes((9 if slot == ready_slot else 1,)))
            stack = 0x3008000
            vm.mem_write(stack, (0x400000).to_bytes(4,"little"))
            vm.reg_write(UC_X86_REG_ESP, stack)
            vm.emu_start(atb.CODE_CAVE, 0x400000, count=200)
            expected = int(bool(native) and not (wait_mode and ready_slot >= 0))
            assert vm.reg_read(UC_X86_REG_EAX) == expected, (native,wait_mode,ready_slot)
assert atb.build_hext(False) == ""
print("PASS: native branch verified; Wait/Active, native stops, all three ready slots executed")
