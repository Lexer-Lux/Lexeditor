"""One mod requiring other mods, for every game.

A mod's `mod.json` may list the mods it needs::

    {"name": "My Tweak", "requires": ["base-tweak"]}

A mod's id is its `mod.json` `id`, or its folder name when it has none; a
requirement names that id, exactly as written. A tweak mod may instead (or
additionally) name tweak mods in its settings schema's `requires`, which
`needs` folds in, so every check below sees one list.

Checks refuse with a plain sentence naming who needs whom:

- switching a mod on or off in the Mods tab (`check_changes`),
- saving switches from a Tweaks page (`check_changes`),
- building, as a backstop for whatever the switches missed (`check_enabled`).

`unmet_lines` phrases the same facts as Mods tab flags, one line per need,
so a mod that lost its requirement still says so instead of failing later.
"""
from __future__ import annotations

from pathlib import Path

from core import mod_metadata


def mod_id(folder: Path) -> str:
    """This mod's id: its mod.json `id`, or its folder name."""
    stored = mod_metadata._stored(Path(folder))
    return str(stored.get("id") or Path(folder).name)


def display_name(folder: Path) -> str:
    """This mod's name for messages: its name, or its folder name."""
    stored = mod_metadata._stored(Path(folder))
    name = stored.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else Path(folder).name


def declared(folder: Path) -> list[str]:
    """The mod ids this mod's own mod.json requires, validated."""
    stored = mod_metadata._stored(Path(folder))
    if "requires" not in stored:
        return []
    requires = stored["requires"]
    if (not isinstance(requires, list) or len(requires) > 256
            or not all(isinstance(item, str) and 0 < len(item) <= 128 for item in requires)):
        raise ValueError(f"{display_name(folder)}: requires must list mod ids")
    return [item for item in requires if item != mod_id(folder)]


def needs(folder: Path, schema: dict | None = None) -> list[str]:
    """Every mod id this mod needs: its mod.json plus its tweak schema.

    A tweak whose schema cannot be read contributes no schema needs; the
    build still reports the broken schema itself.
    """
    folder = Path(folder)
    wanted = list(declared(folder))
    if schema is None:
        try:
            from core import script_mods
            schema = script_mods.schema(folder)
        except (OSError, ValueError):
            schema = {}
    for need in (schema or {}).get("requires", []):
        if isinstance(need, str) and need and need != mod_id(folder) and need not in wanted:
            wanted.append(need)
    return wanted


def _stored_mods(library: Path):
    """Readable mod declarations; discovery never runs component or script code."""
    root = Path(library)
    if not root.is_dir():
        return
    for folder in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            stored = mod_metadata._stored(folder)
        except (OSError, ValueError):
            continue
        yield folder, stored


def _states(library: Path) -> tuple[dict[str, bool], dict[str, str], dict[str, Path]]:
    """The library's mods by id: whether each is on, its name, its folder.

    Two mods sharing an id count as on when either is: ids are matched, not
    owned, so a duplicate never reads as missing.
    """
    enabled: dict[str, bool] = {}
    names: dict[str, str] = {}
    folders: dict[str, Path] = {}
    for folder, stored in _stored_mods(library):
        mod = str(stored.get("id") or folder.name)
        enabled[mod] = enabled.get(mod, False) or stored.get("enabled") is True
        names.setdefault(mod, display_name(folder))
        folders.setdefault(mod, folder)
    return enabled, names, folders


def _describe(needs: list[str], enabled: dict[str, bool]) -> str:
    """One need as "id, which is switched off/not installed", or several."""
    if len(needs) == 1:
        need = needs[0]
        return f"{need}, which is {'switched off' if need in enabled else 'not installed'}"
    parts = [f"{need} ({'switched off' if need in enabled else 'not installed'})" for need in needs]
    return " and ".join(parts)


def check_changes(library: Path, changes: dict[str, bool]) -> None:
    """Refuse switches that would leave a changed mod's needs unmet.

    Only the switched mods are judged, against the library as it would be
    afterwards: switching on needs every need installed and on, and
    switching off needs no still-on mod asking for it. Anything else already
    broken stays flaggable, but never jams an unrelated switch.
    """
    library = Path(library)
    if not isinstance(changes, dict):
        raise ValueError("Switches must map mod ids to on or off")
    enabled, names, folders = _states(library)
    planned = dict(enabled)
    for mod, on in changes.items():
        if type(on) is not bool:
            raise ValueError(f"{names.get(mod, mod)} must be on or off")
        planned[mod] = on
    for folder in folders.values():
        mod = mod_id(folder)
        if mod not in changes:
            continue
        if changes[mod]:
            missing = [need for need in needs(folder) if not planned.get(need, False)]
            if missing:
                raise ValueError(f"{display_name(folder)} requires {_describe(missing, enabled)}")
        else:
            dependents = sorted({other for other in folders
                                 if planned.get(other, False) and mod in needs(folders[other])})
            if dependents:
                who = " and ".join(names.get(other, other) for other in dependents)
                verb = "requires" if len(dependents) == 1 else "require"
                raise ValueError(f"{who} {verb} {display_name(folder)}. "
                                 f"Switch {who} off first.")


def check_enabled(library: Path) -> None:
    """Refuse to build while any switched-on mod's needs are unmet."""
    enabled, _, _ = _states(library)
    for folder, stored in _stored_mods(library):
        if stored.get('enabled') is not True:
            continue
        from core.mod_builds import ModBuildError
        try:
            missing = [need for need in needs(folder) if not enabled.get(need, False)]
        except (OSError, ValueError) as error:
            raise ModBuildError([folder], str(error)) from error
        if missing:
            raise ModBuildError([folder], f"{display_name(folder)} requires {_describe(missing, enabled)}")


def unmet_lines(library: Path) -> dict[str, list[str]]:
    """Each switched-on mod's unmet needs as flag lines, by mod folder.

    A mod whose own requires list is not valid says that instead; an
    unreadable mod stays the Mods tab's error row, not a flag.
    """
    lines: dict[str, list[str]] = {}
    root = Path(library)
    if not root.is_dir():
        return lines
    enabled, _, _ = _states(root)
    for folder in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            stored = mod_metadata._stored(folder)
        except (OSError, ValueError):
            continue
        if stored.get("enabled") is not True:
            continue
        try:
            wanted = needs(folder)
        except ValueError:
            lines[str(folder.resolve())] = ["Its list of required mods is not valid."]
            continue
        missing = [need for need in wanted if not enabled.get(need, False)]
        if missing:
            lines[str(folder.resolve())] = [
                f"Requires {need}, which is {'switched off' if need in enabled else 'not installed'}."
                for need in missing]
    return lines


def table(library: Path) -> dict[str, dict]:
    """Each mod folder's needs with their library state, by resolved folder.

    One entry per need: its id, the installed mod's name ("" when nothing
    by that id is installed), and whether it is installed and switched on.
    A mod whose own requires list is not valid reports that instead, under
    "error"; an unreadable mod is absent, and the Mods tab shows that row
    from its own error state.
    """
    root = Path(library)
    if not root.is_dir():
        return {}
    enabled, names, _ = _states(root)
    out: dict[str, dict] = {}
    for folder in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        try:
            wanted = needs(folder)
        except ValueError:
            out[str(folder.resolve())] = {
                "needs": [], "error": "Its list of required mods is not valid."}
            continue
        except OSError:
            continue
        out[str(folder.resolve())] = {
            "needs": [{"id": need, "name": names.get(need, ""),
                       "installed": need in enabled,
                       "enabled": bool(enabled.get(need, False))}
                      for need in wanted],
            "error": ""}
    return out
