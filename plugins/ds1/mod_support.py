"""Hand DS1 mods from the shared library to the DS1 mod loader.

Switching a mod on or off in the Mods tab applies the new set at once, the
same way the editor's Apply does: tweak mods are composed onto the original
executable (tweak_mods.py), and data mods are combined over the game's own
parameter, item-name, map and character files (mod_loader.py), all under
one lock and with the executable put back if the data files cannot be
written.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from core import memory_conflicts, script_mods
from core.mod_conflicts import MAX_LISTED

from . import deployment, mod_loader, texts, tweak_mods
from .store import MARKER, RELATIVE

MARKER_TEXT = (Path(__file__).with_name("project-template") / MARKER).read_bytes()
DATA_FILES = {RELATIVE.as_posix().casefold(), texts.RELATIVE.as_posix().casefold()}
MAP_PREFIX = "map/mapstudio/"
CHR_PREFIX = "chr/"


def _merge_marks(first: dict[str, list[str]], second: dict[str, list[str]]) -> dict[str, list[str]]:
    """Two folder-to-lines reports as one, capped like lines_by_mod does.

    Neither input is changed: one of them may be the adapter's cached data
    report, reused across calls.
    """
    merged = {folder: list(lines) for folder, lines in first.items()}
    for folder, lines in second.items():
        merged.setdefault(folder, []).extend(lines)
    for folder, lines in merged.items():
        if len(lines) > MAX_LISTED:
            merged[folder] = lines[:MAX_LISTED] + [f"…and {len(lines) - MAX_LISTED} more"]
    return merged


class Ds1ModAdapter:
    """Import, enable and combine DS1 mods from the shared mod library."""

    verified = True
    message = ("Switch mods on or off for the installed game. Switching on "
               "installs the enabled mods over the game's own files; "
               "switching everything off puts the originals back. "
               "Close the game before switching.")
    package_types = ("folder", "zip")
    # Steam starts the game; Play installs the enabled mods first, rebuilt.
    deploys_on_launch = True
    context: dict[str, str] = {}

    def __init__(self):
        self._cache: tuple[tuple, dict] | None = None

    def attach_context(self, *, project_root=None, library_root=None, game_root=None) -> None:
        values = {"projectRoot": project_root, "libraryRoot": library_root, "gameRoot": game_root}
        self.context = {key: str(value) for key, value in values.items() if value}

    def _library(self) -> Path:
        return Path(self.context.get("libraryRoot") or tweak_mods.mods_root())

    def inspect(self, root: Path, files: list[Path]) -> dict:
        """Accept a DS1 data mod (its archives) or a tweak mod (its script)."""
        tweak = script_mods.is_script_mod(Path(root))
        packages, ignored = [], []
        for path in files:
            folded = path.as_posix().casefold()
            if (folded in DATA_FILES or (folded.startswith(MAP_PREFIX) and folded.endswith(".msb"))
                    or (folded.startswith(CHR_PREFIX) and folded.endswith(".anibnd.dcx"))):
                packages.append(path.as_posix())
            else:
                ignored.append(path.as_posix())
        problems = [] if packages or tweak else [
            f"This folder has no Dark Souls Remastered mod files. A data mod keeps "
            f"{RELATIVE.as_posix()}, {texts.RELATIVE.as_posix()} and/or map and character files; "
            f"a tweak mod has a script."]
        return {"valid": not problems, "problems": problems, "packages": sorted(packages),
                "assets": {}, "notDeployed": sorted(ignored)}

    def prepare_editable(self, root: Path) -> None:
        """A new DS1 mod is a project folder: give it the project marker."""
        marker = Path(root) / MARKER
        if not marker.exists():
            marker.write_bytes(MARKER_TEXT)

    def _mods(self, paths: list[Path]) -> list[mod_loader.Mod]:
        from core import mods_service
        wanted = {Path(path).resolve() for path in paths}
        mods = []
        for row in mods_service.library_rows(self._library()):
            if Path(row["path"]).resolve() in wanted:
                mod = mod_loader.read_mod(Path(row["path"]), row["name"])
                if mod is not None:
                    mods.append(mod)
        return mods

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        """Install exactly the chosen set: tweaks and data mods together."""
        game_root = Path(game_root)
        library = self._library()
        tweak_mods.ensure_game_closed()
        data = self._mods(mods)
        with tweak_mods.locked(game_root):
            plan = tweak_mods.prepare(game_root, library)
            composition = mod_loader.compose(mod_loader.vanilla_files(game_root), data)
            tweak_mods.commit(game_root, plan)
            try:
                if composition.files:
                    # The last data mod in load order owns the deployment record.
                    deployment.apply(game_root, data[-1].folder, composed=composition.files)
                elif any(deployment.status(game_root, None).get(key) for key in ("enabled", "everApplied")):
                    deployment.disable(game_root)
            except Exception:
                tweak_mods.rollback(game_root, plan)
                raise
        self._cache = None
        return {"activated": [Path(path).name for path in mods],
                "dataMods": [mod.name for mod in data],
                "conflicts": len(composition.conflicts)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        from core import mods_service
        return [Path(row["path"]).name for row in mods_service.library_rows(self._library()) if row["enabled"]]

    def conflicts(self, mods: list[Path], game_root: Path) -> dict[str, list[str]]:
        """Each switched-on mod's clashes with another one, by mod folder.

        Data clashes come from composing the archives; memory clashes from
        each tweak mod's already-built native patches, read without building
        or enabling anything. A mod carrying a native binary is skipped for
        memory: its addresses are unknowable without running it, so its
        schema's declared conflicts still guard it at enable time.
        """
        data = self._mods(mods)
        data_lines: dict[str, list[str]] = {}
        if len(data) >= 2:
            key = tuple((str(mod.folder), tuple(sorted((str(name), hashlib.sha256(raw).hexdigest())
                                                        for name, raw in mod.files.items()))) for mod in data)
            key += (str(Path(game_root).resolve()),)
            if self._cache and self._cache[0] == key:
                data_lines = self._cache[1]
            else:
                composition = mod_loader.compose(mod_loader.vanilla_files(Path(game_root)), data)
                data_lines = composition.by_mod(data)
                self._cache = (key, data_lines)
        return _merge_marks(data_lines, self._memory_conflicts(mods))

    def _memory_conflicts(self, mods: list[Path]) -> dict[str, list[str]]:
        """Overlapping native addresses between switched-on mods, by folder.

        Hooks, kept state and fixed islands are each compared only with
        their own kind, the way the combiner refuses them; floating code is
        placed at compose time and stays its check.
        """
        from core import mods_service
        wanted = {Path(path).resolve() for path in mods}
        rows = [row for row in mods_service.library_rows(self._library())
                if Path(row["path"]).resolve() in wanted]
        if len(rows) < 2:
            return {}
        per_mod = []
        for row in rows:
            folder = Path(row["path"])
            try:
                tweak = script_mods.is_script_mod(folder)
            except (OSError, ValueError):
                continue  # Unreadable metadata is the Mods tab's error row, not a mark.
            # Only a tweak mod's built patches are ever composed; a stray
            # native/ folder in a data mod is dead weight, never applied.
            if not tweak or memory_conflicts.carries_native_code(folder):
                continue
            claimed = tweak_mods.native_spans(folder, row["name"])
            if any(claimed.values()):
                per_mod.append((row["name"], claimed))
        if len(per_mod) < 2:
            return {}
        pairs = []
        for kind in ("hooks", "state", "islands"):
            pairs += memory_conflicts.overlaps([(name, claimed[kind]) for name, claimed in per_mod])
        folders = {row["name"]: str(Path(row["path"]).resolve()) for row in rows}
        return memory_conflicts.exclusive_lines_by_mod(pairs, folders)

    #: What the Mods tab and the mod selector show on a tweak mod that changed
    #: since the tweaks were last built. One line; the mark lists every flag.
    ALERT_CHANGED = "This mod changed since the last build."

    def alerts(self, mods: list[Path], game_root: Path) -> dict[str, list[str]]:
        """Each switched-on tweak mod that changed since the last build, by folder."""
        wanted = {Path(path).resolve() for path in mods}
        try:
            stale = set(tweak_mods.needs_rebuild(Path(game_root), self._library()).get("stale", []))
            rows = tweak_mods.tweak_rows(self._library()) if stale else []
        except (ValueError, OSError, RuntimeError):
            return {}
        return {str(Path(row["path"]).resolve()): [self.ALERT_CHANGED] for row in rows
                if row["id"] in stale and Path(row["path"]).resolve() in wanted}
