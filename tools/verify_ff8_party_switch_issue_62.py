"""Verify the fail-closed normal-battle party-switch boundary for issue #62."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import struct
import sys

import pefile


ROOT = Path(__file__).resolve().parents[1]
EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX = ROOT / "_scratch" / "ffnx-upstream"
EXPECTED_EXE_SHA256 = "064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570"
EXPECTED_FFNX_REVISION = "1e291885da4ddb482188b81a5198d56a1915fde6"
ENGINE_RANGES = {
    0x00497110: (0xDA, "2f4334faa7baf175d56c9e79a2519ea210c1b074b22c5827da7d5cc4b07c00fc"),
    0x004971F0: (0x78, "c18b6146c108976d65b1197e699742cd8592df366a1d9f1a16dd9cf91b2c6334"),
    0x00497270: (0x21, "c66157f3e5dab29bf63284655a8499c173f1ccdae3c3ddeef7d79574c080d934"),
}


def relative_calls_to(pe: pefile.PE, target: int) -> set[int]:
    section = next(item for item in pe.sections if item.Name.rstrip(b"\0") == b".text")
    image = pe.get_memory_mapped_image()
    start = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
    data = image[section.VirtualAddress:section.VirtualAddress + section.Misc_VirtualSize]
    calls = set()
    for offset in range(len(data) - 4):
        if data[offset] != 0xE8:
            continue
        destination = start + offset + 5 + struct.unpack_from("<i", data, offset + 1)[0]
        if destination == target:
            calls.add(start + offset)
    return calls


def absolute_text_refs(pe: pefile.PE, address: int) -> set[int]:
    section = next(item for item in pe.sections if item.Name.rstrip(b"\0") == b".text")
    image = pe.get_memory_mapped_image()
    start = pe.OPTIONAL_HEADER.ImageBase + section.VirtualAddress
    data = image[section.VirtualAddress:section.VirtualAddress + section.Misc_VirtualSize]
    needle = address.to_bytes(4, "little")
    return {start + offset for offset in range(len(data) - 3)
            if data.startswith(needle, offset)}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    executable = EXE.read_bytes()
    require(hashlib.sha256(executable).hexdigest() == EXPECTED_EXE_SHA256,
            "Unsupported FF8_EN.exe")
    pe = pefile.PE(data=executable, fast_load=True)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    for address, (size, expected) in ENGINE_RANGES.items():
        payload = pe.get_data(address - image_base, size)
        require(hashlib.sha256(payload).hexdigest() == expected,
                f"Reserve-replacement evidence changed at {address:#x}")

    # The only complete three-party builder is battle-startup-owned. The
    # encounter callback is the only other path that rebuilds one participant,
    # and its address is scheduled only from the encounter 0x01FF function.
    require(relative_calls_to(pe, 0x0048B7E0) == {0x0047D5A0},
            "A new caller of the complete battle participant builder exists")
    require(relative_calls_to(pe, 0x0048B8B0) == {
        0x0047DE5F, 0x0047DF47, 0x0047E1DF,
    }, "Battle save-back/teardown caller set changed")
    require(relative_calls_to(pe, 0x00495530) == {
        0x0048B874, 0x00495F05, 0x0049720C,
    }, "Character parser caller set changed")
    require(relative_calls_to(pe, 0x0048B5F0) == {0x0048B889, 0x00497226},
            "Live participant refresh caller set changed")
    require(relative_calls_to(pe, 0x0047DAF0) == {0x00497238},
            "Model replacement caller set changed")
    require(absolute_text_refs(pe, 0x004971F0) == {0x004971CC},
            "Encounter replacement callback gained another producer")

    revision = subprocess.check_output(
        ["git", "-C", str(FFNX), "rev-parse", "HEAD"], text=True,
    ).strip()
    require(revision == EXPECTED_FFNX_REVISION, "Official FFNx revision changed")
    save_source = (FFNX / "src" / "ff8" / "save_data.h").read_text(encoding="utf-8")
    require("uint8_t party[4]; // 0xFF terminated" in save_source,
            "FFNx no longer confirms the saved party array")
    require("savemap_ff8_character chars[CHAR_NUM]" in save_source,
            "FFNx no longer confirms the eight saved characters")

    sys.path.insert(0, str(ROOT))
    from games.ff8 import battle_shortcuts
    from games.ff8 import party_switch_issue_62 as module

    require(module.PARTY_SWITCH_AVAILABLE is True, "Native feature is unavailable")
    require(module.build_hext(enabled=False) == "", "Disabled output changed")
    require("FFNx native extension" in module.build_hext(enabled=True), "Missing native routing")
    require(battle_shortcuts.build_hext(universal_item=False, party_switch=True) == module.build_hext(enabled=True), "Party-only mode emitted shared shortcut caves")
    native_source=(ROOT / "games/ff8/ffnx_party_switch/ffnx-src/lexeditor_ff8_party_switch.cpp").read_text()
    require("VirtualAlloc" in native_source, "Trampoline must own allocated memory")
    for forbidden in ("0x4971F0", "0x497270", "0x1D28E01", "0x1D28E28"):
        require(forbidden not in native_source, "Encounter callback/global reused")

    exists = [True, True, True, True, True, True, False, False]
    blocked = [False, False, False, False, True, False, False, False]
    require(module.eligible_characters(exists, blocked, [0, 1, 2]) == [3, 5],
            "Proved reserve eligibility model changed")

    for invalid in (None, 0, 1, "true", [], {}):
        try:
            module.build_hext(enabled=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Non-boolean setting was accepted: {invalid!r}")

    print("FF8 native party-switch routing and EXE evidence passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
