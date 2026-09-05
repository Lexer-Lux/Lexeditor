"""Static and mutation contract for FF8 Fast Start."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pefile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import fast_start  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX = ROOT / "_scratch" / "ffnx-upstream"
EXPECTED_EXE = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
EXPECTED_FFNX = "1e291885da4ddb482188b81a5198d56a1915fde6"


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == EXPECTED_EXE
pe = pefile.PE(str(EXE), fast_load=True)

# Prove the exact credits-completion call and the unchanged native transition
# that follows it. Fast Start must not replace the initial mode callbacks.
assert image_bytes(
    pe, fast_start.CREDITS_COMPLETION_CALL,
    len(fast_start.CREDITS_COMPLETION_ORIGINAL),
) == fast_start.CREDITS_COMPLETION_ORIGINAL
native_transition = bytes.fromhex(
    "85 C0 74 2E 8D 44 24 08 56 50 C7 44 24 18 40 04 47 00 "
    "C7 44 24 1C 70 D9 56 00 C7 44 24 20 20 05 47 00"
)
assert image_bytes(pe, 0x0052DAE4, len(native_transition)) == native_transition

# FFNx is independent primary evidence for the symbol chain and offsets. It
# resolves both the credits mode and the main-menu mode from these functions.
source = (FFNX / "src" / "ff8_data.cpp").read_text(encoding="utf-8")
for statement in (
    "pubintro_main_loop = get_absolute_value(ff8_externals.main_entry, 0x180)",
    "credits_main_loop = get_absolute_value(ff8_externals.pubintro_main_loop, 0x6D)",
    "go_to_main_menu_main_loop = get_absolute_value(ff8_externals.credits_main_loop, 0xE2)",
    "main_menu_enter = get_absolute_value(ff8_externals.go_to_main_menu_main_loop, 0x19)",
    "main_menu_main_loop = get_absolute_value(ff8_externals.go_to_main_menu_main_loop, 0x2B)",
):
    assert statement in source
assert subprocess.check_output(
    ["git", "-C", str(FFNX), "rev-parse", "HEAD"], text=True,
).strip() == EXPECTED_FFNX

assert fast_start.build_hext(False) == ""
patch = fast_start.build_hext(True)
assert f"{fast_start.CREDITS_COMPLETION_CALL:X} = B8 01 00 00 00" in patch
for retired in ("47040D =", "470415 =", "47041D ="):
    assert retired not in patch
for invalid in (0, 1, "true", None):
    try:
        fast_start.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Fast Start accepted {invalid!r}")

print("FF8 Fast Start static contract passed")
