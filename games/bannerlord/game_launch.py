"""Bannerlord direct-launch support for the selected Lexeditor module.

Bannerlord accepts an explicit module loadout through
``/singleplayer _MODULES_*...*_MODULES_``. Lexeditor derives that loadout from
SubModule.xml relations rather than launching an unrelated launcher profile.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import threading

from .module_data import is_singleplayer_module, read_submodule


CORE_SINGLEPLAYER_MODULES = (
    "Native",
    "SandBoxCore",
    "BirthAndDeath",
    "CustomBattle",
    "Sandbox",
    "StoryMode",
    "NavalDLC",
)


def _module_id(path: Path) -> str:
    metadata = read_submodule(path / "SubModule.xml")
    module_id = str(metadata.get("id") or "").strip()
    if not module_id:
        raise RuntimeError(f"Bannerlord module has no Id in {path / 'SubModule.xml'}")
    return module_id


def _selected_project_descriptor(project: Path) -> Path:
    root = project.resolve()
    descriptor = (root / "SubModule.xml").resolve()
    if root not in descriptor.parents:
        raise RuntimeError("Resolved selected Bannerlord project SubModule.xml path escaped the project folder")
    if not descriptor.is_file():
        raise RuntimeError("The selected Bannerlord project has no SubModule.xml.")
    return descriptor


def _selected_project_id(project: Path) -> str:
    descriptor = _selected_project_descriptor(project)
    project_id = str(read_submodule(descriptor).get("id") or "").strip()
    if not project_id:
        raise RuntimeError("The selected Bannerlord project has no module Id.")
    return project_id


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


def _selected_module_from_index(project: Path, modules: dict[str, Path]) -> tuple[str, Path]:
    project_id = _selected_project_id(project)
    installed = modules.get(project_id)
    if installed is None:
        raise RuntimeError(
            f"Bannerlord module {project_id} is not installed under this game's Modules folder. "
            "Build/deploy it before Play."
        )
    return project_id, installed


def selected_module(game_root: Path, project: Path) -> tuple[str, Path]:
    """Match a source workspace or installed folder to exactly one installed module."""
    return _selected_module_from_index(project, installed_modules(game_root))


def module_load_order(game_root: Path, project: Path) -> list[str]:
    """Resolve the enabled module set and topologically sort Bannerlord relations.

    Non-optional ``DependedModule`` entries are enabled recursively. Optional
    dependencies constrain order only when the dependency is already in the
    enabled set, matching Bannerlord launcher semantics. ``ModulesToLoadAfterThis``
    adds the inverse edge without enabling its target.
    """
    modules = installed_modules(game_root)
    selected_id, installed = _selected_module_from_index(project, modules)
    selected_metadata = read_submodule(installed / "SubModule.xml")
    if not is_singleplayer_module(selected_metadata):
        raise RuntimeError(
            f"Bannerlord module {selected_id} is not declared as a single-player module; "
            "Lexeditor Play currently supports single-player modules only."
        )

    metadata_cache: dict[str, dict] = {selected_id: selected_metadata}

    def metadata(module_id: str) -> dict:
        if module_id not in metadata_cache:
            folder = modules.get(module_id)
            if folder is None:
                raise RuntimeError(f"Required Bannerlord dependency is not installed: {module_id}")
            metadata_cache[module_id] = read_submodule(folder / "SubModule.xml")
        return metadata_cache[module_id]

    included: set[str] = set()
    preference: list[str] = []
    visiting: set[str] = set()

    def include_required(module_id: str) -> None:
        if module_id in included:
            return
        if module_id in visiting:
            raise RuntimeError(f"Bannerlord required-dependency cycle includes {module_id}")
        if module_id not in modules:
            raise RuntimeError(f"Required Bannerlord dependency is not installed: {module_id}")
        visiting.add(module_id)
        for dependency in metadata(module_id).get("dependencies", []):
            dependency_id = str(dependency.get("id") or "").strip()
            if not dependency_id or dependency.get("optional"):
                continue
            include_required(dependency_id)
        visiting.remove(module_id)
        included.add(module_id)
        preference.append(module_id)

    # Lexeditor's direct single-player profile includes the installed official SP
    # stack, then the selected project's required closure. Optional dependencies
    # are deliberately not auto-enabled merely because their folders exist.
    for module_id in CORE_SINGLEPLAYER_MODULES:
        if module_id in modules:
            include_required(module_id)
    include_required(selected_id)

    edges: dict[str, set[str]] = {module_id: set() for module_id in included}
    indegree = {module_id: 0 for module_id in included}

    def add_edge(before: str, after: str) -> None:
        if before == after or after in edges[before]:
            return
        edges[before].add(after)
        indegree[after] += 1

    conflicts = []
    for module_id in list(included):
        model = metadata(module_id)
        for dependency in model.get("dependencies", []):
            dependency_id = str(dependency.get("id") or "").strip()
            if dependency_id in included:
                add_edge(dependency_id, module_id)
            elif dependency_id and not dependency.get("optional"):
                # Defensive consistency check; include_required should have caught it.
                raise RuntimeError(f"Required Bannerlord dependency is not enabled: {dependency_id}")

        for relation in model.get("modulesToLoadAfterThis", []):
            after_id = str(relation.get("id") or "").strip()
            if after_id in included:
                add_edge(module_id, after_id)
        for relation in model.get("incompatibleModules", []):
            incompatible_id = str(relation.get("id") or "").strip()
            if incompatible_id in included:
                conflicts.append((module_id, incompatible_id))

    if conflicts:
        rows = ", ".join(f"{left} ↔ {right}" for left, right in conflicts)
        raise RuntimeError(f"Incompatible Bannerlord modules would be enabled together: {rows}")

    rank = {module_id: index for index, module_id in enumerate(preference)}
    ready = [module_id for module_id, count in indegree.items() if count == 0]
    order: list[str] = []
    while ready:
        ready.sort(key=lambda value: (rank.get(value, len(rank)), value.casefold()))
        module_id = ready.pop(0)
        order.append(module_id)
        for after_id in sorted(edges[module_id], key=str.casefold):
            indegree[after_id] -= 1
            if indegree[after_id] == 0:
                ready.append(after_id)

    if len(order) != len(included):
        blocked = sorted(
            (module_id for module_id, count in indegree.items() if count > 0),
            key=str.casefold,
        )
        raise RuntimeError(
            "Bannerlord module load-order constraints form a cycle: " + ", ".join(blocked)
        )
    return order


def _launch_command(game_root: Path, modules: list[str]) -> list[str]:
    game_root = game_root.resolve()
    executable = game_root / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
    if not executable.is_file():
        raise RuntimeError(f"Bannerlord.exe not found: {executable}")
    module_argument = "_MODULES_*" + "*".join(modules) + "*_MODULES_"
    return [str(executable), "/singleplayer", module_argument]


def launch_command(game_root: Path, project: Path) -> list[str]:
    return _launch_command(game_root, module_load_order(game_root, project))


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
            load_order = module_load_order(game_root, project)
            module_id = _selected_project_id(project)
            command = _launch_command(game_root, load_order)
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
