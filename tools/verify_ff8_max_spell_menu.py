"""Execute native Max Spell battle fragments. Requires capstone and unicorn.

Run with the test-only dependency directory on PYTHONPATH when needed.
No process memory, save, or game installation is modified.
"""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from games.ff8 import max_spell

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--exe", type=Path, required=True)
EXE = parser.parse_args().exe
raw = EXE.read_bytes()
assert sha256(raw).hexdigest() == "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
max_spell.verify_executable(BytesIO(raw))
patch = max_spell.build_hext(True, 255)
replacements = {int(a, 16): bytes.fromhex(b) for a, b in re.findall(r"(?m)^([0-9A-F]+) = ([0-9A-F ]+)$", patch)}


def machine(mutant=None):
    vm = Uc(UC_ARCH_X86, UC_MODE_32)
    vm.mem_map(0x400000, 0x100000)
    vm.mem_map(0x2000000, 0x1000)
    # This supported PE has file offsets equal to VA minus image base here.
    vm.mem_write(0x400000, raw[:0x100000])
    for address, original, _replacement in max_spell.UNSIGNED_BATTLE_STOCK_SITES:
        vm.mem_write(address, original if address == mutant else replacements[address])
    return vm


def check(mutant=None):
    vm = machine(mutant)
    for stock in (0, 1, 127, 128, 150, 254, 255):
        for start, register, target in ((0x4C8A14, UC_X86_REG_EAX, 0x4C8A22), (0x4FE3F0, UC_X86_REG_ECX, 0x4FE427)):
            vm.reg_write(register, stock)
            vm.emu_start(start, 0x500000, count=2)
            assert (vm.reg_read(UC_X86_REG_EIP) == target) == bool(stock), (hex(start), stock, "visibility")
        vm.mem_write(0x2000000, bytes((1, stock)))
        for start, source, destination in ((0x4C8A52, UC_X86_REG_ESI, UC_X86_REG_EDX), (0x4FE2A5, UC_X86_REG_EAX, UC_X86_REG_ESI)):
            vm.reg_write(source, 0x2000000)
            vm.emu_start(start, 0x500000, count=1)
            assert vm.reg_read(destination) == stock, (hex(start), stock, "stock value")
        for used in (0, 1, 2, 3):
            vm.mem_write(0x2000000, bytes((1, stock)))
            vm.reg_write(UC_X86_REG_ECX, 0x2000001)
            vm.reg_write(UC_X86_REG_EDI, used)
            vm.reg_write(UC_X86_REG_EBP, 0)
            vm.emu_start(0x4FE706, 0x4FE71B)
            expected = max(0, stock - used)
            assert bytes(vm.mem_read(0x2000000, 2)) == bytes((1 if expected else 0, expected)), (stock, used, "debit")


check()
for address, original, _replacement in max_spell.UNSIGNED_BATTLE_STOCK_SITES:
    try:
        check(address)
    except AssertionError:
        pass
    else:
        raise AssertionError(f"Original signed instruction survived mutation at {address:X}")
    changed = bytearray(raw)
    changed[address - 0x400000] ^= 1
    try:
        max_spell.verify_executable(BytesIO(changed))
    except RuntimeError:
        pass
    else:
        raise AssertionError(f"Changed executable guard accepted at {address:X}")
assert max_spell.build_hext(False, 255) == ""
print("Native x86: visibility, numeric display, selection stock, exact debit; 0..255 boundaries; 5 bad-code and 5 executable mutations rejected")
