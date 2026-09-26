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

# The two Square Enix cards are not the credits: they are a movie the
# publisher intro starts in its init (0055A140 with movie 4, 0055A530 sets
# 0209A798). The intro loop at 004703B0 keeps playing it while that flag is
# set (004703F9..00470401 JNE 00470436 -> 0055A620) and only then schedules
# the credits. Keep this branch: skipping it abandons a playing movie with
# enable_framelimiter still false. The intro's exit only releases rendering
# objects; it does not stop playback or restore the gameplay timer.
# Replace this intro's update call with stop_movie (0055A5C0). The next loop
# schedules credits normally, after FFNx has restored timing and closed the
# movie handle. Other movies retain their ordinary update calls.
INTRO_MOVIE_BRANCH = 0x00470401
INTRO_MOVIE_BRANCH_ORIGINAL = bytes.fromhex("75 33")
INTRO_MOVIE_UPDATE_CALL = 0x00470436
INTRO_MOVIE_UPDATE_ORIGINAL = bytes.fromhex("E8 E5 A1 0E 00")
INTRO_MOVIE_STOP = bytes.fromhex("E8 85 A1 0E 00")


def build_hext(enabled: bool) -> str:
    """Return the focused Hext fragment, or no patch for vanilla startup."""
    if not isinstance(enabled, bool):
        raise ValueError("Fast Start must be true or false")
    if not enabled:
        return ""
    return "\n".join([
        "# Fast Start: skip the logo movie, then complete the credits immediately.",
        f"{INTRO_MOVIE_BRANCH:X} = {INTRO_MOVIE_BRANCH_ORIGINAL.hex(' ').upper()}",
        f"{INTRO_MOVIE_UPDATE_CALL:X} = {INTRO_MOVIE_STOP.hex(' ').upper()}",
        f"{CREDITS_COMPLETION_CALL:X} = {CREDITS_COMPLETE_TRUE.hex(' ').upper()}",
        "",
    ])
