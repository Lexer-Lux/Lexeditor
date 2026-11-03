"""Memory overlaps between mods, found without enabling anything.

File conflicts come from a loader combining files: each game adapter reports
them through core/mod_conflicts.py and the Mods tab marks them. Memory
conflicts used to surface only at enable time, when one tweak's build refused
another enabled tweak's hand-written mod id (core/script_mods.py), or when
the combiner itself rejected two patches at once.

This module finds them statically instead. Each mod's patch address ranges
are parsed from files already in its folder - a Hext patch's `ADDRESS = ...`
lines, or DS1's already-built native descriptions - without running any mod
script. Overlapping ranges become the same generic (part, mods) pairs file
conflicts use, so the Mods tab marks them the same way.

Two readings of an overlap exist. Where the last mod in load order wins
(FF8's ordered Hext stream), the pairs go to lines_by_mod. Where overlapping
mods cannot apply together at all (DS1's native combiner refuses them),
exclusive_lines_by_mod says so from every side: there is no winner.

A mod carrying a native binary (.dll, .asi) is skipped: its addresses are
unknowable without running it, so its conflicts keep coming from its
schema's declared mod ids, checked when it is enabled. Enabling stays the
authority everywhere - settings, floating code and damaged files are all
rechecked then - and anything this module cannot parse is left for it.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.mod_conflicts import MAX_LISTED

#: A mod tree is walked only this far looking for a native binary. Past the
#: cap the search stops and the mod counts as carrying none: enabling still
#: guards it, and any static overlap found is real either way.
MAX_SCAN_ENTRIES = 20000
#: Suffixes of a binary loaded into the game: a plain DLL or an ASI plugin.
NATIVE_SUFFIXES = frozenset({".dll", ".asi"})
_HEX = frozenset("0123456789abcdefABCDEF")


def carries_native_code(folder: Path) -> bool:
    """True when the mod folder holds a native binary, at any depth."""
    entries, stack = 0, [Path(folder)]
    while stack:
        try:
            children = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for child in children:
            entries += 1
            if entries > MAX_SCAN_ENTRIES:
                return False
            try:
                if child.is_dir(follow_symlinks=False):
                    stack.append(Path(child.path))
                elif Path(child.name).suffix.casefold() in NATIVE_SUFFIXES:
                    return True
            except OSError:
                continue
    return False


def hext_ranges(text: str) -> list[tuple[int, int]]:
    """(start, end) of every address a Hext patch writes, end exclusive.

    Only `ADDRESS = BYTE ...` lines count. Blank lines, comments and
    anything else a hand-written patch may hold are skipped, not failed:
    this is the Mods tab's advisory mark, and an unknown line is left for
    the game to load, not guessed at.
    """
    ranges = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[:1] in "#;/" or "=" not in stripped:
            continue
        left, right = stripped.split("=", 1)
        address = left.strip()
        if address[:2].casefold() == "0x":
            address = address[2:].strip()
        if not address or any(char not in _HEX for char in address):
            continue
        for marker in ("#", ";", "/"):
            cut = right.find(marker)
            if cut >= 0:
                right = right[:cut]
        digits = "".join(right.split())
        if not digits or len(digits) % 2 or any(char not in _HEX for char in digits):
            continue
        start = int(address, 16)
        ranges.append((start, start + len(digits) // 2))
    return ranges


def overlaps(spans_by_mod: list[tuple[str, list[tuple[int, int]]]]) -> list[tuple[str, list[str]]]:
    """(part, [earlier, later]) for every address two mods both patch.

    `spans_by_mod` is load order, lowest first, each span (start, end) with
    the end exclusive; the part names their shared bytes, `memory START` for
    one byte or `memory START-END` for a run, inclusive and in hex. A mod
    never conflicts with itself, and the same shared bytes are listed once.
    """
    ordered = [(name, sorted((start, end) for start, end in spans if start < end))
               for name, spans in spans_by_mod]
    found, seen = [], set()
    for index, (earlier, first) in enumerate(ordered):
        for later, second in ordered[index + 1:]:
            if earlier == later:
                continue
            for start_a, end_a in first:
                for start_b, end_b in second:
                    start, end = max(start_a, start_b), min(end_a, end_b)
                    if start >= end:
                        continue
                    part = f"memory {start:X}" if end - start == 1 else f"memory {start:X}-{end - 1:X}"
                    if (part, earlier, later) in seen:
                        continue
                    seen.add((part, earlier, later))
                    found.append((part, [earlier, later]))
    return found


def _names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def exclusive_lines_by_mod(conflicts: list[tuple[str, list[str]]],
                           folders: dict[str, str]) -> dict[str, list[str]]:
    """Each mod's conflict lines where overlaps cannot apply together.

    The same inputs as mod_conflicts.lines_by_mod, but no winner: enabling
    any two of the mods fails, so every side names the others. A mod not in
    `folders` still counts as one of the others, but gets no lines itself.
    """
    result: dict[str, list[str]] = {}
    for part, mods in conflicts:
        unique = list(dict.fromkeys(mods))
        if len(unique) < 2:
            continue
        for name in unique:
            folder = folders.get(name)
            if folder is None:
                continue
            others = [other for other in unique if other != name]
            verb = "patches" if len(others) == 1 else "patch"
            result.setdefault(folder, []).append(
                f"{part}: {_names(others)} {verb} this too; only one of these mods can be on")
    for folder, lines in result.items():
        if len(lines) > MAX_LISTED:
            result[folder] = lines[:MAX_LISTED] + [f"…and {len(lines) - MAX_LISTED} more"]
    return result
