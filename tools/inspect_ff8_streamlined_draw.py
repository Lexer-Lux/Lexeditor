"""Print the proved FF8 Draw menu builders and terminal execution cases."""

from __future__ import annotations

from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
import pefile


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
RANGES = (
    (0x004ADD20, 0x004AE250, "Battle target controller and Draw source list"),
    (0x004AE250, 0x004AE3A0, "Draw spell-list producer candidate"),
    (0x004AE3A0, 0x004AE520, "Stock/Cast selection and commit"),
    (0x004AE800, 0x004AEE00, "Draw spell and Stock/Cast controller states"),
    (0x004AF150, 0x004AF210, "Draw controller tail states"),
    (0x004AF4F0, 0x004AF900, "Battle target and Draw menu renderer"),
    (0x004BBB70, 0x004BBD00, "Battle-menu state dispatcher"),
    (0x0048C8D0, 0x0048C920, "Single/Double magic child builder"),
    (0x0048C920, 0x0048C9A0, "Generic command child builder"),
    (0x0048C9A0, 0x0048CA70, "Single/Double/Triple magic child builder"),
    (0x0048CA70, 0x0048CC20, "Adjacent descriptor builders"),
    (0x0048D4F0, 0x0048D750, "Command terminal cases 9 and 10"),
    (0x004BBD00, 0x004BBF10, "Generic spell confirmation state"),
    (0x004BBF10, 0x004BC2A0, "Adjacent battle-menu states"),
    (0x004BC3E0, 0x004BC6C0, "Command commit and target states"),
    (0x004BCA80, 0x004BCB80, "Magic child-menu dispatcher"),
)


def main() -> int:
    pe = pefile.PE(str(EXE), fast_load=True)
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    for start, end, label in RANGES:
        print(f"\n{label} {start:08X}..{end:08X}")
        data = image[start - base:end - base]
        for instruction in decoder.disasm(data, start):
            print(f"{instruction.address:08X}  {instruction.bytes.hex(' '):<24} {instruction.mnemonic:<8} {instruction.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
