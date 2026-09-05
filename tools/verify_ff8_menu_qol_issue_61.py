"""Issue-local contract for FF8 menu quality-of-life issue #61."""

from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import inventory_auto_sort  # noqa: E402
from games.ff8 import menu_qol_issue_61 as source  # noqa: E402


INSTALLED = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")
FFNX_SAVE_DATA = ROOT / "_scratch" / "ffnx-upstream" / "src" / "ff8" / "save_data.h"
FFNX_DATA = ROOT / "_scratch" / "ffnx-upstream" / "src" / "ff8_data.cpp"


def _read_va(path: Path, address: int, length: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(address - 0x00400000)
        return stream.read(length)


def _call_target(source_address: int, call: bytes) -> int:
    assert len(call) == 5 and call[:1] == b"\xE8"
    return source_address + 5 + struct.unpack("<i", call[1:])[0]


def _jump_target(source_address: int, jump: bytes) -> int:
    assert len(jump) == 5 and jump[:1] == b"\xE9"
    return source_address + 5 + struct.unpack("<i", jump[1:])[0]


def _expect_blocked(builder, blocker: str) -> None:
    assert builder(False) == ""
    try:
        builder(True)
    except RuntimeError as error:
        assert str(error) == blocker
    else:
        raise AssertionError("an unresolved option emitted a patch")


def main() -> int:
    assert INSTALLED.is_file(), "the supported installed FF8 executable is missing"
    assert hashlib.sha256(INSTALLED.read_bytes()).hexdigest() == source.SUPPORTED_EXE_SHA256

    assert _read_va(
        INSTALLED, source.MAGIC_SORT_RESOURCE_LOAD,
        len(source.MAGIC_SORT_RESOURCE_LOAD_ORIGINAL),
    ) == source.MAGIC_SORT_RESOURCE_LOAD_ORIGINAL
    hook = _read_va(INSTALLED, source.MAGIC_OPEN_HOOK, len(source.MAGIC_OPEN_HOOK_ORIGINAL))
    assert hook == source.MAGIC_OPEN_HOOK_ORIGINAL
    assert _call_target(source.MAGIC_OPEN_HOOK, hook) == source.MAGIC_OPEN_DISPLACED_CALL
    assert _read_va(
        INSTALLED, source.NATIVE_MAGIC_SORT, len(source.NATIVE_MAGIC_SORT_PREFIX),
    ) == source.NATIVE_MAGIC_SORT_PREFIX
    rearrange = _read_va(
        INSTALLED, source.MAGIC_REARRANGE_CALL_SITE,
        len(source.MAGIC_REARRANGE_CALL_ORIGINAL),
    )
    assert rearrange == source.MAGIC_REARRANGE_CALL_ORIGINAL
    native_call_at = source.MAGIC_REARRANGE_CALL_SITE + 11
    assert _call_target(native_call_at, rearrange[11:16]) == source.NATIVE_MAGIC_SORT

    ffnx_data = FFNX_DATA.read_text(encoding="utf-8")
    assert "ff8_externals.menu_callbacks = (ff8_menu_callback *)" in ffnx_data
    save_data = FFNX_SAVE_DATA.read_text(encoding="utf-8")
    assert "uint32_t played_time_secs;" in save_data
    assert "uint8_t battle_order[32];" in save_data
    assert "savemap_ff8_item items[198];" in save_data

    payload = source.build_auto_sort_magic_code_cave()
    assert len(payload) == source.AUTO_SORT_MAGIC_CAVE_LENGTH
    assert payload == source.build_auto_sort_magic_code_cave()
    assert _call_target(source.AUTO_SORT_MAGIC_CAVE, payload[:5]) == source.MAGIC_OPEN_DISPLACED_CALL
    native_call_offset = payload.index(b"\xE8", 5)
    assert _call_target(
        source.AUTO_SORT_MAGIC_CAVE + native_call_offset,
        payload[native_call_offset:native_call_offset + 5],
    ) == source.NATIVE_MAGIC_SORT
    assert bytes((0x6A, source.ATTACK_RESTORE_INDIRECT_MODE, 0x53)) in payload
    assert bytes.fromhex("83 FB 08") in payload, "all eight character magic lists must sort"
    assert payload.endswith(bytes.fromhex("61 9D C3"))
    assert source.AUTO_SORT_MAGIC_CAVE >= (
        inventory_auto_sort.CODE_CAVE + inventory_auto_sort.CODE_CAVE_LENGTH
    )

    assert _read_va(
        INSTALLED, source.ABILITY_LIST_RETURN_HOOK,
        len(source.ABILITY_LIST_RETURN_ORIGINAL),
    ) == source.ABILITY_LIST_RETURN_ORIGINAL
    learned = bytes((7, 0xFF, source.ABILITY_COMPLETE, 1, 20, 20, 0, 0))
    available_a = bytes((3, 4, source.ABILITY_AVAILABLE, 1, 40, 12, 0, 0))
    available_b = bytes((9, 8, source.ABILITY_AVAILABLE, 2, 100, 5, 0, 0))
    learned_b = bytes((12, 0xFF, source.ABILITY_COMPLETE, 3, 200, 200, 0, 0))
    ordered = source.stable_ability_order([
        learned, available_a, learned_b, available_b,
    ])
    # Category first, so FF8's own groups survive; unfinished before completed
    # inside each group; alphabetical by ability name inside each of those.
    assert ordered == [available_a, learned, available_b, learned_b], ordered
    ranks = source.ability_rank_table()
    same_group = [
        bytes((identifier, 0, source.ABILITY_AVAILABLE, 1, 0, 0, 0, 0))
        for identifier in (4, 2, 1, 3)
    ]
    by_name = source.stable_ability_order(same_group)
    assert [record[0] for record in by_name] == sorted(
        (4, 2, 1, 3), key=lambda identifier: ranks[identifier]), by_name
    assert all(record in ordered for record in (learned, available_a, learned_b, available_b))
    try:
        source.stable_ability_order([b"short"])
    except ValueError:
        pass
    else:
        raise AssertionError("Enhanced Ability ordering accepted a partial record")

    ability_payload = source.build_enhanced_ability_order_code_cave()
    assert len(ability_payload) == source.ENHANCED_ABILITY_ORDER_CAVE_LENGTH
    assert bytes.fromhex("8B B4 24 50 01 00 00") in ability_payload
    # The cave no longer compares states directly; it builds one sort key per
    # record from category, completion and the alphabetical rank table.
    assert bytes((0x0F, 0xB6, 0x47, source.ABILITY_CATEGORY_OFFSET)) in ability_payload
    assert bytes((0x0F, 0xB6, 0x57, source.ABILITY_STATE_OFFSET)) in ability_payload
    assert bytes((0x0F, 0xB6, 0x57, source.ABILITY_ID_OFFSET)) in ability_payload
    assert bytes.fromhex("8B 07 8B 57 04 87 47 08 87 57 0C 89 07 89 57 04") in ability_payload
    ranks = source.ability_rank_table()
    assert len(ranks) == 256 and ability_payload.endswith(ranks)
    table_address = source.ENHANCED_ABILITY_ALPHA_CAVE + len(ability_payload) - len(ranks)
    assert bytes.fromhex("8A 92") + table_address.to_bytes(4, "little") in ability_payload
    jump = source.relative_branch(
        bytes((0xE9,)),
        source.ENHANCED_ABILITY_ALPHA_CAVE + ability_payload.index(bytes((0xE9,)) ) ,
        source.ABILITY_LIST_RETURN,
    )
    assert jump in ability_payload
    ability_fragment = source.build_enhanced_ability_order_hext()
    assert f"{source.ABILITY_LIST_RETURN_HOOK:X} = E9" in ability_fragment
    assert f"{source.ENHANCED_ABILITY_ALPHA_CAVE:X}:{len(ability_payload):X}" in ability_fragment

    assert _read_va(
        INSTALLED, source.ABILITY_STATE_READ,
        len(source.ABILITY_STATE_READ_ORIGINAL),
    ) == source.ABILITY_STATE_READ_ORIGINAL
    assert _read_va(
        INSTALLED, source.ABILITY_PALETTE_HOOK,
        len(source.ABILITY_PALETTE_HOOK_ORIGINAL),
    ) == source.ABILITY_PALETTE_HOOK_ORIGINAL
    renderer_call = _read_va(
        INSTALLED, source.ABILITY_TEXT_RENDER_CALL,
        len(source.ABILITY_TEXT_RENDER_CALL_ORIGINAL),
    )
    assert renderer_call == source.ABILITY_TEXT_RENDER_CALL_ORIGINAL
    assert _call_target(source.ABILITY_TEXT_RENDER_CALL, renderer_call) == source.ABILITY_TEXT_RENDERER
    assert source.ability_palette_for_state(source.ABILITY_AVAILABLE) == 7
    assert source.ability_palette_for_state(source.ABILITY_COMPLETE) == 1
    try:
        source.ability_palette_for_state(0)
    except ValueError:
        pass
    else:
        raise AssertionError("Enhanced Ability palette accepted an unknown semantic state")
    palette_payload = source.build_enhanced_ability_palette_code_cave()
    assert len(palette_payload) == source.ENHANCED_ABILITY_PALETTE_CAVE_LENGTH
    assert palette_payload.startswith(bytes.fromhex("F7 D3 83 E3 06 52 50"))
    assert _jump_target(
        source.ENHANCED_ABILITY_PALETTE_CAVE + len(palette_payload) - 5,
        palette_payload[-5:],
    ) == source.ABILITY_PALETTE_RETURN
    palette_fragment = source.build_enhanced_ability_palette_hext()
    assert f"{source.ABILITY_PALETTE_HOOK:X} = E9" in palette_fragment
    assert f"{source.ENHANCED_ABILITY_PALETTE_CAVE:X}:{len(palette_payload):X}" in palette_fragment

    fragment = source.build_auto_sort_magic_hext(True)
    expected_hook = source.relative_branch(
        b"\xE8", source.MAGIC_OPEN_HOOK, source.AUTO_SORT_MAGIC_CAVE,
    ).hex(" ").upper()
    assert f"{source.MAGIC_OPEN_HOOK:X} = {expected_hook}" in fragment
    assert f"{source.AUTO_SORT_MAGIC_CAVE:X}:{len(payload):X}" in fragment
    assert f"{source.AUTO_SORT_MAGIC_CAVE:X} = {payload.hex(' ').upper()}" in fragment
    assert source.build_auto_sort_magic_hext(False) == ""

    enhanced_fragment = source.build_enhanced_ability_menu_hext(True)
    assert ability_fragment in enhanced_fragment
    assert palette_fragment in enhanced_fragment
    assert source.build_enhanced_ability_menu_hext(False) == ""
    _expect_blocked(source.build_ingame_time_hext, source.INGAME_TIME_BLOCKER)
    _expect_blocked(source.build_battle_item_auto_sort_hext, source.BATTLE_ITEM_AUTO_SORT_BLOCKER)
    assert source.build_hext() == ""
    assert source.build_hext(auto_sort_magic=True) == fragment
    assert source.build_hext(enhanced_ability_menu=True) == enhanced_fragment

    for name in (
        "build_auto_sort_magic_hext",
        "build_enhanced_ability_menu_hext",
        "build_ingame_time_hext",
        "build_battle_item_auto_sort_hext",
    ):
        builder = getattr(source, name)
        try:
            builder(1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{name} accepted a non-boolean setting")

    print("FF8 menu quality-of-life issue #61 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
