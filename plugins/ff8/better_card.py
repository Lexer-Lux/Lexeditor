"""Verified FF8 Better Card data and shared-dispatcher entry point."""

from __future__ import annotations


DEFAULT_BETTER_CARD = False
BETTER_CARD_AVAILABLE = True
CARD_COMMAND_ID = 25
FIRST_ENEMY_ACTOR = 3
LAST_ENEMY_ACTOR = 6

# Native Card conversion predicate for one battle actor. The first branch
# returns false only when both card result bytes in the raw c0m record are FF.
CARD_PREDICATE = 0x0048FBA0
CARD_PREDICATE_PREFIX = bytes.fromhex(
    "8B 44 24 04 56 57 8D 0C 40 8D 0C 88 C1 E1 04 "
    "8B 91 10 7B D2 01 8B 3A "
    "80 BF F9 00 00 00 FF 75 0E "
    "80 BF FA 00 00 00 FF 75 05 5F 33 C0 5E C3"
)

# These are the shared command-list hooks already owned by Draw Once. Better
# Card needs the same three stages: filter the target mask, disable selection
# when no cardable targets remain, and draw the command as disabled. A second
# independent patch at these addresses would overwrite Draw Once.
TARGET_MASK_HOOK = 0x004BC81A
TARGET_MASK_ORIGINAL = bytes.fromhex("66 8B F8 83 C4 04")
COMMAND_SELECT_HOOK = 0x004BC7B5
COMMAND_SELECT_ORIGINAL = bytes.fromhex("8A 4B 03 83 C4 10 F6 C1 02")
COMMAND_RENDER_HOOK = 0x004BCB3B
COMMAND_RENDER_ORIGINAL = bytes.fromhex("8A 59 03 56 0F BF 70 34")

def enemy_can_be_carded(common_card_id: int, rare_card_id: int) -> bool:
    """Mirror the proven first branch of the native Card predicate."""
    values = (common_card_id, rare_card_id)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("Card IDs must be whole bytes")
    if any(not 0 <= value <= 0xFF for value in values):
        raise ValueError("Card IDs must be from 0 to 255")
    return common_card_id != 0xFF or rare_card_id != 0xFF


def build_hext(*, enabled: bool, draw_once: bool = False) -> str:
    """Build the one shared Card/Draw command-eligibility fragment."""
    if not isinstance(enabled, bool) or not isinstance(draw_once, bool):
        raise ValueError("Better Card and Draw Once must be true or false")
    from . import battle_issue_54
    return battle_issue_54.build_command_eligibility_patch(
        draw_once=draw_once, better_card=enabled,
    )
