"""List executable instructions that compare or load FF8's Draw command ID."""

from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
import pefile


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def main() -> int:
    pe = pefile.PE(str(EXE), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.skipdata = True
    for section in pe.sections:
        if not section.Characteristics & 0x20000000:
            continue
        start = base + section.VirtualAddress
        data = section.get_data()
        for instruction in decoder.disasm(data, start):
            operands = instruction.op_str.lower()
            if "0x16" not in operands:
                continue
            if instruction.mnemonic not in {
                "cmp", "mov", "push", "and", "sub", "add", "test",
            }:
                continue
            if 0x480000 <= instruction.address < 0x4D0000:
                raw = instruction.bytes.hex(" ")
                print(
                    f"{instruction.address:08X}  {raw:<28} "
                    f"{instruction.mnemonic:<8} {instruction.op_str}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
