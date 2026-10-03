"""What the shared Mods tab and the first-run screen need, for every game.

The Mods tab lists every mod folder in the game's library (its standard
details from core/mod_metadata.py, whether it is on, where it came from and
its settings), followed by Lexer's Mod modules the reader has not downloaded.
The first-run screen offers Lexer's Mod once per game.
"""
from __future__ import annotations

import json
from pathlib import Path
import threading
import time

from core import lexmods, mod_metadata, script_mods
from core.mod_library import metadata

CATALOG_TTL = 600
UPDATE_INTERVAL = 3600
_catalogs: dict[str, tuple[float, dict]] = {}
_catalog_lock = threading.Lock()


def game_library(library_root: Path, plugin_id: str) -> Path:
    return Path(library_root) / plugin_id


def checked_mod(game_root: Path, path: str) -> Path:
    """A mod folder directly inside this game's library, or an error."""
    folder = Path(path).resolve()
    if folder.parent != Path(game_root).resolve() or not folder.is_dir() or folder.name.startswith("."):
        raise ValueError("Choose a mod in this game's library")
    return folder


def mod_row(folder: Path) -> dict:
    row = {"path": str(folder), "folder": folder.name, "error": "", "remote": False}
    try:
        info = metadata(folder)
        row.update({key: info.get(key, "") for key in mod_metadata.FIELDS})
        row.update({"version": info.get("version", ""), "missing": info.get("missing", []),
                    "enabled": info.get("enabled") is True, "order": info.get("order", 1000)})
    except (ValueError, OSError) as error:
        row.update({"name": folder.name, "author": "", "description": "", "credits": "", "version": "",
                    "missing": ["name"], "enabled": False, "order": 1000, "error": str(error)})
    marker = folder / lexmods.MARKER
    row["lexmod"] = None
    if marker.is_file():
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
            row["lexmod"] = {"repository": info.get("repository", ""), "version": info.get("version", "")}
        except (OSError, ValueError):
            pass
    row["script"] = None
    if script_mods.is_script_mod(folder):
        script = script_mods.catalog_row(folder)
        row["script"] = {key: script.get(key) for key in ("schema", "values", "trust", "error")}
    return row


def library_rows(game_root: Path) -> list[dict]:
    root = Path(game_root)
    if not root.is_dir():
        return []
    rows = [mod_row(folder) for folder in root.iterdir() if folder.is_dir() and not folder.name.startswith(".")]
    return sorted(rows, key=lambda row: (int(row["order"]) if isinstance(row["order"], int) else 1000,
                                         row["name"].casefold()))


def catalog(repository: str, *, fresh: bool = False) -> dict:
    """Lexer's Mod's latest feature list and modules, cached for a while."""
    with _catalog_lock:
        cached = _catalogs.get(repository)
        if cached and not fresh and time.monotonic() - cached[0] < CATALOG_TTL:
            return cached[1]
    result = lexmods.catalog(repository)
    with _catalog_lock:
        _catalogs[repository] = (time.monotonic(), result)
    return result


def overview(game_root: Path, repository: str) -> dict:
    """Everything the Mods tab lists: local mods first, then downloadable ones."""
    rows = library_rows(game_root)
    result = {"rows": rows, "remote": [], "lexmod": None}
    if not repository:
        return result
    result["lexmod"] = {"repository": repository, "url": f"https://github.com/{repository}", "error": ""}
    try:
        remote = catalog(repository)
    except lexmods.LexmodError as error:
        result["lexmod"]["error"] = str(error)
        return result
    present = set(lexmods.installed(game_root, repository))
    local = {row["folder"].casefold() for row in rows}
    result["lexmod"]["version"] = remote["version"]
    result["remote"] = [{**module, "remote": True} for module in remote["modules"]
                        if module["folder"] not in present and module["folder"].casefold() not in local]
    return result


def set_enabled(folder: Path, enabled: bool) -> None:
    if type(enabled) is not bool:
        raise ValueError("A mod is on or off")
    stored = mod_metadata._stored(folder)
    stored["enabled"] = enabled
    if not str(stored.get("name", "")).strip():
        raise mod_metadata.MetadataError("Name this mod before switching it on or off")
    from core.plugin_files import atomic_write
    atomic_write(Path(folder) / mod_metadata.FILE, (json.dumps(stored, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


class Downloads:
    """One Lexer's Mod download per game, run in the background.

    Back on the first-run screen cancels a download in progress, or removes
    what a finished one just installed; nothing else is touched.
    """

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, plugin_id: str, repository: str, game_root: Path, modules: list[str] | None = None) -> dict:
        with self._lock:
            job = self._jobs.get(plugin_id)
            if job and job["state"] == "running":
                raise ValueError("Lexer's mod is already downloading")
            job = {"state": "running", "phase": "download", "done": 0, "total": 0, "error": "",
                   "installed": [], "cancel": threading.Event(), "repository": repository,
                   "root": str(game_root)}
            self._jobs[plugin_id] = job

        def progress(phase, done, total):
            job.update(phase=phase, done=done, total=total)

        def run():
            try:
                result = lexmods.install(repository, game_root, modules=modules, progress=progress, cancel=job["cancel"])
                job.update(state="done", installed=result["installed"], version=result["version"])
            except lexmods.Cancelled:
                job.update(state="cancelled")
            except Exception as error:  # Reported on the screen, never raised in the thread.
                job.update(state="failed", error=str(error))

        threading.Thread(target=run, name=f"lexmod-{plugin_id}", daemon=True).start()
        return self.progress(plugin_id)

    def progress(self, plugin_id: str) -> dict:
        job = self._jobs.get(plugin_id)
        if not job:
            return {"state": "idle"}
        return {key: value for key, value in job.items() if key not in ("cancel", "root", "repository")}

    def cancel(self, plugin_id: str) -> dict:
        """Stop a running download, or take back what a finished one installed."""
        job = self._jobs.get(plugin_id)
        if not job:
            return {"state": "idle"}
        if job["state"] == "running":
            job["cancel"].set()
        elif job["state"] == "done":
            lexmods.remove(Path(job["root"]), job["repository"], job["installed"])
            job.update(state="cancelled", installed=[])
        return self.progress(plugin_id)


def update_if_due(repository: str, game_root: Path, state_path: Path) -> dict:
    """Bring downloaded modules up to the latest version, at most hourly."""
    if not repository or not lexmods.installed(game_root, repository):
        return {"updated": False}
    try:
        state = json.loads(Path(state_path).read_text(encoding="utf-8")) if Path(state_path).is_file() else {}
    except (OSError, ValueError):
        state = {}
    last = state.get(repository, 0)
    if isinstance(last, (int, float)) and time.time() - last < UPDATE_INTERVAL:
        return {"updated": False}
    state[repository] = time.time()
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(json.dumps(state), encoding="utf-8")
    current = {info.get("version") for info in lexmods.installed(game_root, repository).values()}
    version = lexmods.latest(repository)
    if current == {version["version"]}:
        return {"updated": False, "version": version["version"]}
    result = lexmods.install(repository, game_root, modules=[])
    return {"updated": True, **result}


class Onboarding:
    """Which games have shown their first-run screen."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _done(self) -> list[str]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return [item for item in value.get("done", []) if isinstance(item, str)] if isinstance(value, dict) else []

    def seen(self, plugin_id: str) -> bool:
        return plugin_id in self._done()

    def finish(self, plugin_id: str) -> None:
        done = self._done()
        if plugin_id not in done:
            done.append(plugin_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"done": done}, indent=2) + "\n", encoding="utf-8")
