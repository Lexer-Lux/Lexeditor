"""Static contract for FF8 True ATB Wait, GitHub issue #63."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings, true_atb_wait_issue_63 as atb  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def target(code: bytes, offset: int, address: int) -> int:
    displacement = int.from_bytes(code[offset + 1:offset + 5], "little", signed=True)
    return address + offset + 5 + displacement


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)
assert image_bytes(pe, atb.ATB_WAIT_HOOK, 5) == atb.ATB_WAIT_HOOK_ORIGINAL
assert atb.build_hext(False) == ""
code = atb.build_code_cave()
assert len(code) == atb.CODE_CAVE_LENGTH == 0x2D
# The wrapper must retain all native battle-state stop conditions and add party
# readiness independently of Active/Wait configuration. The retired version
# inspected config bit 0x10 and therefore did nothing in Active mode.
assert target(code, 0, atb.CODE_CAVE) == atb.WAIT_PREDICATE
assert bytes((0xF6, 0x80)) + atb.CONFIG_FLAGS_OFFSET.to_bytes(4, "little") \
    + bytes((atb.ATB_WAIT_CONFIG_MASK,)) not in code
assert atb.CONFIG_ACCESSOR.to_bytes(4, "little") not in code
assert bytes.fromhex("85 C0 75 1E") in code
assert bytes.fromhex("B9 8C 7B D2 01 BA 03 00 00 00") in code
assert bytes.fromhex("8A 01 24 09 3C 09") in code
assert bytes.fromhex("81 C1 D0 00 00 00 4A 75 EF") in code
assert code.endswith(bytes.fromhex("31 C0 C3 B8 01 00 00 00 C3"))
patch = atb.build_hext(True)
assert f"{atb.ATB_WAIT_HOOK:X} = E8" in patch
assert f"{atb.CODE_CAVE:X}:{atb.CODE_CAVE_LENGTH:X}" in patch
for invalid in (0, 1, "true", None):
    try:
        atb.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"True ATB Wait accepted {invalid!r}")

mutated = bytearray(code)
mutated[code.index(bytes.fromhex("24 09 3C 09"))] = 0x08
assert bytes.fromhex("24 09 3C 09") not in mutated

# A mutation that restores the old configuration-only gate must be rejected by
# the contract above: the native predicate call is required and direct config
# inspection is forbidden.
retired = bytearray(code)
retired[:5] = atb._rel32(0xE8, atb.CODE_CAVE, atb.CONFIG_ACCESSOR)
assert target(bytes(retired), 0, atb.CODE_CAVE) != atb.WAIT_PREDICATE

print("FF8 True ATB Wait static contract passed")
