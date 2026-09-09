"""Project-overlay inventory and safe revert operations for Chrono Trigger."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from .ctext_manager import DEPLOY_MANIFEST
from .data import OverlayStore, classify_resource, normalize_virtual_path
from .paths import PROJECT_MARKER


EXCLUDED_ROOT_FILES = {PROJECT_MARKER, DEPLOY_MANIFEST}


def _resource_files(store: OverlayStore) -> list[tuple[str, Path]]:
    root = store.project_root.resolve()
    if not root.is_dir():
        return []
    rows = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"Project changes refuse symlinked content: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if len(relative.parts) == 1 and relative.name in EXCLUDED_ROOT_FILES:
            continue
        virtual = normalize_virtual_path(PurePosixPath(*relative.parts).as_posix())
        rows.append((virtual, path))
    return sorted(rows, key=lambda item: item[0].casefold())


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def list_changes(store: OverlayStore) -> dict:
    rows = []
    counts = {"modified": 0, "added": 0, "redundant": 0}
    for virtual, path in _resource_files(store):
        project_data = path.read_bytes()
        project_sha = _digest(project_data)
        vanilla_exists = False
        vanilla_sha = None
        same = False
        try:
            vanilla = store.archive.read(virtual)
            vanilla_exists = True
            vanilla_sha = _digest(vanilla)
            same = project_data == vanilla
        except KeyError:
            pass
        status = "redundant" if same else "modified" if vanilla_exists else "added"
        counts[status] += 1
        rows.append({
            "path": virtual,
            "size": len(project_data),
            "sha256": project_sha,
            "vanillaExists": vanilla_exists,
            "vanillaSha256": vanilla_sha,
            "sameAsVanilla": same,
            "status": status,
            **classify_resource(virtual),
        })
    return {
        "kind": "project-changes",
        "project": str(store.project_root.resolve()),
        "writable": store.writable,
        "counts": counts,
        "changeCount": len(rows),
        "rows": rows,
    }


def _target(store: OverlayStore, virtual_path: str) -> Path:
    virtual = normalize_virtual_path(virtual_path)
    root = store.project_root.resolve()
    target = (root / Path(*PurePosixPath(virtual).parts)).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Project revert path escaped the selected project")
    return target


def revert_change(store: OverlayStore, virtual_path: str, expected_sha256: str) -> dict:
    if not store.writable:
        raise RuntimeError("Create or select an editable Chrono Trigger project before reverting overrides")
    target = _target(store, virtual_path)
    if target.is_symlink():
        raise RuntimeError("Lexeditor will not remove a symlinked project override")
    if not target.is_file():
        raise FileNotFoundError(f"Project override does not exist: {virtual_path}")
    current = _digest(target.read_bytes())
    if current != str(expected_sha256):
        raise RuntimeError("The project override changed since it was listed; refresh before reverting")
    target.unlink()
    root = store.project_root.resolve()
    parent = target.parent
    while parent != root:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    return {"reverted": normalize_virtual_path(virtual_path), **list_changes(store)}
