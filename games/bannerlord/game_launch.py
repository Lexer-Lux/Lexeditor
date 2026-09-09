"""Bannerlord direct-launch support for the selected Lexeditor module.

Bannerlord accepts an explicit module loadout through
``/singleplayer _MODULES_*...*_MODULES_``.  Lexeditor derives that loadout from
SubModule.xml rather than launching an unrelated launcher profile.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import threading

from .module_data import read_submodule


CORE_SINGLEPLAYER_MODULES = (
    "Native",
    "SandBoxCore",
    "CustomBattle",
    "Sandbox",
    "StoryMode",
)


def _module_id(path: Path) -> str:
    metadata = read_submodule(path / "SubModule.xml")
    module_id = str(metadata.get("id") or "").strip()
    if not module_id:
        raise RuntimeError(f"Bannerlord module has no Id in {path / 'SubModule.xml'}")
    return module_id


def installed_modules(game_root: Path) -> dict[str, Path]:
    """Installed Bannerlord modules keyed by their SubModule.xml Id."""
    modules_root = game_root.resolve() / "Modules"
    if not modules_root.is_dir():
        raise RuntimeError(f"Bannerlord Modules folder not found: {modules_root}")
    modules: dict[str, Path] = {}
    for folder in sorted(modules_root.iterdir(), key=lambda value: value.name.casefold()):
        descriptor = folder / "SubModule.xml"
        if not folder.is_dir() or not descriptor.is_file():
            continue
        module_id = _module_id(folder)
        if module_id in modules and modules[module_id].resolve() != folder.resolve():
            raise RuntimeError(
                f"Several installed Bannerlord modules declare Id {module_id}: "
                f"{modules[module_id]} and {folder}"
            )
        modules[module_id] = folder
    return modules


def selected_module(game_root: Path, project: Path) -> tuple[str, Path]:
    """Match a source workspace or installed folder to exactly one installed module."""
    descriptor = project.resolve() / "SubModule.xml"
    if not descriptor.is_file():
        raise RuntimeError("The selected Bannerlord project has no SubModule.xml.")
    project_id = str(read_submodule(descriptor).get("id") or "").strip()
    if not project_id:
        raise RuntimeError("The selected Bannerlord project has no module Id.")
    modules = installed_modules(game_root)
    installed = modules.get(project_id)
    if installed is None:
        raise RuntimeError(
            f"Bannerlord module {project_id} is not installed under this game's Modules folder. "
            "Build/deploy it before Play."
        )
    return project_id, installed


def module_load_order(game_root: Path, project: Path) -> list[str]:
    """Resolve required dependency closure, core SP modules, then the selected mod."""
    selected_id, installed = selected_module(game_root, project)
    modules = installed_modules(game_root)
    metadata_cache: dict[str, dict] = {}
    visiting: set[str] = set()
    added: set[str] = set()
    order: list[str] = []

    def metadata(module_id: str) -> dict:
        if module_id not in metadata_cache:
            folder = modules.get(module_id)
            if folder is None:
                raise RuntimeError(f"Required Bannerlord dependency is not installed: {module_id}")
            metadata_cache[module_id] = read_submodule(folder / "SubModule.xml")
        return metadata_cache[module_id]

    def add(module_id: str) -> None:
        if module_id in added:
            return
        if module_id in visiting:
            raise RuntimeError(f"Bannerlord module dependency cycle includes {module_id}")
        visiting.add(module_id)
        for dependency in metadata(module_id).get("dependencies", []):
            dependency_id = str(dependency.get("id") or "").strip()
            if not dependency_id:
                continue
            if dependency.get("optional") and dependency_id not in modules:
                continue
            add(dependency_id)
        visiting.remove(module_id)
        if module_id not in added:
            added.add(module_id)
            order.append(module_id)

    # Respect the selected module's declared dependency order first.  Then add
    # any standard single-player modules that are installed but were not already
    # reached through dependency metadata.  Finally add the selected module.
    selected_metadata = read_submodule(installed / "SubModule.xml")
    for dependency in selected_metadata.get("dependencies", []):
        dependency_id = str(dependency.get("id") or "").strip()
        if not dependency_id:
            continue
        if dependency.get("optional") and dependency_id not in modules:
            continue
        add(dependency_id)
    for module_id in CORE_SINGLEPLAYER_MODULES:
        if module_id in modules:
            add(module_id)
    add(selected_id)
    return order


def launch_command(game_root: Path, project: Path) -> list[str]:
    game_root = game_root.resolve()
    executable = game_root / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    if not executable.is_file():
        raise RuntimeError(f"Bannerlord.exe not found: {executable}")
    modules = module_load_order(game_root, project)
    module_argument = "_MODULES_*" + "*".join(modules) + "*_MODULES_"
    return [str(executable), "/singleplayer", module_argument]


class BannerlordGameController:
    """Own the Bannerlord process launched for the selected Lexeditor project."""

    def __init__(self, process_factory=subprocess.Popen):
        self._process_factory = process_factory
        self._process = None
        self._module = ""
        self._load_order: list[str] = []
        self._lock = threading.RLock()

    def status(self) -> dict:
        with self._lock:
            running = self._process is not None and self._process.poll() is None
            if not running and self._process is not None:
                self._process = None
            return {
                "running": running,
                "pid": getattr(self._process, "pid", None) if running else None,
                "owned": running,
                "module": self._module if running else "",
                "loadOrder": list(self._load_order) if running else [],
                "processes": ([{"pid": self._process.pid}] if running else []),
            }

    def launch(self, game_root: Path, project: Path) -> dict:
        with self._lock:
            current = self.status()
            if current["running"]:
                return {**current, "alreadyRunning": True}
            module_id, _installed = selected_module(game_root, project)
            command = launch_command(game_root, project)
            load_order = module_load_order(game_root, project)
            cwd = game_root.resolve() / "bin" / "Win64_Shipping_Client"
            process = self._process_factory(command, cwd=str(cwd))
            if process.poll() is not None:
                raise RuntimeError("Bannerlord exited immediately after launch.")
            self._process = process
            self._module = module_id
            self._load_order = load_order
            return {**self.status(), "alreadyRunning": False}

    def stop(self) -> dict:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._process = None
                self._module = ""
                self._load_order = []
                return {"running": False, "stopped": False}
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None
            self._module = ""
            self._load_order = []
            return {"running": False, "stopped": True}
