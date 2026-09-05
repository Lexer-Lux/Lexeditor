"""Finish FF8's opening credits immediately on the supported executable.

The game still enters and cleans up its native credits mode. The patch changes
only the credits-completion result, so the game's own transition schedules and
initializes the main menu.
"""

from __future__ import annotations


DEFAULT_FAST_START = False

# Supported FF8_EN.exe SHA-256:
# 064d466b5fe2ba901fd44abf19f37c0fd6a2db40aabd95c9e5959195b6589570
#
# The credits loop calls its completion predicate at 0052DADF. When it returns
# nonzero, the unchanged game schedules 00470440 / 0056D970 / 00470520. The
# last function then schedules the proved main-menu callbacks. The retired
# implementation replaced the initial credits callbacks with menu callbacks;
# that skipped required initialization and crashed in the menu renderer.
CREDITS_COMPLETION_CALL = 0x0052DADF
CREDITS_COMPLETION_ORIGINAL = bytes.fromhex("E8 1C 18 00 00")
CREDITS_COMPLETE_TRUE = bytes.fromhex("B8 01 00 00 00")


def build_hext(enabled: bool) -> str:
    """Return the focused Hext fragment, or no patch for vanilla startup."""
    if not isinstance(enabled, bool):
        raise ValueError("Fast Start must be true or false")
    if not enabled:
        return ""
    return "\n".join([
        "# Fast Start: complete the native credits mode immediately.",
        f"{CREDITS_COMPLETION_CALL:X} = {CREDITS_COMPLETE_TRUE.hex(' ').upper()}",
        "",
    ])
