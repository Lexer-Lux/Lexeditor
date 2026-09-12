"""Persistent editable-mod projects shared by all game plugins."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import threading

from plugin_api import GamePlugin


ROOT = Path(os.environ.get("LOCALAPPDATA", Path(__file__).resolve().parent / "out")) / "Lexeditor"
DEFAULT_PATH = ROOT / "projects.json"
IGNORED_NAMES = {".git", ".pytest_cache", "__pycache__", "out"}
_INVALID_FOLDER_CHARS = '<>:"/\\|?*'
_WINDOWS_RESERVED_STEMS = {
    "con", "prn", "aux", "nul", "clock$", "conin$", "conout$",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
    "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³",
}


def _project_folder_name(name: str) -> str:
    """Return a portable Windows-safe project folder name or reject it."""
    clean_name = str(name).strip()
    stem = clean_name.split(".", 1)[0].rstrip(" .").casefold()
    invalid = (
        not clean_name
        or clean_name in {".", ".."}
        or clean_name.endswith(".")
        or any(char in clean_name for char in _INVALID_FOLDER_CHARS)
        or any(ord(char) < 32 for char in clean_name)
        or stem in _WINDOWS_RESERVED_STEMS
    )
    if invalid:
        raise ValueError("Enter a valid folder name")
    return clean_name


class ProjectManager:
    """Validate, remember, and clone editable projects without touching games."""

    def __init__(self, plugins: dict[str, GamePlugin], path: Path | None = None) -> None:
        self.plugins = plugins
        self.path = Path(path or DEFAULT_PATH)
        self._lock = threading.RLock()

    def _spec(self, plugin_id: str):
        plugin = self.plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        if plugin.projects is None:
            raise ValueError(f"{plugin.name} does not define an editable project")
        return plugin, plugin.projects

    def _read(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temporary.unlink(missing_ok=True)
        except OSError as error:
            raise RuntimeError(f"Cannot safely clear project registry helper: {temporary}") from error
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def _problems(root: Path, required_paths: tuple[str, ...],
                  required_any: tuple[tuple[str, ...], ...] = ()) -> list[str]:
        """Report what a root is missing, allowing alternative shapes.

        A game can have more than one kind of editable thing. Warband has
        Module System source projects and compiled installed modules, so a
        root is valid when it satisfies any one of the listed groups.
        """
        groups = required_any or (required_paths,)
        failures = []
        for group in groups:
            missing = [f"{root} is missing {relative}"
                       for relative in group if not (root / relative).exists()]
            if not missing:
                return []
            failures.append(missing)
        return min(failures, key=len) if failures else []

    def snapshot(self, plugin_id: str) -> dict:
        plugin, spec = self._spec(plugin_id)
        with self._lock:
            payload = self._read()
        entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
        current = Path(entry.get("current") or spec.default_root).expanduser().resolve()
        candidates = [current, spec.default_root.resolve()]
        # A discovered root is often a junction into the game folder, and
        # resolving it renames it to the link target. Keep the name the player
        # actually sees in that folder.
        display_names: dict[str, str] = {}
        if spec.discover:
            try:
                for found in spec.discover():
                    found = Path(found).expanduser()
                    resolved = found.resolve()
                    display_names.setdefault(os.path.normcase(str(resolved)), found.name)
                    candidates.append(resolved)
            except Exception:
                pass  # discovery is a convenience, never a hard failure
        candidates.extend(Path(value).expanduser().resolve() for value in entry.get("known", [])
                          if isinstance(value, str) and value)
        # A removed mod must stay removed. Discovery would otherwise hand the
        # same folder back on the next snapshot, so removal is recorded rather
        # than merely dropped from the known list.
        forgotten = {os.path.normcase(str(Path(value).expanduser().resolve()))
                     for value in entry.get("forgotten", []) if isinstance(value, str) and value}
        seen: set[str] = set()
        rows = []
        for root in candidates:
            key = os.path.normcase(str(root))
            if key in seen:
                continue
            seen.add(key)
            if key in forgotten and key != os.path.normcase(str(current)):
                continue
            problems = self._problems(root, spec.required_paths, spec.required_any)
            rows.append({"path": str(root), "name": display_names.get(key) or root.name or plugin.name,
                         "valid": not problems, "problems": problems,
                         "current": key == os.path.normcase(str(current))})
        return {"pluginId": plugin_id, "current": str(current),
                "environment": spec.root_env, "projects": rows,
                "canCreate": spec.template_root.is_dir()}

    def select(self, plugin_id: str, root_value: str) -> dict:
        _plugin, spec = self._spec(plugin_id)
        root = Path(root_value).expanduser().resolve()
        problems = self._problems(root, spec.required_paths, spec.required_any)
        if problems:
            raise ValueError("\n".join(problems))
        with self._lock:
            payload = self._read()
            entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
            known = [value for value in entry.get("known", []) if isinstance(value, str)]
            if os.path.normcase(str(root)) not in {os.path.normcase(value) for value in known}:
                known.append(str(root))
            # Choosing a folder again undoes an earlier removal.
            forgotten = [value for value in entry.get("forgotten", [])
                         if isinstance(value, str)
                         and os.path.normcase(str(Path(value).expanduser().resolve()))
                         != os.path.normcase(str(root))]
            payload[plugin_id] = {"current": str(root), "known": known,
                                  "forgotten": forgotten}
            self._write(payload)
        return self.snapshot(plugin_id)

    def create(self, plugin_id: str, parent_value: str, name: str) -> dict:
        _plugin, spec = self._spec(plugin_id)
        clean_name = _project_folder_name(name)
        parent = Path(parent_value).expanduser().resolve()
        if not parent.is_dir():
            raise ValueError(f"Parent folder does not exist: {parent}")
        target = parent / clean_name
        if target.exists():
            raise ValueError(f"A file or folder already exists: {target}")
        try:
            shutil.copytree(
                spec.template_root, target,
                ignore=lambda _root, names: [name for name in names if name in IGNORED_NAMES],
            )
            if spec.initialize is not None:
                spec.initialize(target)
            return self.select(plugin_id, str(target))
        except Exception as error:
            if target.exists():
                try:
                    shutil.rmtree(target)
                except Exception as cleanup_error:
                    raise RuntimeError(
                        f"Project creation failed and the new folder could not be cleaned up: {cleanup_error}"
                    ) from error
            raise

    def rename(self, plugin_id: str, root_value: str, name: str) -> dict:
        """Rename one known project folder and keep its selection stable."""
        _plugin, spec = self._spec(plugin_id)
        root = Path(root_value).expanduser().resolve()
        problems = self._problems(root, spec.required_paths, spec.required_any)
        if problems:
            raise ValueError("\n".join(problems))
        clean_name = _project_folder_name(name)
        target = root.with_name(clean_name)
        if target.exists():
            raise ValueError(f"A file or folder already exists: {target}")
        root.rename(target)
        try:
            with self._lock:
                payload = self._read()
                entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
                current = Path(entry.get("current") or spec.default_root).expanduser().resolve()
                known = [str(target) if os.path.normcase(str(Path(value).expanduser().resolve())) == os.path.normcase(str(root)) else value
                         for value in entry.get("known", []) if isinstance(value, str)]
                if os.path.normcase(str(current)) == os.path.normcase(str(root)):
                    current = target
                payload[plugin_id] = {"current": str(current), "known": known,
                                      "forgotten": entry.get("forgotten", [])}
                self._write(payload)
        except Exception as error:
            try:
                if target.exists() and not root.exists():
                    target.rename(root)
            except Exception as rollback_error:
                raise RuntimeError(
                    f"Project rename failed and the original folder could not be restored: {rollback_error}"
                ) from error
            raise
        return self.snapshot(plugin_id)

    def contents(self, plugin_id: str, root_value: str = "") -> dict:
        """Count what this game's loader recognises inside one mod folder.

        Adding a mod used to say nothing about whether the folder made sense,
        so a player found out it had loaded nothing only when the game looked
        unchanged. This walks the folder once and reports, per declared
        category, how many files the loader will pick up - plus how many it
        will ignore, which is the number that explains a mod doing nothing.
        """
        _plugin, spec = self._spec(plugin_id)
        if root_value:
            root = Path(root_value).expanduser().resolve()
        else:
            with self._lock:
                payload = self._read()
            entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
            root = Path(entry.get("current") or spec.default_root).expanduser().resolve()
        categories = [(label, tuple(suffix.lower() for suffix in suffixes))
                      for label, suffixes in (spec.content_types or ())]
        known = {suffix: label for label, suffixes in categories for suffix in suffixes}
        counts = {label: 0 for label, _suffixes in categories}
        unrecognized = 0
        total = 0
        bytes_seen = 0
        if not root.is_dir():
            return {"path": str(root), "exists": False, "declared": bool(categories),
                    "categories": [], "unrecognized": 0, "files": 0, "bytes": 0}
        for folder, folders, files in os.walk(root):
            folders[:] = [name for name in folders if name not in IGNORED_NAMES]
            for name in files:
                total += 1
                try:
                    bytes_seen += os.path.getsize(os.path.join(folder, name))
                except OSError:
                    pass
                label = known.get(Path(name).suffix.lower())
                if label is None:
                    unrecognized += 1
                else:
                    counts[label] += 1
        return {
            "path": str(root),
            "exists": True,
            "declared": bool(categories),
            "categories": [{"label": label, "count": counts[label],
                            "suffixes": list(suffixes)}
                           for label, suffixes in categories],
            "unrecognized": unrecognized,
            "files": total,
            "bytes": bytes_seen,
        }

    def forget(self, plugin_id: str, root_value: str) -> dict:
        """Stop listing one mod. Nothing on disk is touched.

        Lexeditor keeps a list of mod folders, which is not the same thing as
        owning them: a folder may be someone else's mod, or live under the
        game's own directory. Removing an entry therefore only stops Lexeditor
        loading and listing it. Deleting the files stays the player's decision,
        made in their file manager.
        """
        _plugin, spec = self._spec(plugin_id)
        root = Path(root_value).expanduser().resolve()
        key = os.path.normcase(str(root))
        with self._lock:
            payload = self._read()
            entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
            known = [value for value in entry.get("known", [])
                     if isinstance(value, str)
                     and os.path.normcase(str(Path(value).expanduser().resolve())) != key]
            forgotten = [value for value in entry.get("forgotten", []) if isinstance(value, str)]
            if key not in {os.path.normcase(str(Path(value).expanduser().resolve()))
                           for value in forgotten}:
                forgotten.append(str(root))
            current = Path(entry.get("current") or spec.default_root).expanduser().resolve()
            if os.path.normcase(str(current)) == key:
                current = spec.default_root.resolve()
            payload[plugin_id] = {"current": str(current), "known": known,
                                  "forgotten": forgotten}
            self._write(payload)
        return self.snapshot(plugin_id)
