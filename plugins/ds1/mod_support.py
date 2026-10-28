"""Hand DS1 mods from the shared library to the DS1 mod loader.

Switching a mod on or off in the Mods tab applies the new set at once, the
same way the editor's Apply does: tweak mods are composed onto the original
executable (tweak_mods.py), and data mods are combined over the game's own
parameter, item-name, map and character files (mod_loader.py), all under
one lock and with the executable put back if the data files cannot be
written.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

from core import memory_conflicts, mod_requires, script_mods
from core.mod_conflicts import MAX_LISTED

from . import assets, deployment, mod_loader, texts, tweak_mods
from .store import MARKER, RELATIVE

MARKER_TEXT = (Path(__file__).with_name("project-template") / MARKER).read_bytes()
DATA_FILES = {RELATIVE.as_posix().casefold(), texts.RELATIVE.as_posix().casefold(), texts.MENU_RELATIVE.as_posix().casefold()}
MAP_PREFIX = "map/mapstudio/"


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
    context: dict[str, str] = {}

    REPORT_VERSION = 1
    REPORT_LIMIT = 2 * 1024 * 1024

    @staticmethod
    def _report_path() -> Path:
        from core.runtime_bootstrap import user_data_dir
        return user_data_dir() / "cache/ds1/mod-conflicts.json"

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
                    or assets.is_character_file(path)):
                packages.append(path.as_posix())
            else:
                ignored.append(path.as_posix())
        problems = [] if packages or tweak else [
            f"This folder has no Dark Souls Remastered mod files. A data mod keeps "
            f"{RELATIVE.as_posix()}, {texts.RELATIVE.as_posix()}, {texts.MENU_RELATIVE.as_posix()} "
            f"and/or map and character files; a tweak mod has a script."]
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

    def _cache_root(self):
        try:
            return self._report_path().parent
        except Exception:
            return None

    def activate(self, mods: list[Path], game_root: Path) -> dict:
        """Install exactly the chosen set: tweaks and data mods together."""
        game_root = Path(game_root)
        library = self._library()
        tweak_mods.ensure_game_closed()
        with tweak_mods.locked(game_root):
            plan = tweak_mods.prepare(game_root, library, cache_root=self._cache_root())
            ordered = self._ordered_mods(mods)
            try:
                content = self._content_signature(ordered)
            except Exception:
                content = None
            report = self._read_report(game_root, ordered)
            if report and report.get("installedOrder") == [str(folder.resolve()) for _name, folder in ordered]:
                # Native settings can change while every data input and
                # installed data file stays the same. Keep that deployment.
                tweak_mods.commit(game_root, plan)
                conflicts = [mod_loader.Conflict(Path(file), part, names)
                             for file, part, names in report["conflicts"]]
                self._save_report(game_root, ordered, conflicts, installed=True, expected_content=content)
                return {"activated": [Path(path).name for path in mods],
                        "dataMods": [name for name, _folder in ordered],
                        "conflicts": len(conflicts)}
            data = self._mods(mods)
            composition = mod_loader.compose_installed(game_root, data, cache_root=self._cache_root())
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
        # The build already compared these records. Publish that report for
        # both the host's Mods tab and selector, including after a restart.
        self._save_report(game_root, ordered, composition.conflicts, installed=True, expected_content=content)
        return {"activated": [Path(path).name for path in mods],
                "dataMods": [mod.name for mod in data],
                "conflicts": len(composition.conflicts)}

    def active_mod_ids(self, game_root: Path) -> list[str]:
        from core import mods_service
        return [Path(row["path"]).name for row in mods_service.library_rows(self._library()) if row["enabled"]]

    def _ordered_mods(self, mods):
        from core import mods_service
        wanted = {Path(path).resolve() for path in mods}
        return [(row["name"], Path(row["path"])) for row in mods_service.library_rows(self._library())
                if Path(row["path"]).resolve() in wanted and (Path(row["path"]) / MARKER).is_file()]

    def conflicts(self, mods: list[Path], game_root: Path) -> dict[str, list[str]]:
        """Each switched-on mod's clashes with another one, by mod folder.

        Data clashes come from composing the archives; memory clashes from
        each tweak mod's already-built native patches, read without building
        or enabling anything. A mod carrying a native binary is skipped for
        memory: its addresses are unknowable without running it, so its
        schema's declared conflicts still guard it at enable time.

        The build publishes its record-conflict report. Reuse it while mod
        files and game originals have the same size and write/change times.
        Reordering only re-sorts the reported owners; it does not re-merge.
        """
        game_root = str(Path(game_root).resolve())
        ordered = self._ordered_mods(mods)
        if len(ordered) < 2:
            return _merge_marks({}, self._memory_conflicts(mods))
        data_lines = self._load_report(Path(game_root), ordered)
        if data_lines is not None:
            return _merge_marks(data_lines, self._memory_conflicts(mods))
        try:
            compared_key = self._report_key(Path(game_root), ordered)
        except OSError:
            compared_key = None
        data = self._mods(mods)
        composition = mod_loader.compose_installed(Path(game_root), data, conflicts_only=True)
        data_lines = composition.by_mod(data)
        if compared_key is not None:
            self._save_report(Path(game_root), ordered, composition.conflicts, expected_key=compared_key)
        return _merge_marks(data_lines, self._memory_conflicts(mods))

    @classmethod
    def _content_signature(cls, ordered):
        return sorted((str(folder.resolve()), name, cls._content_stamp(folder, name))
                      for name, folder in ordered)

    @classmethod
    def _report_key(cls, game_root: Path, ordered) -> str:
        content = cls._content_signature(ordered)
        originals = []
        for relative in sorted({key for _folder, _name, stamped in content for key, *_stat in stamped}):
            path = Path(relative)
            for source in (game_root / path, deployment._backup_path(game_root, path),
                           deployment._marker_path(game_root, path)):
                try:
                    stat = source.stat()
                    originals.append((str(source), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
                except FileNotFoundError:
                    originals.append((str(source), None))
        encoded = json.dumps([cls.REPORT_VERSION, str(game_root.resolve()), content, originals],
                             sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _read_report(self, game_root, ordered):
        try:
            path = self._report_path()
            if path.stat().st_size > self.REPORT_LIMIT:
                return None
            report = json.loads(path.read_text(encoding="utf-8"))
            if report.get("key") != self._report_key(game_root, ordered):
                return None
            cached = report["conflicts"]
            if not isinstance(cached, list) or any(
                    not isinstance(row, list) or len(row) != 3
                    or not isinstance(row[0], str) or not isinstance(row[1], str)
                    or not isinstance(row[2], list) or any(not isinstance(name, str) for name in row[2])
                    for row in cached):
                return None
            return report
        except Exception:
            return None

    def _load_report(self, game_root, ordered):
        report = self._read_report(game_root, ordered)
        if report is None:
            return None
        return self._lines_for_order([(Path(file), part, names) for file, part, names in report["conflicts"]], ordered)

    def _save_report(self, game_root, ordered, conflicts, *, installed=False,
                     expected_key=None, expected_content=None):
        from core.plugin_files import atomic_write
        try:
            key = self._report_key(game_root, ordered)
            if expected_key is not None and key != expected_key:
                return
            if expected_content is not None and self._content_signature(ordered) != expected_content:
                return
            report = {"key": key,
                      "conflicts": [[str(row.file), row.part, list(row.mods)] for row in conflicts]}
            if installed:
                report["installedOrder"] = [str(folder.resolve()) for _name, folder in ordered]
            encoded = json.dumps(report).encode("utf-8")
            if len(encoded) > self.REPORT_LIMIT:
                return
            path = self._report_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, encoded)
        except Exception:
            pass  # A derived report must never turn a successful build into a failure.

    @staticmethod
    def _content_stamp(folder: Path, name: str) -> tuple:
        """What a mod holds, cheaply: names, sizes and change times.

        mod.json is not content: reordering rewrites every mod's order key,
        which must not look like a changed mod.
        """
        stamped = []
        for key, path in mod_loader.content_files(folder, name):
            stat = path.stat()
            stamped.append((str(key), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
        return tuple(sorted(stamped))

    @staticmethod
    def _lines_for_order(cached, ordered) -> dict[str, list[str]] | None:
        """Cached conflict parts said in this load order, or None to recompute."""
        rank = {name: index for index, (name, _) in enumerate(ordered)}
        conflicts = []
        for file, part, names in cached:
            if any(name not in rank for name in names):
                return None
            conflicts.append(mod_loader.Conflict(file, part, sorted(names, key=rank.__getitem__)))
        # by_mod only reads names and folders, never file bytes.
        shims = [mod_loader.Mod(name, folder, {}) for name, folder in ordered]
        return mod_loader.Composition({}, conflicts).by_mod(shims)

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
    #: What they show on an executable-patch mod while the loader mod is off:
    #: its last-built native patches cannot install until the loader is on.
    ALERT_NEEDS_LOADER = "Requires Lexeditor Loader, which is switched off."
    ALERT_LOADER_MISSING = "Requires Lexeditor Loader, which is not installed."

    def alerts(self, mods: list[Path], game_root: Path) -> dict[str, list[str]]:
        """Each given mod that changed since the last build, that patches the
        executable while the loader is off, or whose required mods are not
        installed and on, by folder, on or off."""
        wanted = {Path(path).resolve() for path in mods}
        try:
            stale = set(tweak_mods.needs_rebuild(Path(game_root), self._library()).get("stale", []))
            rows = tweak_mods.tweak_rows(self._library()) if stale else []
        except (ValueError, OSError, RuntimeError):
            rows, stale = [], set()
        lines = {str(Path(row["path"]).resolve()): [self.ALERT_CHANGED] for row in rows
                 if row["id"] in stale and Path(row["path"]).resolve() in wanted}
        try:
            pending = mod_requires.unmet_lines(self._library())
        except (ValueError, OSError, RuntimeError):
            pending = {}
        for folder, need_lines in pending.items():
            if Path(folder) in wanted:
                lines.setdefault(folder, []).extend(need_lines)
        installed, enabled = tweak_mods.loader_mod_state(self._library())
        if not enabled:
            try:
                rows = tweak_mods.tweak_rows(self._library())
            except (ValueError, OSError, RuntimeError):
                rows = []
            line = self.ALERT_LOADER_MISSING if not installed else self.ALERT_NEEDS_LOADER
            for row in rows:
                folder = Path(row["path"])
                if folder.resolve() in wanted and any(
                        tweak_mods.native_spans(folder, row["name"]).values()):
                    lines.setdefault(str(folder.resolve()), []).append(line)
        for folder in sorted(wanted):
            if self._changes_code(folder, Path(game_root)):
                lines.setdefault(str(folder), []).append(self.ALERT_OFFLINE)
        return lines

    def describe_changes(self, folder, game_root):
        """One mod's changed records and loaded files, for its detail panel.

        The records are the mod's parameter rows and text entries against
        the game's own files; without the game installed there is nothing
        to compare, but the loaded files (what the loader reads from the
        folder) never needed it.
        """
        loaded = mod_loader.loaded_files(Path(folder))
        if game_root is None:
            return {'changes': [], 'loaded': loaded, 'truncated': False,
                    'note': 'Locate the game to compare records against vanilla.'}
        result = mod_loader.describe_changes(Path(folder), Path(game_root))
        result['loaded'] = loaded
        return result

    #: On every mod that changes the game's code: the loader then blocks the
    #: network, so FromSoftware's anti-cheat never sees a patched game.
    ALERT_OFFLINE = ("Online play is off while this mod is on: it changes the game's code, "
                     "which may trigger anti-cheat.")

    @staticmethod
    def _changes_code(folder: Path, game_root: Path) -> bool:
        """A tweak mod's native patches, or a project's saved native rules.

        Parameters, text, maps, characters and other assets replace data
        and leave the game online.
        """
        try:
            if script_mods.is_script_mod(folder):
                return tweak_mods.changes_code(folder)
            if not (folder / MARKER).is_file():
                return False
            from .native_rules import NativeRules
            return NativeRules(game_root, folder).changes_code()
        except (OSError, ValueError, PermissionError):
            return False  # Unreadable metadata is the Mods tab's error row, not a mark.

    def launch_notice(self, game_root: Path) -> str:
        """The toast Play shows: why the game starts offline, or ""."""
        return tweak_mods.offline_reason(Path(game_root))
