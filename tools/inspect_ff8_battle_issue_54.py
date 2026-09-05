"""Disassemble the verified FF8 battle paths used by GitHub issue #54."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM
import pefile


EXPECTED_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
DEFAULT_EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
TARGETS = {
    "battle command and Draw dispatcher": (0x0048D200, 0x500),
    "vanilla Draw amount": (0x0048FD20, 0x180),
    "battle menu loop": (0x004A2690, 0x300),
    "battle menu command setup": (0x004A3D20, 0x240),
    "battle menu command setup 2": (0x004A3EE0, 0x240),
    "battle menu state": (0x004A6660, 0x240),
}


def main() -> int:
    executable = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXE
    data = executable.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA256:
        raise SystemExit(f"Unsupported FF8_EN.exe SHA-256: {actual}")
    pe = pefile.PE(data=data, fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    text = next(section for section in pe.sections if section.Name.rstrip(b"\0") == b".text")
    text_va = image_base + text.VirtualAddress
    text_data = text.get_data()
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = True

    def read(va: int, size: int) -> bytes:
        return pe.get_data(va - image_base, size)

    instructions = list(decoder.disasm(text_data, text_va))
    print(f"FF8_EN.exe {actual}")
    selected = sys.argv[2].casefold() if len(sys.argv) > 2 else ""
    targets = {label: value for label, value in TARGETS.items() if not selected or selected in label.casefold()}
    if not targets:
        raise SystemExit(f"Unknown target filter: {selected}")
    for label, (target, length) in targets.items():
        print(f"\n## {label} 0x{target:08X}")
        xrefs = []
        for instruction in instructions:
            if instruction.mnemonic in {"call", "jmp"} and instruction.operands and instruction.operands[0].type == X86_OP_IMM and instruction.operands[0].imm == target:
                xrefs.append(instruction.address)
        print("xrefs:", ", ".join(f"0x{value:08X}" for value in xrefs) or "none")
        for instruction in decoder.disasm(read(target, length), target):
            raw = instruction.bytes.hex(" ").upper()
            print(f"{instruction.address:08X}  {raw:<24} {instruction.mnemonic:<7} {instruction.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
