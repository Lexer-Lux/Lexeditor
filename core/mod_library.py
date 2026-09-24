"""Shared, staged mod imports. Game adapters decide which files can load."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import stat
import tempfile
import uuid
import zipfile


MOD_FILE = "mod.json"  # Same metadata file used by the FF8 mod composer.
MAX_FILES = 100000
MAX_BYTES = 32 * 1024**3


def documents_folder() -> Path:
    """Ask Windows for Documents, including folder redirection."""
    if os.name != "nt":
        raise RuntimeError("Choose a mod library folder on this operating system")
    folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(
        uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)
    result = ctypes.c_void_p()
    shell = ctypes.windll.shell32.SHGetKnownFolderPath
    shell.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                      ctypes.POINTER(ctypes.c_void_p)]
    shell.restype = ctypes.c_long
    status = shell(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
    if status != 0:
        raise OSError(f"Windows could not locate Documents ({status:#x})")
    try:
        return Path(ctypes.wstring_at(result))
    finally:
        ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.ole32.CoTaskMemFree(result)


def legacy_appdata_library_root() -> Path:
    """Where per-game mod folders lived before the Documents move."""
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Lexeditor" / "mods"


def default_user_library_root() -> Path:
    """Documents/Mods, falling back to the legacy AppData library."""
    try:
        return documents_folder() / "Mods"
    except (OSError, RuntimeError):
        return legacy_appdata_library_root()


# Per-game user-data trees that moved from AppData to Documents: the
# environment override that keeps winning, and the game folder under both
# libraries. Whole trees move so custom projects move with the defaults.
USER_DATA_MOVES = (
    {"env": "LEXEDITOR_FF7_PROJECT", "game": "ff7"},
    {"env": "LEXEDITOR_FF7_2013_PROJECT", "game": "ff7-2013"},
    {"env": "LEXEDITOR_FF8_MODS_ROOT", "game": "ff8"},
)

MIGRATION_JOURNAL = "user-data-migration.json"
SKIP_MIGRATION_ENV = "LEXEDITOR_SKIP_USER_DATA_MIGRATION"


def _read_migration_journal(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def migrate_appdata_user_data(projects=None, journal_dir=None) -> dict:
    """Copy legacy AppData mod trees to Documents once.

    Each move is verified file by file and the AppData source is kept as
    recovery, so a failed or interrupted move loses nothing. A game is
    skipped when its environment override is set, when the AppData tree is
    missing or empty, when Documents already holds that game, or when the
    journal records a finished move. Returns {"moved": [...], "skipped": [...]}.
    """
    report: dict[str, list] = {"moved": [], "skipped": []}
    if os.environ.get(SKIP_MIGRATION_ENV):
        report["skipped"].append({"game": "*", "reason": "disabled"})
        return report
    old_library = legacy_appdata_library_root()
    new_library = default_user_library_root()
    if old_library == new_library:
        report["skipped"].append({"game": "*", "reason": "same library"})
        return report
    base = Path(journal_dir) if journal_dir else old_library.parent
    journal_path = base / MIGRATION_JOURNAL
    journal = _read_migration_journal(journal_path)
    moves = journal.setdefault("moves", {})

    def record() -> None:
        try:
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            journal_path.write_text(json.dumps(journal, indent=2), encoding="utf-8")
        except OSError:
            pass

    for spec in USER_DATA_MOVES:
        game = spec["game"]
        if os.environ.get(spec["env"]):
            report["skipped"].append({"game": game, "reason": "environment override set"})
            continue
        if moves.get(game, {}).get("phase") == "done":
            report["skipped"].append({"game": game, "reason": "already migrated"})
            continue
        source, dest = old_library / game, new_library / game
        if not source.is_dir() or not any(source.iterdir()):
            report["skipped"].append({"game": game, "reason": "nothing to migrate"})
            continue
        if dest.exists() and any(dest.iterdir()):
            moves[game] = {"source": str(source), "dest": str(dest), "phase": "settled"}
            record()
            report["skipped"].append({"game": game, "reason": "Documents copy already settled"})
            continue
        try:
            files = [path for path in file_tree(source) if (source / path).is_file()]
            total = sum((source / path).stat().st_size for path in files)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if total > shutil.disk_usage(dest.parent).free:
                raise OSError("There is not enough space to migrate this library")
            staged = dest.parent / f".migrate-{game}"
            if staged.exists():
                shutil.rmtree(staged, ignore_errors=True)
            staged.mkdir(parents=True, exist_ok=True)
            try:
                for path in files:
                    target = staged / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source / path, target)
                    if digest(source / path) != digest(target):
                        raise OSError(f"Copy verification failed: {path}")
                if dest.is_dir() and not any(dest.iterdir()):
                    dest.rmdir()
                staged.rename(dest)
            except BaseException:
                shutil.rmtree(staged, ignore_errors=True)
                raise
        except (OSError, ValueError) as error:
            moves[game] = {"source": str(source), "dest": str(dest), "phase": "failed",
                           "error": str(error)[:200]}
            record()
            report["skipped"].append({"game": game, "reason": f"move failed: {error}"})
            continue
        if projects is not None:
            try:
                projects.remap_prefix(source, dest)
            except OSError:
                pass
        moves[game] = {"source": str(source), "dest": str(dest), "files": len(files),
                       "bytes": total, "phase": "done"}
        record()
        report["moved"].append({"game": game, "source": str(source), "dest": str(dest),
                               "files": len(files), "bytes": total})
    return report


def relative_path(value: str) -> Path:
    """Reject traversal, alternate streams and Windows name aliases."""
    value = value.replace("\\", "/")
    parts = value.split("/")
    if (not value or PureWindowsPath(value).drive or value.startswith("/")
            or any(not part or part in {".", ".."} or part.endswith((".", " "))
                   or any(c in part for c in '<>:"|?*')
                   or any(ord(c) < 32 for c in part)
                   or PureWindowsPath(part).is_reserved() for part in parts)):
        raise ValueError(f"Unsafe mod path: {value}")
    return Path(*parts)


def metadata(root: Path) -> dict:
    path = root / MOD_FILE
    if not path.exists():
        return {"name": root.name, "version": ""}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("mod.json must contain an object")
    for key in ("name", "version"):
        if key in value and not isinstance(value[key], str):
            raise ValueError(f"Mod {key} must be text")
    return {**value, "name": value.get("name") or root.name,
            "version": value.get("version", "")}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def file_tree(root: Path) -> list[Path]:
    files = []
    size = 0
    seen = set()
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in folders + names:
            path = Path(directory) / name
            attributes = path.lstat()
            if path.is_symlink() or getattr(attributes, "st_file_attributes", 0) & 0x400:
                raise ValueError(f"Mod packages cannot contain links: {path.name}")
            relative = relative_path(path.relative_to(root).as_posix())
            key = relative.as_posix().casefold()
            if key in seen:
                raise ValueError(f"Duplicate mod path: {relative}")
            seen.add(key)
            if len(seen) > MAX_FILES:
                raise ValueError("The mod contains too many files or folders")
            if path.is_file():
                size += attributes.st_size
                files.append(relative)
                if size > MAX_BYTES:
                    raise ValueError("The mod exceeds the import size limit")
    return sorted(files, key=lambda path: path.as_posix().casefold())


@contextmanager
def package_root(source: Path):
    """Expand only ZIPs; never run package code or follow package links."""
    source = Path(source)
    if source.is_symlink() or (source.exists() and
            getattr(source.lstat(), "st_file_attributes", 0) & 0x400):
        raise ValueError("Choose a real folder or ZIP, not a link")
    if source.is_dir():
        file_tree(source)
        yield source
        return
    if source.suffix.casefold() not in {".zip", ".ctp"}:
        raise ValueError("Choose a folder, ZIP archive, or CTP archive")
    with tempfile.TemporaryDirectory(prefix="lexeditor-mod-import-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError("The archive exceeds the import size limit")
            if sum(e.file_size for e in entries) > shutil.disk_usage(root).free:
                raise OSError("There is not enough space to open this archive")
            seen = set()
            for entry in entries:
                path = relative_path(entry.filename.rstrip("/"))
                key = path.as_posix().casefold()
                if key in seen or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError(f"Duplicate path or link in archive: {path}")
                seen.add(key)
                target = root / path
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as src, target.open("xb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
        yield root


class ModLibrary:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def relocate(self, destination: Path, commit, progress=None, journal=None) -> dict:
        """Copy and verify before switching settings. Keep the old library as recovery.

        The caller confirms the paths before invoking this operation. Retaining
        the source also preserves edits made while the copy is in progress.
        """
        destination = Path(destination).resolve()
        if destination == self.root or self.root in destination.parents or destination in self.root.parents:
            raise ValueError("Choose a separate destination outside the current library")
        if destination.exists():
            raise FileExistsError("Choose a new destination folder; existing folders are not merged")
        files = file_tree(self.root) if self.root.exists() else []
        hashes = {path.as_posix(): digest(self.root / path) for path in files}
        total = sum((self.root / path).stat().st_size for path in files)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if total > shutil.disk_usage(destination.parent).free:
            raise OSError("There is not enough space to move the library")
        move = {"source": str(self.root), "destination": str(destination),
                "hashes": hashes, "phase": "copying"}
        if journal:
            journal(move)
        with tempfile.TemporaryDirectory(prefix=".lexeditor-library-", dir=destination.parent) as temp:
            staged = Path(temp) / "library"
            staged.mkdir()
            for index, path in enumerate(files):
                target = staged / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / path, target)
                if digest(target) != hashes[path.as_posix()]:
                    raise OSError(f"File changed during the move: {path}")
                if progress:
                    progress(index + 1, len(files), path.as_posix())
            current = {p.as_posix(): digest(self.root / p) for p in file_tree(self.root)} if self.root.exists() else {}
            if current != hashes:
                raise OSError("The library changed during the move. The current library remains active.")
            staged.rename(destination)
            move["phase"] = "copied"
            if journal:
                journal(move)
            # If settings fail, both copies survive and the original stays active.
            commit(destination)
            move["phase"] = "committed"
            if journal:
                journal(move)
        return {"root": str(destination), "recovery": str(self.root),
                "files": len(files), "bytes": total}

    @staticmethod
    def verify_move_copy(path: Path, expected: dict) -> None:
        actual = {p.as_posix(): digest(path / p) for p in file_tree(path)} if path.is_dir() else ({} if not path.exists() and not expected else None)
        if actual != expected:
            raise ValueError(f"Files changed or are missing in {path}. Both copies were kept.")

    @staticmethod
    def recover_move(move: dict, commit) -> dict:
        source, destination = Path(move["source"]).resolve(), Path(move["destination"]).resolve()
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError("Invalid library recovery paths")
        ModLibrary.verify_move_copy(source, move["hashes"])
        if not destination.exists():
            return {**move, "phase": "retry", "message": "The original library is intact. Start the move again."}
        ModLibrary.verify_move_copy(destination, move["hashes"])
        commit(destination)
        return {**move, "phase": "committed"}

    @staticmethod
    def remove_move_recovery(move: dict, active: Path) -> None:
        source, destination = Path(move["source"]).resolve(), Path(move["destination"]).resolve()
        if (move.get("phase") != "committed" or destination != active.resolve()
                or source == destination or source in destination.parents or destination in source.parents):
            raise ValueError("The verified destination must be active before removing the recovery copy")
        ModLibrary.verify_move_copy(source, move["hashes"])
        ModLibrary.verify_move_copy(destination, move["hashes"])
        # Remove only inventoried files, then empty folders. New files make the
        # final rmdir fail rather than being swept up in recursive deletion.
        for name, expected in move["hashes"].items():
            target = source / relative_path(name)
            if source not in target.resolve().parents or digest(target) != expected:
                raise ValueError("The recovery copy changed during cleanup")
            target.unlink()
        for folder, _dirs, _files in os.walk(source, topdown=False):
            Path(folder).rmdir()

    @staticmethod
    def select_files(files: list[Path], selected: list[str] | None) -> list[Path]:
        if selected is None:
            return files
        choices = [relative_path(value) for value in selected]
        if len(set(choices)) != len(choices) or not set(choices).issubset(files):
            raise ValueError("Choose existing files once each")
        return choices

    def inspect(self, source: Path, adapter, data_root: str = "", selected: list[str] | None = None) -> dict:
        with package_root(source) as package:
            root = package / relative_path(data_root) if data_root else package
            if not root.is_dir():
                raise ValueError("Choose a folder in the package")
            files = self.select_files(file_tree(root), selected)
            result = adapter.inspect(root, files)
            return {**result, "files": [p.as_posix() for p in file_tree(package)],
                    "rootFiles": [p.as_posix() for p in file_tree(root)],
                    "dataRoot": data_root, "metadata": metadata(root)}

    def import_mod(self, plugin_id: str, source: Path, adapter, name: str,
                   data_root: str = "", selected: list[str] | None = None,
                   prepare_editable: bool = False) -> Path:
        game = relative_path(plugin_id)
        folder = relative_path(name)
        if len(game.parts) != 1 or len(folder.parts) != 1:
            raise ValueError("Choose a single folder name")
        parent = self.root / game
        target = parent / folder
        parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"A mod named {name} already exists")
        with package_root(source) as package:
            root = package / relative_path(data_root) if data_root else package
            if not root.is_dir():
                raise ValueError("Choose a folder in the package")
            files = self.select_files(file_tree(root), selected)
            report = adapter.inspect(root, files)
            if not report["valid"]:
                raise ValueError("; ".join(report["problems"]))
            size = sum((root / path).stat().st_size for path in files)
            if size > shutil.disk_usage(parent).free:
                raise OSError("There is not enough space to import this mod")
            with tempfile.TemporaryDirectory(prefix=".import-", dir=parent) as temp:
                staged = Path(temp) / "mod"
                staged.mkdir()
                for path in files:
                    destination = staged / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(root / path, destination)
                    if digest(root / path) != digest(destination):
                        raise OSError(f"Copy verification failed: {path}")
                info = metadata(root)
                info["name"] = name
                (staged / MOD_FILE).write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
                if prepare_editable:
                    adapter.prepare_editable(staged)
                staged.rename(target)
        return target
