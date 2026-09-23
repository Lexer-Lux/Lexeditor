"""Journal and rollback only the destinations declared by the pinned patcher."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile

from .memoria_patcher import PayloadFile

CLEANUP_PATH = "StreamingAssets/Assets/Resources/CommonAsset"
CONFIG_NAMES = {"memoria.ini", "settings.ini"}
MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def root_key(root: Path) -> str:
    return hashlib.sha256(os.path.normcase(str(root.resolve())).encode("utf-8")).hexdigest()[:24]


def atomic_json(target: Path, value: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or any(
            p in {".", ".."} or "\\" in p or ":" in p for p in parts):
        raise RuntimeError("Unsafe path in the Memoria recovery manifest")
    current = root
    for part in parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise RuntimeError(f"Memoria cannot safely patch a linked path: {current}")
    return current


@contextmanager
def install_lock(root: Path, control_root: Path, *, recover_stale: bool = False):
    """OS-owned lock: exclusive across processes and released after a crash.

    Keep the lock file's inode. Unlinking a supposedly stale PID file can race
    another recovery process and remove its newly acquired lock instead.
    The recovery flag remains a compatible argument; the journal, not a stale
    PID, decides whether an interrupted installation needs explicit recovery.
    """
    control_root.mkdir(parents=True, exist_ok=True)
    path = control_root / (root_key(root) + ".lock")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "r+b", buffering=0) as stream:
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError(f"Another Memoria operation holds {path}. Close any patcher before recovering an interrupted operation.") from error
        try:
            stream.write(str(os.getpid()).encode("ascii"))
            stream.truncate()
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Recovery:
    def __init__(self, root: Path, journal: Path):
        self.root = root.resolve()
        self.journal = journal
        self.folder = journal.parent
        self.manifest = json.loads(journal.read_text(encoding="utf-8"))
        if self.manifest.get("root") != str(self.root):
            raise RuntimeError("The Memoria recovery belongs to a different game folder")

    @classmethod
    def prepare(cls, root: Path, files: tuple[PayloadFile, ...], backup_root: Path) -> "Recovery":
        root = root.resolve()
        backup_root = backup_root.resolve()
        if root == backup_root or root in backup_root.parents:
            raise RuntimeError("Memoria backups must be outside the game folder")
        names = {entry.relative_path for entry in files}
        for entry in files:
            name = PurePosixPath(entry.relative_path)
            if name.suffix.casefold() in {".exe", ".dll"}:
                names.add(str(name.with_suffix(".bak")))
            if name.name.casefold() in CONFIG_NAMES:
                names.add(str(name) + ".bak")
            if name.name.casefold() == "ff9_launcher.exe":
                names.add(str(name.with_suffix(".fix")))
        cleanup = safe_path(root, CLEANUP_PATH)
        directories = []
        if cleanup.exists():
            if not cleanup.is_dir():
                raise RuntimeError("Memoria's field-script cleanup path is not a directory")
            directories.append(CLEANUP_PATH)
            for path in cleanup.rglob("*"):
                relative = path.relative_to(root).as_posix()
                safe_path(root, relative)
                if path.is_dir():
                    directories.append(relative)
                elif path.is_file():
                    names.add(relative)
                else:
                    raise RuntimeError(f"Cannot back up this game file: {path}")
        rows, total = [], 0
        for relative in sorted(names):
            path = safe_path(root, relative)
            if path.exists() and not path.is_file():
                raise RuntimeError(f"A Memoria file destination is not a file: {path}")
            exists = path.is_file()
            size = path.stat().st_size if exists else 0
            total += size
            rows.append({"path": relative, "exists": exists, "size": size})
        if total > MAX_BACKUP_BYTES:
            raise RuntimeError("Memoria recovery backup exceeds the 2 GiB safety limit")
        backup_root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(backup_root).free < total + 64 * 1024 * 1024:
            raise RuntimeError("There is not enough free space for a Memoria recovery backup")
        folder = Path(tempfile.mkdtemp(prefix=root_key(root) + "-", dir=backup_root))
        journal = folder / "manifest.json"
        # No game writes have happened yet. Failure here leaves the game alone.
        for row in rows:
            if row["exists"]:
                source = safe_path(root, row["path"])
                target = safe_path(folder / "files", row["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                before = digest(source)
                shutil.copy2(source, target)
                if before != digest(target) or before != digest(source):
                    raise RuntimeError(f"A game file changed while backing it up: {source}")
                row["sha256"] = before
        atomic_json(journal, {"root": str(root), "phase": "prepared", "files": rows,
                              "directories": directories})
        return cls(root, journal)

    def phase(self, value: str) -> None:
        self.manifest["phase"] = value
        atomic_json(self.journal, self.manifest)

    def preserve_config(self) -> None:
        # The publisher's INI merge rewrites user comments and whitespace.
        # Keep existing configuration byte-for-byte; new installs keep defaults.
        for row in self.manifest["files"]:
            if row["exists"] and PurePosixPath(row["path"]).name.casefold() in CONFIG_NAMES:
                self._restore_file(row)

    def _restore_file(self, row: dict) -> None:
        source = safe_path(self.folder / "files", row["path"])
        if digest(source) != row["sha256"]:
            raise RuntimeError(f"The Memoria backup is damaged: {source}")
        target = safe_path(self.root, row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=target.name + ".restore-", dir=target.parent)
        os.close(fd)
        try:
            shutil.copy2(source, name)
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)

    def rollback(self) -> None:
        # Prove every backup is intact before restoring any of them.
        for row in self.manifest["files"]:
            safe_path(self.root, row["path"])
            if row["exists"] and digest(safe_path(self.folder / "files", row["path"])) != row["sha256"]:
                raise RuntimeError("The Memoria recovery backup is damaged; no rollback was attempted")
        self.phase("restoring")
        for row in self.manifest["files"]:
            if row["exists"]:
                self._restore_file(row)
            else:
                safe_path(self.root, row["path"]).unlink(missing_ok=True)
        for relative in self.manifest["directories"]:
            safe_path(self.root, relative).mkdir(parents=True, exist_ok=True)
        self.phase("rolled-back")


def verify_install(root: Path, files: tuple[PayloadFile, ...]) -> None:
    """A zero patcher exit code is not evidence that extraction succeeded."""
    for entry in files:
        path = safe_path(root, entry.relative_path)
        if path.name.casefold() in CONFIG_NAMES:
            if not path.is_file() or not path.stat().st_size:
                raise RuntimeError(f"Memoria did not create its configuration: {path}")
            continue
        candidates = [path]
        if path.name.casefold() == "ff9_launcher.exe":
            candidates.append(path.with_suffix(".fix"))
        if not any(candidate.is_file() and candidate.stat().st_size == entry.size
                   and digest(candidate) == entry.sha256 for candidate in candidates):
            raise RuntimeError(f"Memoria did not install the verified file: {path}")
