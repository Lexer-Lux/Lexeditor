"""Static evidence and fail-closed contract for FF8 Better Card."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import (  # noqa: E402
    battle_issue_54, better_card, gameplay_settings, menu_qol_issue_61,
)

EXE = Path(r"D:\SteamLibrary\steamapps\common\FINAL FANTASY VIII\FF8_EN.exe")


def image_bytes(pe: pefile.PE, address: int, length: int) -> bytes:
    rva = address - pe.OPTIONAL_HEADER.ImageBase
    return pe.get_memory_mapped_image()[rva:rva + length]


assert EXE.is_file()
assert sha256(EXE.read_bytes()).hexdigest() == gameplay_settings.SUPPORTED_EXE_SHA256
pe = pefile.PE(str(EXE), fast_load=True)
assert image_bytes(
    pe, better_card.CARD_PREDICATE, len(better_card.CARD_PREDICATE_PREFIX),
) == better_card.CARD_PREDICATE_PREFIX

assert not better_card.enemy_can_be_carded(0xFF, 0xFF)
assert better_card.enemy_can_be_carded(0, 0xFF)
assert better_card.enemy_can_be_carded(0xFF, 0)
for invalid in ((-1, 0), (0, 256), (True, 0), ("1", 0)):
    try:
        better_card.enemy_can_be_carded(*invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"invalid Card IDs were accepted: {invalid!r}")

for address, original in (
    (better_card.TARGET_MASK_HOOK, better_card.TARGET_MASK_ORIGINAL),
    (better_card.COMMAND_SELECT_HOOK, better_card.COMMAND_SELECT_ORIGINAL),
    (better_card.COMMAND_RENDER_HOOK, better_card.COMMAND_RENDER_ORIGINAL),
):
    assert image_bytes(pe, address, len(original)) == original

# Prove the overlap and require one composed dispatcher, never two independent
# last-writer-wins fragments.
assert better_card.TARGET_MASK_HOOK == battle_issue_54.DRAW_TARGET_MASK_HOOK
assert better_card.COMMAND_SELECT_HOOK == battle_issue_54.DRAW_SELECT_HOOK
assert better_card.COMMAND_RENDER_HOOK == battle_issue_54.DRAW_RENDER_HOOK
assert better_card.BETTER_CARD_AVAILABLE
assert better_card.build_hext(enabled=False) == ""
card_patch = better_card.build_hext(enabled=True)
combined = better_card.build_hext(enabled=True, draw_once=True)
for patch in (card_patch, combined):
    assert patch.count(f"{better_card.TARGET_MASK_HOOK:X} = ") == 1
    assert patch.count(f"{better_card.COMMAND_SELECT_HOOK:X} = ") == 1
    assert patch.count(f"{better_card.COMMAND_RENDER_HOOK:X} = ") == 1
    assert "both FF" in patch
assert f"{battle_issue_54.DRAW_STATE:X}:4" not in card_patch
assert f"{battle_issue_54.DRAW_STATE:X}:4" in combined
assert f"{battle_issue_54.CARD_FILTER_CAVE:X}:" in card_patch
assert battle_issue_54.DRAW_STATE.to_bytes(4, "little").hex(" ").upper() not in card_patch

filter_code = battle_issue_54._card_filter_payload()
assert bytes.fromhex("80 BA F9 00 00 00 FF") in filter_code
assert bytes.fromhex("80 BA FA 00 00 00 FF") in filter_code
assert bytes.fromhex("0F B3 F7") in filter_code  # remove only the invalid actor bit
assert bytes.fromhex("46 83 FE 07") in filter_code  # actors 3 through 6

target_code = battle_issue_54._draw_target_mask_payload(better_card=True)
select_code = battle_issue_54._draw_select_payload(better_card=True)
render_code = battle_issue_54._draw_render_payload(better_card=True)
card_id_check = bytes.fromhex("80 39 19")
assert card_id_check in target_code
assert card_id_check in render_code
assert bytes.fromhex("80 38 19") in select_code
for code in (target_code, select_code, render_code):
    assert battle_issue_54.CARD_FILTER_CAVE.to_bytes(4, "little") not in code
# The render hook must restore EAX before replaying `movsx esi,[eax+0x34]`.
assert bytes.fromhex("80 CB 02 58 56 0F BF 70 34") in render_code

# The new shared helper starts after the highest existing ability-menu payload.
assert (
    menu_qol_issue_61.ENHANCED_ABILITY_ORDER_CAVE
    + menu_qol_issue_61.ENHANCED_ABILITY_ORDER_CAVE_LENGTH
    <= battle_issue_54.CARD_FILTER_CAVE
)

for invalid in (0, 1, "true", None):
    try:
        better_card.build_hext(enabled=invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Better Card accepted {invalid!r}")

print("FF8 Better Card evidence and shared-dispatcher contract passed")
