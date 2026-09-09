"""Deterministic CTExt CTP export for Chrono Trigger projects.

CTExt reads ``.ctp`` files with a ZIP reader and maps archive member names to
the same virtual resource paths used by loose-file mods. Lexeditor therefore
exports project resource files directly without ever rebuilding resources.bin.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import tempfile
import zipfile


EXCLUDED_ROOT_FILES = {"lexeditor-project.json", ".lexeditor-deployment.json"}
_FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _project_files(project_root: Path) -> list[tuple[str, Path]]:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Chrono Trigger project does not exist: {root}")
    rows: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"CTP export refuses symlinked project content: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if len(relative.parts) == 1 and relative.name in EXCLUDED_ROOT_FILES:
            continue
        virtual = PurePosixPath(*relative.parts).as_posix()
        if not virtual or virtual.startswith("/") or any(part in {"", ".", ".."} for part in PurePosixPath(virtual).parts):
            raise RuntimeError(f"Unsafe CTP member path: {virtual}")
        rows.append((virtual, path))
    return sorted(rows, key=lambda item: item[0].casefold())


def export_ctp(project_root: Path, target: Path) -> dict:
    root, destination = Path(project_root).resolve(), Path(target).resolve()
    if destination == root or root in destination.parents:
        raise ValueError("CTP export target must be outside the project directory")
    rows = _project_files(root)
    if not rows:
        raise RuntimeError("The Chrono Trigger project has no resource files to export")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    Path(name).unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(name, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for virtual, path in rows:
                info = zipfile.ZipInfo(virtual, _FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        temporary = Path(name)
        temporary.replace(destination)
    finally:
        Path(name).unlink(missing_ok=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {
        "format": "CTExt CTP (ZIP)",
        "project": str(root),
        "path": str(destination),
        "fileCount": len(rows),
        "size": destination.stat().st_size,
        "sha256": digest,
        "members": [virtual for virtual, _path in rows],
    }


def default_target(project_root: Path) -> Path:
    root = Path(project_root).resolve()
    return root.parent / f"{root.name}.ctp"
