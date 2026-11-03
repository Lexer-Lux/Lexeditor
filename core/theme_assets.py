"""Shared browser-theme cache helpers."""
from __future__ import annotations

import json
from pathlib import Path

from core.plugin_files import atomic_write


def atomic_json(target: Path, payload: dict) -> None:
    atomic_write(target, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))


def asset_path(cache_root: Path, route: str) -> Path:
    """Resolve a browser theme URL beneath the private cache root."""
    root = Path(cache_root).resolve()
    relative = str(route).replace("\\", "/").strip("/")
    target = (root / relative).resolve()
    if target == root or root not in target.parents or not target.is_file():
        raise FileNotFoundError("Theme asset not found")
    if "browser" not in target.relative_to(root).parts:
        raise FileNotFoundError("Raw theme sources are not web-served")
    return target
