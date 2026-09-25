"""Hand FF8 mods from the shared library to the FF8 mod composer.

The shared mod library and the FF8 composer already use one layout:
``<library>/ff8/<name>/mod.json``, and both use the same source roots under a
mod folder (``direct/``, ``hext/`` and the media roots). This adapter is the
only place the shared library talks to that composer.

Activation changes two things and nothing else: the ``enabled`` flag in each
library mod's own metadata, and Lexeditor's own composed runtime tree. The
game installation is never a write target here. FFNx reads the runtime tree,
so the enabled set is one load order no matter which screen changed it.
"""

from __future__ import annotations

from pathlib import Path

from . import runtime_layout

# Suffixes that describe a mod instead of belonging to the game. Hext patches
# are the one .txt family the composer deploys, so they are handled apart.
IGNORED_SUFFIXES = frozenset({".txt", ".md", ".png", ".jpg", ".jpeg", ".ini", ".json"})
IGNORED_NAMES = frozenset({"mod.json", "mod.xml"})
ROOT_TEXT = "direct/, hext/, textures/, sfx/, voice/, ambient/, override/ or save/"


class Ff8ModAdapter:
    """Import, enable and compose FF8 mods from the shared mod library."""

    # Activation composes into Lexeditor's own runtime tree only, and every
    # destination is inside that owned folder. A separate flag states whether
    # the game itself has been shown to load the result.
    verified = True
    message = ("Imports FF8 mod folders and ZIPs, keeps one load order, and "
               "composes the enabled mods into Lexeditor's own FF8 runtime "
               "tree. Activation never writes into the game installation.")
    package_types = ("folder", "zip")

    # The host owns two paths that the plugin's defaults cannot know: the
    # selected editable project, and the mod library, which a reader can move.
    context: dict[str, str] = {}

    def attach_context(self, *, project_root=None, library_root=None,
                       game_root=None) -> None:
        """Record the paths only the host knows before an adapter call."""
        values = {"projectRoot": project_root, "libraryRoot": library_root,
                  "gameRoot": game_root}
        self.context = {key: str(value) for key, value in values.items() if value}

    def _roots(self) -> tuple[Path, Path, Path, Path]:
        from . import paths
        project = Path(self.context.get("projectRoot") or paths.PROJECT_ROOT)
        library = Path(self.context.get("libraryRoot") or paths.MODS_ROOT)
        return project, library, paths.RUNTIME_ROOT, paths.BASELINE_ROOT

    def inspect(self, root: Path, files: list[Path]) -> dict:
        """Accept one FF8 mod folder and name every file it cannot deploy."""
        problems: list[str] = []
        packages: list[str] = []
        ignored: list[str] = []
        for path in files:
            top = path.parts[0].casefold() if path.parts else ""
            suffix = path.suffix.casefold()
            if path.name.casefold() in IGNORED_NAMES:
                ignored.append(path.as_posix())
                continue
            if top not in runtime_layout.SOURCE_FOLDERS:
                problems.append(
                    f"{path.as_posix()} is not an FF8 mod file. An FF8 mod keeps "
                    f"game files under {ROOT_TEXT}.")
                continue
            if top == "hext":
                # The composer deploys only Hext .txt patches. A file the game
                # cannot load stays in the library and is reported, not refused.
                if suffix == ".txt":
                    packages.append(path.as_posix())
                else:
                    ignored.append(path.as_posix())
                continue
            if suffix in IGNORED_SUFFIXES:
                ignored.append(path.as_posix())
                continue
            packages.append(path.as_posix())
        if not packages:
            problems.append(
                f"This folder has no FF8 game files. An FF8 mod keeps game files "
                f"under {ROOT_TEXT}.")
        return {"valid": not problems, "problems": problems,
                "packages": sorted(set(packages)), "assets": {},
                "notDeployed": sorted(set(ignored))}

    def prepare_editable(self, root: Path) -> None:
        """An editable FF8 mod is its own source tree; make its root explicit."""
        (Path(root) / "direct").mkdir(parents=True, exist_ok=True)

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        """Enable the chosen library mods and compose the runtime in one step."""
        from . import formats, paths
        project, library, runtime, baseline = self._roots()
        wanted = {Path(path).name for path in mods}
        rows = runtime_layout.catalog(project, library)
        for row in rows:
            # The library addresses a mod by its folder name. Its own metadata
            # may carry a different id, so match the folder.
            folder = Path(row["path"]).name
            row["enabled"] = bool(row.get("selected")) or folder in wanted
        order = [row["id"] for row in sorted(
            rows, key=lambda row: (int(row["order"]), row["name"].casefold()))]
        rows = runtime_layout.configure(
            project, library, order, {row["id"]: row["enabled"] for row in rows})
        composition = runtime_layout.compose(
            project, runtime, rows, baseline, formats.SECTIONS,
            runtime_layout.prelaunch_condition_state(Path(game_root) / "FFNx.toml"),
        )
        return {"activated": sorted(wanted),
                "mods": [row["id"] for row in rows if row["enabled"]],
                "runtimeRoot": str(runtime), "composition": composition,
                "gameRoot": str(game_root), "libraryRoot": str(library)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        """Report the mods of the composed runtime, not the requested ones."""
        _, _, runtime, _ = self._roots()
        rows = runtime_layout.read(runtime).get("mods")
        if not isinstance(rows, list):
            return []
        return [str(row["id"]) for row in rows
                if isinstance(row, dict) and row.get("id")]
