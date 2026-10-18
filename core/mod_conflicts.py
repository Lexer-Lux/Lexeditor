"""What the Mods tab says about changes one mod overrides in another.

A game's mod loader combines what it can. What it cannot combine, it hands
here as conflicts: the part (a file, a table row's field, a name) and the
mods that change it, in load order, so the last one is the one used. Each
mod then gets its own lines, said from its side, for the red mark on its row
in the Mods tab.
"""
from __future__ import annotations

# A row's list stops here; the rest is counted.
MAX_LISTED = 12


def _names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def lines_by_mod(conflicts: list[tuple[str, list[str]]], folders: dict[str, str]) -> dict[str, list[str]]:
    """Each mod's conflict lines, keyed by its folder.

    `conflicts` holds (part, mod names in load order); `folders` maps a mod
    name to its folder. A mod not in `folders` (a project outside the
    library) still counts as one of the others, but gets no lines itself.
    """
    result: dict[str, list[str]] = {}
    for part, mods in conflicts:
        if len(mods) < 2:
            continue
        winner = mods[-1]
        for name in mods:
            folder = folders.get(name)
            if folder is None:
                continue
            if name == winner:
                line = f"{part}: overrides {_names([other for other in mods if other != name])}"
            else:
                line = f"{part}: {winner} changes this too and loads later, so this mod's change is not used"
            result.setdefault(folder, []).append(line)
    for folder, lines in result.items():
        if len(lines) > MAX_LISTED:
            result[folder] = lines[:MAX_LISTED] + [f"…and {len(lines) - MAX_LISTED} more"]
    return result
