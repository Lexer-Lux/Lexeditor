"""Static contract for FF8 Vibration Consolidation, GitHub issue #66."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import gameplay_settings, vibration_consolidation_issue_66 as vibration  # noqa: E402

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


def branch_target(code: bytes, offset: int, address: int) -> int:
    displacement = int.from_bytes(code[offset + 1:offset + 5], "little", signed=True)
    return address + offset + 5 + displacement


assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)
assert image_bytes(pe, vibration.FIELD_HOOK, 5) == vibration.FIELD_HOOK_ORIGINAL
assert image_bytes(pe, vibration.BATTLE_HOOK, 5) == vibration.BATTLE_HOOK_ORIGINAL
assert vibration.FIELD_HOOK + 5 <= vibration.FIELD_PATCHED_CALL
assert vibration.BATTLE_HOOK + 5 <= vibration.BATTLE_PATCHED_CALL
field = vibration.build_field_cave()
battle = vibration.build_battle_cave()
assert branch_target(field, 0, vibration.FIELD_CAVE) == vibration.FIELD_NATIVE_PREPARE
assert branch_target(field, 10, vibration.FIELD_CAVE) == vibration.FIELD_NATIVE_PAUSE
assert branch_target(field, 15, vibration.FIELD_CAVE) == vibration.FIELD_RETURN
assert battle.startswith(bytes.fromhex("83 C4 28 5F 50 55"))
assert branch_target(battle, 6, vibration.BATTLE_CAVE) == vibration.BATTLE_NATIVE_PAUSE
assert branch_target(battle, 11, vibration.BATTLE_CAVE) == vibration.BATTLE_RETURN
assert vibration.build_hext(False) == ""
patch = vibration.build_hext(True)
assert f"{vibration.FIELD_HOOK:X} = E9" in patch
assert f"{vibration.BATTLE_HOOK:X} = E9" in patch
assert f"{vibration.FIELD_PATCHED_CALL:X} =" not in patch
assert f"{vibration.BATTLE_PATCHED_CALL:X} =" not in patch
for invalid in (0, 1, "true", None):
    try:
        vibration.build_hext(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Vibration Consolidation accepted {invalid!r}")

print("FF8 Vibration Consolidation static contract passed")
