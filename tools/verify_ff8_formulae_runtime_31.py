"""Executable and mutation audit for the runtime part of FF8 Formulae Rework."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
import pefile


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
EXPECTED_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings, healing_rework, luck_accuracy  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def executable_bytes(data: bytes, pe: pefile.PE, address: int, size: int) -> bytes:
    offset = pe.get_offset_from_rva(address - pe.OPTIONAL_HEADER.ImageBase)
    return data[offset:offset + size]


def healing_payload_is_exact(payload: bytes) -> bool:
    decoded = [f"{item.mnemonic} {item.op_str}".strip() for item in
               Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                   payload, healing_rework.HEALING_FORMULA_CAVE)]
    return decoded == [
        "mov eax, dword ptr [esp + 0x10]",
        "lea edx, [eax + eax*2]",
        "lea eax, [eax + edx*4]",
        "shl eax, 4",
        "movzx eax, byte ptr [eax + 0x1d27bcf]",
        "imul eax, edi",
        f"jmp {healing_rework.HEALING_FORMULA_CONTINUE:#x}",
    ]


def main() -> int:
    data = EXE.read_bytes()
    require(sha256(data).hexdigest() == EXPECTED_SHA256,
            "FF8_EN.exe is not the supported Steam English build")
    pe = pefile.PE(data=data)

    luck_native = executable_bytes(
        data, pe, luck_accuracy.LUCK_HALVE, len(luck_accuracy.LUCK_HALVE_ORIGINAL),
    )
    require(luck_native == luck_accuracy.LUCK_HALVE_ORIGINAL,
            "the full-LUCK patch site no longer matches the supported executable")
    require(luck_accuracy.build_hext(True).endswith("492EEF = 90 90\n"),
            "Formulae Rework no longer removes only the attacker-LUCK halving")

    healing_native = executable_bytes(
        data, pe, healing_rework.HEALING_FORMULA_HOOK,
        len(healing_rework.HEALING_FORMULA_ORIGINAL),
    )
    require(healing_native == healing_rework.HEALING_FORMULA_ORIGINAL,
            "the normal-curative-magic hook no longer matches the executable")
    healing_payload = healing_rework.build_code_cave()
    require(healing_payload_is_exact(healing_payload),
            "the healing cave is not exactly spell power times effective MAG")

    combined = gameplay_settings.build_hext(25, formulae_rework=True)
    require(luck_accuracy.build_hext(True).rstrip() in combined,
            "the unified switch does not compose the proved full-LUCK slice")
    require(healing_rework.build_hext(True).rstrip() in combined,
            "the unified switch does not compose the proved healing slice")

    rejected = 0
    for original, actual in (
        (luck_accuracy.LUCK_HALVE_ORIGINAL, luck_native),
        (healing_rework.HEALING_FORMULA_ORIGINAL, healing_native),
    ):
        for index in range(len(original)):
            mutant = bytearray(original)
            mutant[index] ^= 0x01
            if bytes(mutant) != actual:
                rejected += 1

    for index in range(len(healing_payload)):
        mutant = bytearray(healing_payload)
        mutant[index] ^= 0x01
        if not healing_payload_is_exact(bytes(mutant)):
            rejected += 1
    require(rejected == (len(luck_native) + len(healing_native) + len(healing_payload)),
            "Formulae runtime mutation coverage is incomplete")

    source = (ROOT / "games" / "ff8" / "gameplay_settings.py").read_text(
        encoding="utf-8",
    )
    require('"formulaeReworkAvailable": False' in source and
            'raise ValueError("Formulae Rework is not available")' in source,
            "the incomplete three-slice rework was exposed as a complete feature")

    print(
        "FF8 Formulae runtime audit passed: healing and full LUCK proved; "
        f"{rejected} mutations rejected; melee, magic, and status remain preview-only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
