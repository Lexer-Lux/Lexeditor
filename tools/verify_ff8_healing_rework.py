"""Static, semantic, and mutation contract for FF8 Spell Healing Rework."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
sys.path.insert(0, str(ROOT))

from games.ff8 import healing_rework  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def executable_bytes(address: int, size: int) -> bytes:
    data = EXE.read_bytes()
    require(sha256(data).hexdigest() == EXPECTED_SHA256,
            "FF8_EN.exe is not the supported Steam English build")
    pe = pefile.PE(data=data)
    offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
    return data[offset:offset + size]


def executable_code(address: int, size: int) -> dict[int, str]:
    data = EXE.read_bytes()
    pe = pefile.PE(data=data)
    offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
    return {item.address: f"{item.mnemonic} {item.op_str}".strip()
            for item in Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                data[offset:offset + size], address)}


def main() -> int:
    h = healing_rework
    require(executable_bytes(h.HEALING_FORMULA_HOOK,
                             len(h.HEALING_FORMULA_ORIGINAL)) ==
            h.HEALING_FORMULA_ORIGINAL,
            "normal curative-magic formula hook bytes changed")
    native = executable_code(0x00493373, 0xD8)
    for address, instruction in {
        0x0049337C: "sub eax, 7",
        0x0049337F: "je 0x493398",       # mode 7 only
        0x00493382: "jne 0x4933e4",      # mode 8 keeps its own arithmetic
        0x004933E8: "test byte ptr [esi + 0x1d27b18], 0x40",
        0x004933FC: "sar eax, 1",         # Shell
        0x00493405: "test cl, 4",
        0x0049340A: "xor eax, eax",       # Invincible
        0x0049340C: "test cl, 0x40",
        0x00493413: "neg eax",            # Zombie
        0x0049343D: "call 0x491820",      # cure statuses
    }.items():
        require(native.get(address) == instruction,
                f"native healing continuation changed at {address:#x}")

    payload = h.build_code_cave()
    require(len(payload) == h.HEALING_FORMULA_CAVE_LENGTH,
            "healing cave length is unstable")
    decoded = [f"{i.mnemonic} {i.op_str}".strip() for i in
               Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                   payload, h.HEALING_FORMULA_CAVE)]
    for instruction in (
        "mov eax, dword ptr [esp + 0x10]",
        "movzx eax, byte ptr [eax + 0x1d27bcf]",
        "imul eax, edi",
        f"jmp {h.HEALING_FORMULA_CONTINUE:#x}",
    ):
        require(instruction in decoded, f"healing cave lost {instruction}")
    require(not any(item.startswith("call ") for item in decoded),
            "reworked healing must not retain the vanilla random roll")

    require(h.build_hext(False) == "", "default-off must emit no patch")
    patch = h.build_hext(True)
    require(f"{h.HEALING_FORMULA_HOOK:X} =" in patch and
            f"{h.HEALING_FORMULA_CAVE:X} =" in patch,
            "enabled healing patch is incomplete")
    for invalid in (0, 1, None, "true"):
        try:
            h.build_hext(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("non-boolean enable state was accepted")

    require(h.reworked_healing(30, 120) == 3600,
            "spell power * MAG contract changed")
    require(h.apply_native_healing_modifiers(3600, shell=True) == 1800,
            "native Shell branch was not preserved")
    require(h.apply_native_healing_modifiers(
        3600, shell=True, zombie=True) == -1800,
        "native Zombie sign branch was not preserved")
    require(h.apply_native_healing_modifiers(
        3600, shell=True, invincible=True, zombie=True) == 0,
        "native Invincible branch was not preserved")
    print("FF8 Spell Healing Rework static and semantic contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
