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

from core import memory_conflicts, script_mods
from core.mod_conflicts import MAX_LISTED

from . import runtime_layout

# Suffixes that describe a mod instead of belonging to the game. Hext patches
# are the one .txt family the composer deploys, so they are handled apart.
IGNORED_SUFFIXES = frozenset({".txt", ".md", ".png", ".jpg", ".jpeg", ".ini", ".json"})
IGNORED_NAMES = frozenset({"mod.json", "mod.xml"})
ROOT_TEXT = "direct/, hext/, textures/, sfx/, voice/, ambient/, override/ or save/"
CHANGE_LIMIT = 1000


def _merge_marks(first: dict[str, list[str]], second: dict[str, list[str]]) -> dict[str, list[str]]:
    """Two folder-to-lines reports as one, capped like lines_by_mod does."""
    merged = {folder: list(lines) for folder, lines in first.items()}
    for folder, lines in second.items():
        merged.setdefault(folder, []).extend(lines)
    for folder, lines in merged.items():
        if len(lines) > MAX_LISTED:
            merged[folder] = lines[:MAX_LISTED] + [f"…and {len(lines) - MAX_LISTED} more"]
    return merged


def _hext_spans(root: Path) -> list[tuple[int, int]] | None:
    """Every address range the mod's Hext patches write, or None when unknowable.

    Only the ``.txt`` patches the composer deploys count. A mod carrying a
    native binary is unknowable without running it, and an unreadable patch
    is left for enable time, so both give None. Variant folders count
    whether or not they are active: an over-marked variant is rechecked when
    the mod is enabled.
    """
    from . import iroj_archive
    if root.is_file():
        try:
            archive = iroj_archive.Archive(root)
        except (OSError, ValueError, iroj_archive.IrojError):
            return None
        members = list(archive.names())
        if any(Path(name).suffix.casefold() in memory_conflicts.NATIVE_SUFFIXES
               for name in members):
            return None
        spans: list[tuple[int, int]] = []
        for name in members:
            parts = name.replace("\\", "/").split("/")
            if len(parts) < 2 or parts[0].casefold() != "hext":
                continue
            if Path(parts[-1]).suffix.casefold() != ".txt":
                continue
            try:
                text = archive.read(name).decode("utf-8-sig")
            except (KeyError, OSError, ValueError, UnicodeError):
                return None
            spans.extend(memory_conflicts.hext_ranges(text))
        return spans
    if memory_conflicts.carries_native_code(root):
        return None
    folder = root / "hext"
    if not folder.is_dir():
        return []
    spans = []
    try:
        patches = sorted((item for item in folder.rglob("*") if item.is_file()),
                         key=lambda item: item.as_posix().casefold())
    except OSError:
        return None
    for patch in patches:
        if patch.suffix.casefold() != ".txt":
            continue
        try:
            text = patch.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            return None
        spans.extend(memory_conflicts.hext_ranges(text))
    return spans


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
        # A tweak mod's script and settings belong to the mod, not the game,
        # and its game files only exist once it has been built.
        tweak = script_mods.is_script_mod(Path(root))
        for path in files:
            top = path.parts[0].casefold() if path.parts else ""
            suffix = path.suffix.casefold()
            if path.name.casefold() in IGNORED_NAMES or (tweak and script_mods.owns(path)):
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
        if not packages and not tweak:
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
        # An enabled tweak mod deploys what its script builds, so build first.
        from . import tweak_mods
        tweak_mods.build_enabled(project, library, Path(game_root), baseline)
        composition = runtime_layout.compose(
            project, runtime, rows, baseline, formats.SECTIONS,
            runtime_layout.prelaunch_condition_state(Path(game_root) / "FFNx.toml"),
        )
        return {"activated": sorted(wanted),
                "mods": [row["id"] for row in rows if row["enabled"]],
                "runtimeRoot": str(runtime), "composition": composition,
                "gameRoot": str(game_root), "libraryRoot": str(library)}

    def conflicts(self, mods: list[Path], game_root: Path) -> dict[str, list[str]]:
        """File and memory clashes between the mods, without enabling anything.

        File clashes come from the last composition: semantic merges and the
        ordered Hext stream combine their mods, so only a file kept whole
        from one mod (the record says what was dropped) counts. Memory
        clashes come from each mod's own Hext patches, read statically: two
        mods patching the same address still load in order, but the earlier
        mod's bytes never take effect, so both sides are marked.
        """
        from core.mod_conflicts import lines_by_mod
        project, library, runtime, _ = self._roots()
        rows = {row["id"]: row for row in runtime_layout.catalog(project, library)}
        wanted = {Path(path).resolve() for path in mods}
        names = {row["id"]: row.get("name") or row["id"] for row in rows.values()}
        folders = {names[key]: str(Path(row["path"]).resolve()) for key, row in rows.items()
                   if Path(row["path"]).resolve() in wanted}
        found = []
        for record in runtime_layout.read(runtime).get("conflicts", []):
            if not isinstance(record, dict) or not record.get("warning"):
                continue
            found.append((str(record.get("path", "")),
                          [names.get(str(claimant), str(claimant)) for claimant in record.get("claimants", [])]))
        return _merge_marks(lines_by_mod(found, folders),
                              self._memory_conflicts(rows, names, folders))

    def _memory_conflicts(self, rows: dict[str, dict], names: dict[str, str],
                          folders: dict[str, str]) -> dict[str, list[str]]:
        """Hext address overlaps between the mods, found without enabling anything.

        The ordered Hext stream lets the last mod win, so the pairs read as
        ordinary last-wins marks. A mod whose patches cannot be parsed, or
        which carries a native binary, is skipped: enabling stays the
        authority for it.
        """
        from core.mod_conflicts import lines_by_mod
        ordered = sorted(rows.values(), key=lambda row: (int(row["order"]),
                                                         str(row.get("name") or row["id"]).casefold()))
        spans = []
        for row in ordered:
            name = names[row["id"]]
            if name not in folders:
                continue
            claimed = _hext_spans(Path(row["path"]).resolve())
            if claimed:
                spans.append((name, claimed))
        if len(spans) < 2:
            return {}
        return lines_by_mod(memory_conflicts.overlaps(spans), folders)

    def describe_changes(self, folder, game_root):
        """One mod's changed records and loaded files, for its detail panel.

        The records are the mod's fixed-record data files against the
        extracted baseline; without extracted game data there is nothing
        to compare, but the loaded files (what the composer deploys
        from the folder) never needed it.
        """
        from . import fixed_data_merge, paths
        folder = Path(folder)
        names = sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*")
                       if path.is_file() and not path.is_symlink())
        loaded = self.inspect(folder, [Path(name) for name in names])["packages"]
        baseline = paths.BASELINE_ROOT
        if not baseline.is_dir():
            return {"changes": [], "loaded": loaded, "truncated": False,
                    "note": "Extract the game's archives to compare records against vanilla."}
        changes, notes = [], []
        for key, spec in fixed_data_merge.SPECS.items():
            mod_file, base_file = folder / key, baseline / spec["baseline"]
            if not mod_file.is_file() or not base_file.is_file():
                continue
            try:
                mine, base = mod_file.read_bytes(), base_file.read_bytes()
            except OSError as error:
                notes.append(f'{key} cannot be read ({error})')
                continue
            try:
                changes += fixed_data_merge.diff(base, mine, spec, spec["baseline"])
            except ValueError as error:
                notes.append(str(error))
        notes.append("Compares fixed-record data files; kernel, archives and media show under Files.")
        truncated = len(changes) > CHANGE_LIMIT
        return {"changes": changes[:CHANGE_LIMIT], "loaded": loaded,
                "truncated": truncated, "note": " ".join(notes)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        """Report the mods of the composed runtime, not the requested ones."""
        _, _, runtime, _ = self._roots()
        rows = runtime_layout.read(runtime).get("mods")
        if not isinstance(rows, list):
            return []
        return [str(row["id"]) for row in rows
                if isinstance(row, dict) and row.get("id")]
