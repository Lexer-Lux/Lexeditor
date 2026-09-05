from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import sys

import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import single_gf as single


EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def branch_target(code: bytes, offset: int, address: int, size: int) -> int:
    displacement = int.from_bytes(code[offset + size - 4:offset + size],
                                  "little", signed=True)
    return address + offset + size + displacement


def verify_cave(code: bytes) -> None:
    require(len(code) == single.CODE_CAVE_LENGTH, "code cave has the wrong size")
    require(code[:2] == bytes.fromhex("85 D0"),
            "original existing-bit test was not preserved")
    require(code[2:4] == bytes.fromhex("0F 85"),
            "an existing GF no longer keeps the vanilla no-op path")
    require(branch_target(code, 2, single.DEFAULT_CODE_CAVE, 6) == single.ADD_GATE_SKIP,
            "existing-bit branch no longer reaches the vanilla skip path")
    require(code[8:10] == bytes.fromhex("85 D2"),
            "the proposed GF mask is not tested")
    require(code[10:12] == bytes.fromhex("0F 85"),
            "a different GF is not refused when the mask is nonzero")
    require(branch_target(code, 10, single.DEFAULT_CODE_CAVE, 6) == single.ADD_GATE_SKIP,
            "nonzero-mask branch no longer reaches the vanilla skip path")
    require(branch_target(code, 16, single.DEFAULT_CODE_CAVE, 5) == single.ADD_GATE_OR,
            "empty-mask branch no longer reaches the vanilla add path")


require(EXE.is_file(), "installed FF8_EN.exe is missing")
require(sha256(EXE.read_bytes()).hexdigest() == single.SUPPORTED_EXE_SHA256,
        "installed FF8_EN.exe is not the researched Steam English build")
pe = pefile.PE(str(EXE), fast_load=True)
require(image_bytes(pe, single.ADD_GATE_HOOK, single.ADD_GATE_HOOK_LENGTH) ==
        single.ADD_GATE_ORIGINAL, "GF junction-add gate bytes changed")
require(image_bytes(pe, single.FIELD_ENTER_HOOK, len(single.FIELD_ENTER_ORIGINAL)) ==
        single.FIELD_ENTER_ORIGINAL, "field-enter bytes changed")
require(image_bytes(pe, single.WORLDMAP_ENTER_HOOK, len(single.WORLDMAP_ENTER_ORIGINAL)) ==
        single.WORLDMAP_ENTER_ORIGINAL, "world-map-enter bytes changed")

require(single.allows_add(0, 15, True), "the first GF must be addable")
require(not single.allows_add(0b0001, 1, True),
        "a second different GF must be refused")
require(single.allows_add(0b0001, 0, True),
        "an existing GF must keep its no-op path")
require(not single.allows_add(0b1111, 4, True),
        "a pre-existing multi-GF mask must refuse another GF")
require(single.allows_add(0b0001, 1, False),
        "disabled Single GF must preserve vanilla additions")
require(single.normalize_masks([0, 1, 2, 3, 0x8000, 0x8001, 0xFFFF, 4]) ==
        [0, 1, 2, 0, 0x8000, 0, 0, 4],
        "existing multi-GF characters must lose all junctioned GFs")
for invalid in (0, 1, "true", None):
    try:
        single.boolean(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"non-boolean Single GF value was accepted: {invalid!r}")

require(single.build_hext(False) == "", "disabled Single GF must emit no patch")
patch = single.build_hext(True)
require(f"{single.ADD_GATE_HOOK:X} =" in patch, "enabled setting is missing its hook")
require(f"{single.DEFAULT_CODE_CAVE:X}:{single.CODE_CAVE_LENGTH:X}" in patch,
        "enabled setting is missing its cave reservation")
for address, length in (
        (single.FIELD_ENTER_CAVE, single.FIELD_ENTER_CAVE_LENGTH),
        (single.WORLDMAP_ENTER_CAVE, single.WORLDMAP_ENTER_CAVE_LENGTH),
        (single.NORMALIZE_CAVE, single.NORMALIZE_CAVE_LENGTH)):
    require(f"{address:X}:{length:X}" in patch,
            f"enabled setting is missing cleanup cave {address:X}")
cave_line = next(line for line in patch.splitlines()
                 if line.startswith(f"{single.DEFAULT_CODE_CAVE:X} = "))
cave = bytes.fromhex(cave_line.split("=", 1)[1].strip())
verify_cave(cave)

mutated = bytearray(cave)
mutated[11] = 0x84  # JNE -> JE
try:
    verify_cave(bytes(mutated))
except AssertionError:
    pass
else:
    raise AssertionError("reversed Single GF condition was not detected")

hook_addresses = [int(match.group(1), 16) for match in
                  re.finditer(r"^([0-9A-F]+) = ", patch, re.MULTILINE)]
require(hook_addresses == [
    single.ADD_GATE_HOOK,
    single.FIELD_ENTER_HOOK,
    single.WORLDMAP_ENTER_HOOK,
    single.DEFAULT_CODE_CAVE,
    single.FIELD_ENTER_CAVE,
    single.WORLDMAP_ENTER_CAVE,
    single.NORMALIZE_CAVE,
], "patch must touch only the verified add and gameplay-entry paths")

normalizer_line = next(line for line in patch.splitlines()
                       if line.startswith(f"{single.NORMALIZE_CAVE:X} = "))
normalizer = bytes.fromhex(normalizer_line.split("=", 1)[1].strip())
require(normalizer.count(bytes.fromhex("81 C7 98 00 00 00")) == 1,
        "cleanup must walk the verified 0x98-byte character stride")
require(bytes.fromhex("66 C7 07 00 00") in normalizer,
        "cleanup must clear the complete 16-bit GF mask")
require(bytes.fromhex("8D 50 FF 85 D0") in normalizer,
        "cleanup must use the one-hot mask test before clearing")

print("FF8 Single GF add gate and existing-save cleanup contract passed")
