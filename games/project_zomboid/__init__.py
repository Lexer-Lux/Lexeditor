"""Project Zomboid Build 42 plugin package."""

from __future__ import annotations

import os
from pathlib import Path

from . import core as core


def _portable_script_paths(root: Path) -> list[Path]:
    """Return supported script files with resolved, case-normalized identities.

    Build 42 project APIs use forward-slash relative paths, while Windows may
    resolve a temporary/project root with different case or alias spelling. Keep
    enumeration canonical so save-time containment checks compare like with like.
    """
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
            key = os.path.normcase(str(resolved))
            paths[key] = resolved
    return sorted(paths.values(), key=lambda path: path.relative_to(root).as_posix().casefold())


# Keep the canonical implementation in core while normalizing filesystem identity
# at package load. This is intentionally narrow and covered on both Windows/Linux CI.
core.script_paths = _portable_script_paths
