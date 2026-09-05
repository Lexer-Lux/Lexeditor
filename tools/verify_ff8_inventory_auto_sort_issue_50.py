"""Issue-local contract for FF8's safe inventory auto-sort patch."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import inventory_auto_sort  # noqa: E402
from games.ff8 import single_gf  # noqa: E402


INSTALLED = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX_DATA = ROOT / "_scratch" / "ffnx-upstream" / "src" / "ff8_data.cpp"
FFNX_OPENGL = ROOT / "_scratch" / "ffnx-upstream" / "src" / "ff8_opengl.cpp"


def _read_va(path: Path, address: int, length: int) -> bytes:
    # This supported executable has image base 0x00400000 and its relevant
    # .text bytes have the same RVA-to-file-offset delta.
    with path.open("rb") as stream:
        stream.seek(address - 0x00400000)
        return stream.read(length)


def _call_target(source: int, call: bytes) -> int:
    assert call[:1] == b"\xE8"
    return source + 5 + struct.unpack("<i", call[1:])[0]


def main() -> int:
    source = inventory_auto_sort
    assert INSTALLED.is_file(), "the supported installed FF8 executable is missing"
    assert hashlib.sha256(INSTALLED.read_bytes()).hexdigest() == source.SUPPORTED_EXE_SHA256

    hook = _read_va(INSTALLED, source.ITEM_OPEN_SORT_HOOK, len(source.ITEM_OPEN_SORT_ORIGINAL))
    assert hook == source.ITEM_OPEN_SORT_ORIGINAL
    assert _call_target(source.ITEM_OPEN_SORT_HOOK, hook) == source.ITEM_INITIALIZER

    native = _read_va(INSTALLED, source.NATIVE_SORT_STATE, len(source.NATIVE_SORT_ORIGINAL))
    assert native == source.NATIVE_SORT_ORIGINAL
    assert bytes.fromhex("66 C7 46 10 03 00") in native, "native Sort must return to Item state 3"
    assert bytes.fromhex("8B 7E 20") in native, "native Sort must own the Item inventory pointer"
    assert bytes.fromhex("BB C6 00 00 00") in native, "native Sort must scan all 198 slots"

    ffnx_data = FFNX_DATA.read_text(encoding="utf-8")
    ffnx_opengl = FFNX_OPENGL.read_text(encoding="utf-8")
    assert "menu_callbacks[2].func" in ffnx_data
    assert "menu_use_items_sub_4F81F0" in ffnx_data
    assert "menu_callbacks[2].func + 0x8" in ffnx_opengl

    # Exact native behavior: ignore empty records, let the last duplicate win,
    # compact unique IDs in ascending order, then zero every unused pair.
    source_pairs = [(9, 2), (0, 99), (3, 0), (4, 7), (9, 5), (1, 1)]
    source_pairs.extend([(0, 0)] * (source.INVENTORY_SLOT_COUNT - len(source_pairs)))
    sorted_pairs = source.sort_inventory_pairs(source_pairs)
    assert len(sorted_pairs) == source.INVENTORY_SLOT_COUNT
    assert sorted_pairs[:3] == [(1, 1), (4, 7), (9, 5)]
    assert all(pair == (0, 0) for pair in sorted_pairs[3:])
    assert source.sort_inventory_pairs(sorted_pairs) == sorted_pairs

    payload = source.build_code_cave()
    assert len(payload) == source.CODE_CAVE_LENGTH
    assert payload == source.build_code_cave(), "the patch must be deterministic"
    assert bytes.fromhex("66 C7 46 10 4F 00") not in payload, (
        "the old patch skipped Item startup by forcing controller state 0x4F"
    )
    assert source.relative_call_target(source.CODE_CAVE + len(payload) - 5, payload[-5:]) == source.ITEM_INITIALIZER
    assert payload[-5] == 0xE9, "the wrapper must tail-jump to the original initializer"
    assert bytes.fromhex("8B 7E 20") in payload
    assert bytes.fromhex("BB C6 00 00 00") in payload
    assert source.CODE_CAVE >= single_gf.NORMALIZE_CAVE + single_gf.NORMALIZE_CAVE_LENGTH

    component = source.build_hext(True)
    expected_hook = source.relative_branch(
        b"\xE8", source.ITEM_OPEN_SORT_HOOK, source.CODE_CAVE,
    ).hex(" ").upper()
    assert f"{source.ITEM_OPEN_SORT_HOOK:X} = {expected_hook}" in component
    assert f"{source.CODE_CAVE:X}:{source.CODE_CAVE_LENGTH:X}" in component
    assert f"{source.CODE_CAVE:X} = {payload.hex(' ').upper()}" in component
    assert "66 C7 46 10 4F 00" not in component
    assert "native Item controller" not in component
    assert source.build_hext(False) == ""

    print("FF8 safe inventory auto-sort issue #50 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
