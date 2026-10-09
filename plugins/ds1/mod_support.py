"""Hand DS1 mods from the shared library to the DS1 mod loader.

Switching a mod on or off in the Mods tab applies the new set at once, the
same way the editor's Apply does: tweak mods are composed onto the original
executable (tweak_mods.py), and data mods are combined over the game's own
parameter and item-name archives (mod_loader.py), all under one lock and
with the executable put back if the data files cannot be written.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from core import script_mods

from . import deployment, mod_loader, texts, tweak_mods
from .store import MARKER, RELATIVE

MARKER_TEXT = (Path(__file__).with_name("project-template") / MARKER).read_bytes()
DATA_FILES = {RELATIVE.as_posix().casefold(), texts.RELATIVE.as_posix().casefold()}


class Ds1ModAdapter:
    """Import, enable and combine DS1 mods from the shared mod library."""

    verified = True
    message = ("Combines every enabled Dark Souls Remastered mod over the game's own "
               "files: parameters and item names field by field, tweaks onto the "
               "original executable. Close the game before switching mods.")
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
            if path.as_posix().casefold() in DATA_FILES:
                packages.append(path.as_posix())
            else:
                ignored.append(path.as_posix())
        problems = [] if packages or tweak else [
            f"This folder has no Dark Souls Remastered mod files. A data mod keeps "
            f"{RELATIVE.as_posix()} and/or {texts.RELATIVE.as_posix()}; a tweak mod has a script."]
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
        """Each switched-on mod's changes another one overrides, by mod folder."""
        data = self._mods(mods)
        if len(data) < 2:
            return {}
        key = tuple((str(mod.folder), tuple(sorted((str(name), hashlib.sha256(raw).hexdigest())
                                                    for name, raw in mod.files.items()))) for mod in data)
        key += (str(Path(game_root).resolve()),)
        if self._cache and self._cache[0] == key:
            return self._cache[1]
        composition = mod_loader.compose(mod_loader.vanilla_files(Path(game_root)), data)
        result = composition.by_mod(data)
        self._cache = (key, result)
        return result
