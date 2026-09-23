"""Project Zomboid Build 42 plugin package."""

from __future__ import annotations

import os
from pathlib import Path

from . import core as core


_original_read_items = core.read_items
_original_data_map = core.data_map


def _portable_script_paths(root: Path) -> list[Path]:
    """Return supported script files with canonical filesystem identities."""
    root = Path(root).resolve()
    paths: dict[str, Path] = {}
    for relative in core.SCRIPT_ROOTS:
        base = (root / Path(*relative.split("/"))).resolve()
        if not base.is_dir():
            continue
        for path in base.rglob("*.txt"):
            if not path.is_file() or path.is_symlink():
                continue
            resolved = path.resolve()
            paths[os.path.normcase(str(resolved))] = resolved
    return sorted(
        paths.values(),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def _portable_read_items(root: Path) -> dict:
    """Avoid Windows 8.3-vs-long-name aliases breaking relative paths."""
    return _original_read_items(Path(root).resolve())


def _portable_data_map(root: Path) -> dict:
    return _original_data_map(Path(root).resolve())


# Windows CI exposes temporary roots through both RUNNER~1 and runneradmin.
# Resolve the API root before any relative-path operation so these aliases compare
# as one filesystem identity. Linux remains case-sensitive through normcase.
core.script_paths = _portable_script_paths
core.read_items = _portable_read_items
core.data_map = _portable_data_map
