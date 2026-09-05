"""Persisted game locations, background discovery, and preparation state."""

from __future__ import annotations

import ctypes
import json
import os
import re
import threading
import winreg
from pathlib import Path

from plugin_api import GamePlugin


ROOT = Path(__file__).resolve().parent
LOCAL_DATA = Path(os.environ.get("LOCALAPPDATA", ROOT / "out")) / "Lexeditor"
DEFAULT_CONFIG = LOCAL_DATA / "game-installations.json"
DEFAULT_DATA_ROOT = LOCAL_DATA / "game-data"
STATE_ORDER = {"added": 0, "warning": 1, "broken": 2, "not-added": 3}


class GameInstallationManager:
    """Own the one persistent installation state for every game plugin."""

    def __init__(self, plugins: dict[str, GamePlugin], config_path: Path | None = None,
                 data_root: Path | None = None, auto_scan: bool = True):
        self._plugins = plugins
        self.config_path = Path(config_path or DEFAULT_CONFIG)
        self.data_root = Path(data_root or DEFAULT_DATA_ROOT)
        self._lock = threading.RLock()
        self._generations: dict[str, int] = {plugin_id: 0 for plugin_id in plugins}
        self._states: dict[str, dict] = {}
        self._roots = self._load_roots()
        for plugin_id, plugin in plugins.items():
            root = self._roots.get(plugin_id)
            if plugin.installation is None:
                problems = plugin.check()
                self._states[plugin_id] = self._state(
                    "warning" if problems else "added",
                    "Plugin support files are missing." if problems else "Ready",
                    problems=problems,
                    root=None,
                )
            elif root:
                self._states[plugin_id] = self._state(
                    "added", "Waiting for startup scan…", root=root,
                )
            else:
                self._states[plugin_id] = self._state(
                    "not-added", "Not added to Lexeditor", root=None,
                )
        if auto_scan:
            self.startup_scan()

    @staticmethod
    def _state(status: str, text: str, *, root: str | None,
               problems: list[str] | None = None) -> dict:
        return {
            "status": status,
            "statusText": text,
            "root": root,
            "problems": list(problems or []),
            "scanStatus": "idle",
            "scanInProgress": False,
            "scanCurrent": 0,
            "scanTotal": 0,
            "scanLabel": "",
        }

    def _load_roots(self) -> dict[str, str]:
        if not self.config_path.is_file():
            return {}
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
            games = payload.get("games", {})
            return {
                plugin_id: str(info["root"])
                for plugin_id, info in games.items()
                if plugin_id in self._plugins and isinstance(info, dict) and info.get("root")
            }
        except (OSError, ValueError, TypeError):
            return {}

    def _save_roots(self) -> None:
        payload = {
            "version": 1,
            "games": {
                plugin_id: {"root": root}
                for plugin_id, root in sorted(self._roots.items())
            },
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.config_path)

    def startup_scan(self) -> None:
        """Discover and validate every managed game without blocking startup."""
        for plugin_id, plugin in self._plugins.items():
            if plugin.installation is not None:
                self.begin_scan(plugin_id)

    def _apply_helper(self, plugin_id: str, state: dict) -> dict:
        """Refuse to report a game as ready when its helper is missing."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None or not plugin.helper_status or state["status"] == "not-added":
            return state
        try:
            helper = plugin.helper_status() or {}
        except Exception as error:
            state["problems"] = list(state["problems"]) + [
                f"{plugin.helper_name or 'The runtime helper'} could not be checked: {error}"]
            state["status"] = "broken"
            state["statusText"] = "Broken"
            return state
        state["helper"] = helper
        if helper.get("installed"):
            return state
        name = plugin.helper_name or helper.get("runtime") or "The runtime helper"
        state["problems"] = list(state["problems"]) + [
            f"{name} is not installed. {plugin.name} cannot load edited data without it."]
        state["status"] = "broken"
        state["statusText"] = "Broken"
        return state

    def snapshot(self, plugin_id: str) -> dict:
        with self._lock:
            if plugin_id not in self._states:
                raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
            state = dict(self._states[plugin_id])
            state["problems"] = list(state["problems"])
            state = self._apply_helper(plugin_id, state)
            state["canOpen"] = (
                state["status"] == "added" and not state["scanInProgress"]
                and not state["problems"]
            )
            return state

    def rows(self, bypass: bool = False) -> list[dict]:
        rows = []
        for plugin in self._plugins.values():
            if bypass:
                problems = plugin.check()
                state = self._state(
                    "warning" if problems else "added",
                    "Plugin support files are missing." if problems else "Ready",
                    problems=problems,
                    root=None,
                )
                state = self._apply_helper(plugin.plugin_id, state)
                # Recomputed after the helper check, or a broken game would
                # still report itself as openable.
                state["canOpen"] = state["status"] == "added" and not state["problems"]
            else:
                state = self.snapshot(plugin.plugin_id)
            rows.append({"plugin": plugin, "installation": state})
        rows.sort(key=lambda row: (
            STATE_ORDER[row["installation"]["status"]],
            row["plugin"].name.casefold(),
        ))
        return rows

    def environment(self, plugin_id: str) -> dict[str, str]:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
        spec = plugin.installation
        if spec is None:
            return {}
        state = self.snapshot(plugin_id)
        if not state["canOpen"] or not state["root"]:
            detail = "\n".join(state["problems"]) or state["statusText"]
            raise RuntimeError(detail)
        environment = {spec.root_env: state["root"]}
        if spec.data_env:
            environment[spec.data_env] = str(self.data_root / plugin_id)
        return environment

    def prepare(self, plugin_id: str) -> dict:
        """Prepare editor data on demand after fast installation discovery."""
        plugin = self._plugins.get(plugin_id)
        if plugin is None or plugin.installation is None:
            if plugin is None:
                raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
            return self.snapshot(plugin_id)
        spec = plugin.installation
        if spec.prepare is None:
            return self.snapshot(plugin_id)
        with self._lock:
            current = self._states[plugin_id]
            if current["scanInProgress"]:
                raise RuntimeError(f"{plugin.name} is still being checked")
            root_value = current.get("root")
            if current["status"] != "added" or not root_value or current["problems"]:
                detail = "\n".join(current["problems"]) or current["statusText"]
                raise RuntimeError(detail)
            generation = self._generations[plugin_id] + 1
            self._generations[plugin_id] = generation
            current.update({
                "scanStatus": "preparing",
                "scanInProgress": True,
                "scanCurrent": 0,
                "scanTotal": 0,
                "scanLabel": "Preparing editor data…",
                "statusText": "Preparing editor data…",
            })
        root = Path(root_value).resolve()

        def progress(current: int, total: int, label: str) -> None:
            self._update(
                plugin_id, generation,
                scanCurrent=current,
                scanTotal=total,
                scanLabel=label,
                statusText=label,
            )

        try:
            spec.prepare(root, self.data_root / plugin_id, progress)
        except Exception as error:
            self._update(
                plugin_id, generation,
                status="warning",
                problems=[str(error)],
                scanStatus="error",
                scanInProgress=False,
                scanLabel="",
                statusText="Game data preparation failed.",
            )
            raise
        self._update(
            plugin_id, generation,
            status="added",
            problems=[],
            scanStatus="complete",
            scanInProgress=False,
            scanLabel="",
            statusText="Ready",
        )
        return self.snapshot(plugin_id)

    def begin_scan(self, plugin_id: str) -> dict:
        plugin = self._plugins.get(plugin_id)
        if plugin is None or plugin.installation is None:
            if plugin is None:
                raise ValueError(f"Unknown Lexeditor plugin: {plugin_id}")
            return self.snapshot(plugin_id)
        with self._lock:
            current = self._states[plugin_id]
            if current["scanInProgress"]:
                return self.snapshot(plugin_id)
            generation = self._generations[plugin_id] + 1
            self._generations[plugin_id] = generation
            current.update({
                "scanStatus": "scanning",
                "scanInProgress": True,
                "scanCurrent": 0,
                "scanTotal": 0,
                "scanLabel": "Looking for the game…",
                "statusText": "Scanning for the game…",
            })
            preferred = self._roots.get(plugin_id)
        thread = threading.Thread(
            target=self._scan_worker,
            args=(plugin_id, generation, preferred, None),
            daemon=True,
            name=f"lexeditor-scan-{plugin_id}",
        )
        thread.start()
        return self.snapshot(plugin_id)

    def configure_directory(self, plugin_id: str, root: str | Path) -> dict:
        plugin = self._plugins.get(plugin_id)
        if plugin is None or plugin.installation is None:
            raise ValueError(f"Unknown or unmanaged Lexeditor plugin: {plugin_id}")
        selected = str(Path(root).expanduser().resolve())
        with self._lock:
            generation = self._generations[plugin_id] + 1
            self._generations[plugin_id] = generation
            self._states[plugin_id].update({
                "status": "warning",
                "root": selected,
                "problems": [],
                "scanStatus": "checking",
                "scanInProgress": True,
                "scanCurrent": 0,
                "scanTotal": 0,
                "scanLabel": "Checking the selected folder…",
                "statusText": "Checking the selected folder…",
            })
        thread = threading.Thread(
            target=self._scan_worker,
            args=(plugin_id, generation, selected, selected),
            daemon=True,
            name=f"lexeditor-locate-{plugin_id}",
        )
        thread.start()
        return self.snapshot(plugin_id)

    def _current(self, plugin_id: str, generation: int) -> bool:
        return self._generations.get(plugin_id) == generation

    def _update(self, plugin_id: str, generation: int, **changes) -> bool:
        with self._lock:
            if not self._current(plugin_id, generation):
                return False
            self._states[plugin_id].update(changes)
            return True

    def _validate(self, plugin: GamePlugin, root: Path) -> list[str]:
        spec = plugin.installation
        assert spec is not None
        try:
            if not root.is_dir():
                return [f"The game directory does not exist: {root}"]
            problems = []
            for relative in spec.required_paths:
                target = root / relative
                if not target.exists():
                    problems.append(f"Missing required game file or folder: {relative}")
        except OSError as error:
            return [f"The game directory cannot be read: {root} ({error})"]
        problems.extend(plugin.check())
        return problems

    def _scan_worker(self, plugin_id: str, generation: int,
                     preferred: str | None, manual: str | None) -> None:
        plugin = self._plugins[plugin_id]
        candidates: list[Path] = []
        if preferred:
            candidates.append(Path(preferred))
        if manual is None:
            candidates.extend(self._discover(plugin))
        unique: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(candidate)

        last_problems: list[str] = []
        for index, candidate in enumerate(unique, 1):
            if not self._update(
                plugin_id, generation,
                scanCurrent=index,
                scanTotal=len(unique),
                scanLabel=f"Checking {candidate}",
                statusText="Checking game files…",
            ):
                return
            problems = self._validate(plugin, candidate)
            if not problems:
                self._accept_root(
                    plugin_id, generation, candidate,
                    ready=not (plugin.installation.prepare_on_scan
                               and plugin.installation.prepare is not None),
                )
                if (plugin.installation.prepare_on_scan
                        and plugin.installation.prepare is not None):
                    root = candidate.resolve()

                    def progress(current: int, total: int, label: str) -> None:
                        self._update(
                            plugin_id, generation,
                            scanCurrent=current,
                            scanTotal=total,
                            scanLabel=label,
                            statusText=label,
                        )

                    try:
                        plugin.installation.prepare(
                            root, self.data_root / plugin_id, progress,
                        )
                    except Exception as error:
                        self._update(
                            plugin_id, generation,
                            status="warning",
                            problems=[str(error)],
                            scanStatus="error",
                            scanInProgress=False,
                            scanLabel="",
                            statusText="Game data preparation failed.",
                        )
                        return
                    self._update(
                        plugin_id, generation,
                        status="added",
                        problems=[],
                        scanStatus="complete",
                        scanInProgress=False,
                        scanLabel="",
                        statusText="Ready",
                    )
                return
            last_problems = problems
            if preferred and str(candidate).casefold() == str(preferred).casefold():
                self._update(
                    plugin_id, generation,
                    status="warning",
                    problems=problems,
                    statusText="The saved game directory needs attention. Searching again…",
                )

        had_root = bool(preferred)
        if manual is not None:
            with self._lock:
                if not self._current(plugin_id, generation):
                    return
                self._roots[plugin_id] = str(Path(manual))
                self._save_roots()
        self._update(
            plugin_id, generation,
            status="warning" if had_root or manual is not None else "not-added",
            root=str(Path(preferred or manual).resolve()) if (preferred or manual) else None,
            problems=last_problems or [f"Lexeditor could not find {plugin.name}."],
            scanStatus="not-found",
            scanInProgress=False,
            scanLabel="",
            statusText=(
                "The selected game directory is not usable."
                if manual is not None else
                f"Scan complete. {plugin.name} was not found."
            ),
        )

    def _accept_root(self, plugin_id: str, generation: int, root: Path,
                     *, ready: bool = True) -> None:
        resolved = root.resolve()
        with self._lock:
            if not self._current(plugin_id, generation):
                return
            self._roots[plugin_id] = str(resolved)
            self._save_roots()
        self._update(
            plugin_id, generation,
            status="added" if ready else "warning",
            root=str(resolved),
            problems=[],
            scanStatus="complete" if ready else "preparing",
            scanInProgress=not ready,
            scanLabel="" if ready else "Preparing editor data…",
            statusText="Ready" if ready else "Preparing editor data…",
        )

    @staticmethod
    def _logical_drives() -> list[Path]:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for index in range(26):
            if mask & (1 << index):
                root = f"{chr(65 + index)}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:
                    drives.append(Path(root))
        return drives

    def _discover(self, plugin: GamePlugin) -> list[Path]:
        spec = plugin.installation
        assert spec is not None
        candidates: list[Path] = []
        override = os.environ.get(spec.root_env)
        if override:
            candidates.append(Path(override))
        candidates.extend(self._steam_candidates(spec.steam_app_id, spec.install_dir_names))
        candidates.extend(spec.default_roots)
        candidates.extend(self._uninstall_candidates(plugin.name))
        candidates.extend(self._epic_candidates(plugin.name))
        return candidates

    @staticmethod
    def _steam_candidates(app_id: str, install_names: tuple[str, ...]) -> list[Path]:
        steam_roots: list[Path] = []
        for hive, key_name, value_name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    steam_roots.append(Path(winreg.QueryValueEx(key, value_name)[0]))
            except OSError:
                pass
        libraries: list[Path] = []
        for steam_root in steam_roots:
            libraries.append(steam_root)
            file = steam_root / "steamapps" / "libraryfolders.vdf"
            try:
                text = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            libraries.extend(
                Path(value.replace(r"\\", "\\"))
                for value in re.findall(r'"path"\s+"([^"]+)"', text)
            )
        candidates: list[Path] = []
        for library in libraries:
            manifest = library / "steamapps" / f"appmanifest_{app_id}.acf"
            install_dir = ""
            try:
                text = manifest.read_text(encoding="utf-8", errors="replace")
                match = re.search(r'"installdir"\s+"([^"]+)"', text, re.IGNORECASE)
                install_dir = match.group(1) if match else ""
            except OSError:
                pass
            names = (install_dir,) if install_dir else install_names
            candidates.extend(library / "steamapps" / "common" / name for name in names if name)
        return candidates

    @staticmethod
    def _uninstall_candidates(game_name: str) -> list[Path]:
        candidates = []
        needle = game_name.casefold()
        locations = (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        )
        for hive, key_name in locations:
            try:
                with winreg.OpenKey(hive, key_name) as parent:
                    count = winreg.QueryInfoKey(parent)[0]
                    for index in range(count):
                        try:
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as entry:
                                display = str(winreg.QueryValueEx(entry, "DisplayName")[0])
                                if needle not in display.casefold() and display.casefold() not in needle:
                                    continue
                                location = str(winreg.QueryValueEx(entry, "InstallLocation")[0]).strip()
                                if location:
                                    candidates.append(Path(location))
                        except OSError:
                            continue
            except OSError:
                continue
        return candidates

    @staticmethod
    def _epic_candidates(game_name: str) -> list[Path]:
        root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / (
            "Epic/EpicGamesLauncher/Data/Manifests"
        )
        candidates = []
        if not root.is_dir():
            return candidates
        for manifest in root.glob("*.item"):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            display = str(payload.get("DisplayName", ""))
            location = str(payload.get("InstallLocation", ""))
            if game_name.casefold() in display.casefold() and location:
                candidates.append(Path(location))
        return candidates
