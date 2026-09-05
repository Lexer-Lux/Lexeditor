"""Map every kernel.bin section to its runtime address in FF8_EN.exe.

getGFhpForLvl at 0x496120 reads kernel section 3 at the absolute address
0x01CF4DD4, with a 132-byte stride and the HP modifiers at record offset 0x14.
That pins the whole kernel image at 0x01CF3E48, so every section has a known
runtime address - which is what turns "trace the refine menu somehow" into
"break on reads of section 18 at 0x01CF8208".

It also reports which sections the code reaches ABSOLUTELY, by scanning .text
for the raw little-endian addresses rather than disassembling (a linear sweep
desyncs on the data and padding between functions and misses most of them).
Only one instruction touches section 18, and it belongs to the GF stat
recompute at 0x00495D80, so the refine menu reaches its records through a
pointer - which is why three static hunts for the five refine table bases found
nothing to find.
"""

from __future__ import annotations

import collections
from pathlib import Path
import struct

import pefile

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
KERNEL = Path(r"C:\Users\Lexer\AppData\Local\Lexeditor\game-data\ff8\baseline\en\main\kernel.bin")
# Derived, not assumed: 0x01CF4DD4 (section 3 record 0, field 0x14) minus that
# field offset minus section 3's own file offset.
KERNEL_BASE = 0x01CF3E48


def main() -> int:
    raw = KERNEL.read_bytes()
    sections = {
        section_id: KERNEL_BASE + int.from_bytes(raw[section_id * 4:section_id * 4 + 4], "little")
        for section_id in range(1, 32)
    }
    ordered = sorted((address, section_id) for section_id, address in sections.items())
    end = KERNEL_BASE + len(raw)

    def section_of(value: int) -> int:
        found = 0
        for address, section_id in ordered:
            if value >= address:
                found = section_id
            else:
                break
        return found

    print(f"kernel.bin is {len(raw)} bytes, loaded at 0x{KERNEL_BASE:08X}")
    for section_id, address in sorted(sections.items()):
        print(f"  section {section_id:>2} -> 0x{address:08X}")

    pe = pefile.PE(str(EXE), fast_load=True)
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    start = pe.OPTIONAL_HEADER.ImageBase + text.VirtualAddress
    data = text.get_data()
    counts: collections.Counter = collections.Counter()
    samples = collections.defaultdict(list)
    for offset in range(0, len(data) - 4):
        value = struct.unpack_from("<I", data, offset)[0]
        if KERNEL_BASE <= value < end:
            section_id = section_of(value)
            counts[section_id] += 1
            if len(samples[section_id]) < 4:
                samples[section_id].append((start + offset, value))

    print("\nabsolute references from .text, by section:")
    for section_id in sorted(counts):
        label = f"section {section_id:>2}" if section_id else "kernel header"
        where = ", ".join(
            f"{address:08X}->+0x{value - sections.get(section_id, KERNEL_BASE):X}"
            for address, value in samples[section_id])
        print(f"  {label}: {counts[section_id]:>4}  {where}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
