"""Static evidence contract for the FF8 enemy Flying property."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, gameplay_settings  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)

# This is the complete enemy-only part of the status-normalization routine at
# 00491820. It reads raw c0m byte 0xF7. Bit 0 preserves Zombie (status 1,
# 0x0040). Bit 1 preserves status-2 bit 0x2000, which the kernel status table
# identifies as Float.
native = image_bytes(pe, 0x00491841, 0x43)
assert native == bytes.fromhex(
    "8B 95 10 7B D2 01 8A 4C 24 10 F6 C1 40 8B 02 74 11 "
    "F6 80 F7 00 00 00 01 74 08 81 64 24 10 BF FF 00 00 "
    "8B 0D 34 A2 D2 01 F6 C5 20 74 16 F6 80 F7 00 00 00 02 "
    "74 0D A1 34 A2 D2 01 80 E4 DF A3 34 A2 D2 01"
)

field = next(row for row in formats.ENEMY_FIELDS if row["name"] == "flying")
assert field["offset"] == 0xF7
assert field["mask"] == 0x02
assert "intrinsic Float" in field["help"]
assert "cannot remove" in field["help"]

status_2 = formats.LOOKUPS["status_2"]["entries"]
float_status = next(row for row in status_2 if row["name"] == "Float")
assert float_status["mask"] == 0x2000

# Mutation check: calling this an elemental or EVA field would repeat the old
# unsupported inference. The proven reader only preserves the Float status.
lower_help = field["help"].casefold()
assert "eva" not in lower_help
assert "earth damage" not in lower_help

print("FF8 Flying-property executable trace passed")
