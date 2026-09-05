"""Locate FF8 code that validates a character's battle command slots.

Quistis keeps Treatment in the command menu after her GF no longer has the
ability learned, so something either never revalidates the slots or reads a
stale copy. Treatment is ability 28 (0x1C) in kernel section 13 and battle
command 25 (0x19).
"""

from collections import defaultdict
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
import pefile

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
TREATMENT_COMMAND = 0x19
TREATMENT_ABILITY = 0x1C


def main() -> int:
    pe = pefile.PE(str(EXE), fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = False
    decoder.skipdata = True

    # Collect every call target so we can bucket hits by the function holding
    # them; FF8 has no symbols, so call targets are the only function starts
    # we can name with certainty.
    starts: set[int] = set()
    windows: dict[int, list] = defaultdict(list)
    for section in pe.sections:
        # .bind is the DotEmu DRM wrapper: executable but packed, so
        # disassembling it yields only noise. Real game code is .text.
        if section.Name.rstrip(bytes(1)) != b".text":
            continue
        start = base + section.VirtualAddress
        data = section.get_data()
        listing = list(decoder.disasm(data, start))
        for instruction in listing:
            if instruction.mnemonic == "call" and instruction.op_str.startswith("0x"):
                try:
                    starts.add(int(instruction.op_str, 16))
                except ValueError:
                    pass
        for index, instruction in enumerate(listing):
            operands = instruction.op_str.lower()
            if instruction.mnemonic not in {"cmp", "mov", "movzx", "push", "test"}:
                continue
            if not (
                operands.endswith(", 0x19")
                or operands.endswith(", 0x1c")
                or operands.endswith(", 0x19]")
            ):
                continue
            windows[instruction.address] = listing[max(0, index - 6):index + 7]

    ordered = sorted(starts)

    def owner(address: int) -> int:
        low, high = 0, len(ordered)
        while low < high:
            middle = (low + high) // 2
            if ordered[middle] <= address:
                low = middle + 1
            else:
                high = middle
        return ordered[low - 1] if low else 0

    by_function: dict[int, list[int]] = defaultdict(list)
    for address in windows:
        by_function[owner(address)].append(address)

    # A slot validator should touch BOTH the command id and the ability id, so
    # rank functions that reference both constants.
    interesting = []
    for function, addresses in by_function.items():
        text = "\n".join(
            f"{i.mnemonic} {i.op_str}"
            for address in addresses
            for i in windows[address]
        ).lower()
        if "0x19" in text and "0x1c" in text:
            interesting.append((len(addresses), function, addresses))

    interesting.sort(reverse=True)
    print(f"functions referencing both 0x19 and 0x1C: {len(interesting)}")
    for count, function, addresses in interesting[:8]:
        print(f"\n=== sub_{function:08X}  ({count} hits) ===")
        for address in sorted(addresses)[:2]:
            for instruction in windows[address]:
                marker = "->" if instruction.address == address else "  "
                print(f"  {marker} {instruction.address:08X}  {instruction.mnemonic} {instruction.op_str}")
            print("   ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
