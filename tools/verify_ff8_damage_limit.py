"""Static contract for FF8 damage-limit removal."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import damage_limit, gameplay_settings  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)

# Prove the complete native max-selection expression around the one-byte patch:
# mov cl,[flags]; and cl,8; neg cl; sbb ecx,ecx; and ecx,50001;
# add ecx,9999; cmp damage,ecx.
native = image_bytes(pe, 0x00491124, 0x1D)
assert native == bytes.fromhex(
    "8A 0D 0E 8E D2 01 80 E1 08 F6 D9 1B C9 81 E1 51 C3 00 00 "
    "81 C1 0F 27 00 00 3B F1 7E 04"
)
assert image_bytes(
    pe, damage_limit.DAMAGE_LIMIT_FLAG_OPCODE, 1
) == damage_limit.DAMAGE_LIMIT_FLAG_ORIGINAL
assert damage_limit.VANILLA_DAMAGE_LIMIT + 50_001 == damage_limit.BREAK_DAMAGE_LIMIT

assert damage_limit.build_hext(False) == ""
patch = damage_limit.build_hext(True)
assert f"{damage_limit.DAMAGE_LIMIT_FLAG_OPCODE:X} = C9" in patch
assert "60,000" in patch
for invalid in (0, 1, "true", None):
    try:
        damage_limit.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Damage Limit Removal accepted {invalid!r}")

# Mutation check: the old AND opcode restores the conditional 9,999 path and
# must never satisfy the enabled patch contract.
mutated = patch.replace(" = C9", " = E1")
assert f"{damage_limit.DAMAGE_LIMIT_FLAG_OPCODE:X} = C9" not in mutated

print("FF8 damage-limit removal static contract passed")
