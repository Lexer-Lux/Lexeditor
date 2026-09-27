"""No Hext hook may overwrite an instruction a native branch jumps to.

A hook that replaces several instructions with one jump breaks any native
jump or call aimed at the second or later of them: the CPU lands inside the
new jump. Vibration Consolidation did exactly that at 004C8D8F (004C8CC2
jumps to 004C8D93), and pausing early in an enemy attack crashed. Every
tweak that can be switched on alone is switched on here, and every native
branch target in .text is checked against the bytes the patch overwrites.
"""
import inspect
import re
import struct

import pytest

from plugins.ff8 import gameplay_settings, paths

capstone = pytest.importorskip("capstone")
EXE = paths.GAME_ROOT / "FF8_EN.exe"
# These need a plan or a partner setting and cannot be switched on alone.
NOT_ALONE = {"world_map_fullscreen", "battle_results_help", "drop_chance_enabled"}


def _text_section(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional = struct.unpack_from("<H", data, pe + 20)[0]
    for index in range(count):
        at = pe + 24 + optional + index * 40
        if data[at:at + 5] == b".text":
            size, rva, raw_size, raw = struct.unpack_from("<IIII", data, at + 8)
            return 0x400000 + rva, size, data[raw:raw + raw_size]
    raise AssertionError("no .text section")


def test_no_native_branch_lands_inside_a_hook():
    if not EXE.is_file():
        pytest.skip("FF8_EN.exe is not installed")
    signature = inspect.signature(gameplay_settings.build_hext)
    switches = {name: True for name, parameter in signature.parameters.items()
                if isinstance(parameter.default, bool) and name not in NOT_ALONE}
    patch = gameplay_settings.build_hext(10, **switches)
    base, size, code = _text_section(EXE.read_bytes())
    spans = []
    for line in patch.splitlines():
        match = re.fullmatch(r"\s*([0-9A-Fa-f]+)\s*=\s*([0-9A-Fa-f ]+)", line)
        if match:
            start = int(match[1], 16)
            length = len(bytes.fromhex(match[2]))
            if base <= start < base + size and length > 1:
                spans.append((start, start + length))
    assert len(spans) > 50, "the patch should touch many code sites"
    inside = {}
    for low, high in spans:
        for address in range(low + 1, high):
            inside[address] = (low, high)
    disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    disassembler.skipdata = True
    problems = []
    for instruction in disassembler.disasm(code, base):
        if not (instruction.mnemonic.startswith("j") or instruction.mnemonic == "call"):
            continue
        if not instruction.op_str.startswith("0x"):
            continue
        target = int(instruction.op_str, 16)
        span = inside.get(target)
        if span and not span[0] <= instruction.address < span[1]:
            # Rewritten in the patch itself, as the pause fix does.
            if any(low <= instruction.address < high for low, high in spans):
                continue
            problems.append(f"{instruction.address:08X} -> {target:08X} inside {span[0]:08X}-{span[1]:08X}")
    assert not problems, problems
