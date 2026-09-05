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
        seen: set[str] = set()
        rows = []
        for root in candidates:
            key = os.path.normcase(str(root))
            if key in seen:
                continue
            seen.add(key)
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
            payload[plugin_id] = {"current": str(root), "known": known}
            self._write(payload)
        return self.snapshot(plugin_id)

    def create(self, plugin_id: str, parent_value: str, name: str) -> dict:
        _plugin, spec = self._spec(plugin_id)
        clean_name = name.strip()
        if not clean_name or clean_name in {".", ".."} or any(char in clean_name for char in '<>:"/\\|?*'):
            raise ValueError("Enter a valid folder name")
        parent = Path(parent_value).expanduser().resolve()
        if not parent.is_dir():
            raise ValueError(f"Parent folder does not exist: {parent}")
        target = parent / clean_name
        if target.exists():
            raise ValueError(f"A file or folder already exists: {target}")
        shutil.copytree(
            spec.template_root, target,
            ignore=lambda _root, names: [name for name in names if name in IGNORED_NAMES],
        )
        if spec.initialize is not None:
            spec.initialize(target)
        return self.select(plugin_id, str(target))

    def rename(self, plugin_id: str, root_value: str, name: str) -> dict:
        """Rename one known project folder and keep its selection stable."""
        _plugin, spec = self._spec(plugin_id)
        root = Path(root_value).expanduser().resolve()
        problems = self._problems(root, spec.required_paths, spec.required_any)
        if problems:
            raise ValueError("\n".join(problems))
        clean_name = name.strip()
        if not clean_name or clean_name in {".", ".."} or any(char in clean_name for char in '<>:"/\\|?*'):
            raise ValueError("Enter a valid folder name")
        target = root.with_name(clean_name)
        if target.exists():
            raise ValueError(f"A file or folder already exists: {target}")
        root.rename(target)
        with self._lock:
            payload = self._read()
            entry = payload.get(plugin_id, {}) if isinstance(payload.get(plugin_id), dict) else {}
            current = Path(entry.get("current") or spec.default_root).expanduser().resolve()
            known = [str(target) if os.path.normcase(str(Path(value).expanduser().resolve())) == os.path.normcase(str(root)) else value
                     for value in entry.get("known", []) if isinstance(value, str)]
            if os.path.normcase(str(current)) == os.path.normcase(str(root)):
                current = target
            payload[plugin_id] = {"current": str(current), "known": known}
            self._write(payload)
        return self.snapshot(plugin_id)
