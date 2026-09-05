"""Static contract for FF8 Modern Controls, GitHub issue #65."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings, modern_controls_issue_65 as controls  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def executable_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)
for address, original in (
    (controls.CAMERA_YAW_HOOK, controls.CAMERA_YAW_HOOK_ORIGINAL),
    (controls.REJECTED_NORMAL_INPUT_FIELD, controls.REJECTED_NORMAL_INPUT_ORIGINAL),
    (controls.REJECTED_SPECIAL_MODE_READ, controls.REJECTED_SPECIAL_MODE_ORIGINAL),
):
    assert executable_bytes(pe, address, len(original)) == original

assert controls.MODERN_CONTROLS_AVAILABLE is True
assert controls.MODERN_CONTROLS_BLOCKER == ""
assert controls.build_hext(False) == ""
assert controls.build_hext(True).startswith("# Modern Controls uses the FFNx")
assert " = " not in controls.build_hext(True)

source = Path(controls.__file__).read_text(encoding="utf-8")
for rejected in (
    "CODE_CAVE =",
    "def build_code_cave",
    "def analog_camera_delta",
    "0F B6 15 A0 09 04 02",
    "66 01 0D 02 ED 03 02",
    "88 56 0E",
):
    assert rejected not in source

for invalid in (0, 1, "true", None):
    try:
        controls.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Modern Controls accepted {invalid!r}")

print("FF8 Modern Controls native-runtime contract passed")
