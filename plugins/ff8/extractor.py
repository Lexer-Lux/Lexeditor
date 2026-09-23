"""Create the private, read-only FF8 baseline used by Lexeditor."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from .fs_archive import FsArchive
from . import formats, paths


Progress = Callable[[int, int, str], None]
BASE_TARGETS = {
    "main": ("kernel.bin", "init.out"),
    "menu": (
        "mitem.bin", "mwepon.bin", "price.bin", "shop.bin", "mngrp.bin",
        "sysfnt.TEX", "sysfnt.tdw", "icon.sp1", "icon.TEX",
    ),
    "battle": ("scene.out",),
}
BASELINE_FORMAT = 3
SOURCE_COMMIT = "343d97e9e15023b15b2956b30c1c80cd93969164"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_fingerprint() -> dict:
    result: dict[str, dict] = {}
    for name, prefix in paths.ARCHIVES.items():
        result[name] = {
            suffix: {"size": prefix.with_suffix(suffix).stat().st_size,
                     "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns}
            for suffix in (".fs", ".fi", ".fl")
        }
    return result


def manifest_path(data_root: Path | None = None) -> Path:
    root = data_root or paths.DATA_ROOT
    return root / "baseline" / "manifest.json"


def baseline_ready(data_root: Path | None = None) -> bool:
    root = data_root or paths.DATA_ROOT
    manifest = manifest_path(root)
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("format") != BASELINE_FORMAT:
            return False
        if data.get("source") != source_fingerprint():
            return False
        return all((root / "baseline" / relative).is_file()
                   for relative in data.get("files", {}))
    except (OSError, ValueError, TypeError):
        return False


def prepare(game_root: Path | None = None, data_root: Path | None = None,
            progress: Progress | None = None) -> dict:
    """Extract only the files that this plugin can use."""
    if game_root is not None:
        resolved_game = Path(game_root).resolve()
        os.environ["LEXEDITOR_FF8_ROOT"] = str(resolved_game)
        paths.GAME_ROOT = resolved_game
        paths.ARCHIVES = {
            "main": resolved_game / "Data" / "lang-en" / "main",
            "menu": resolved_game / "Data" / "lang-en" / "menu",
            "battle": resolved_game / "Data" / "lang-en" / "battle",
        }
    root = data_root or paths.DATA_ROOT
    root = Path(root).resolve()
    paths.DATA_ROOT = root
    paths.BASELINE_ROOT = root / "baseline" / "en"
    root.parent.mkdir(parents=True, exist_ok=True)
    if paths.game_problems():
        raise RuntimeError("\n".join(paths.game_problems()))
    if baseline_ready(root):
        paths.DIRECT_ROOT.mkdir(parents=True, exist_ok=True)
        from .game_icons import ensure_icons
        manifest = json.loads(manifest_path(root).read_text(encoding="utf-8"))
        manifest["gameIcons"] = ensure_icons(root)
        return manifest

    targets: list[tuple[str, object]] = []
    archives: dict[str, FsArchive] = {}
    for archive_name, names in BASE_TARGETS.items():
        archive = FsArchive(paths.ARCHIVES[archive_name])
        archives[archive_name] = archive
        targets.extend((archive_name, archive.find(name)) for name in names)
    targets.extend(("battle", entry) for entry in archives["battle"].matching("c0m", ".dat"))
    total = len(targets)
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff8-baseline-", dir=str(root.parent)) as temp_name:
        temp_root = Path(temp_name) / "baseline"
        output_root = temp_root / "en"
        files: dict[str, dict] = {}
        for index, (archive_name, entry) in enumerate(targets, 1):
            destination = output_root / archive_name / entry.basename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archives[archive_name].extract(entry))
            relative = destination.relative_to(temp_root).as_posix()
            files[relative] = {"size": destination.stat().st_size, "sha256": _sha256(destination)}
            if progress:
                progress(index, total, f"Extracting {entry.basename}")
        manifest = {
            "format": BASELINE_FORMAT,
            "game": "Final Fantasy VIII (2013 Steam)",
            "source": source_fingerprint(),
            "upstream": {"project": "FF8UltimateEditor", "commit": SOURCE_COMMIT},
            "files": files,
        }
        (temp_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        destination = root / "baseline"
        destination.parent.mkdir(parents=True, exist_ok=True)
        old = root / "baseline.previous"
        if old.exists():
            shutil.rmtree(old)
        if destination.exists():
            destination.replace(old)
        temp_root.replace(destination)
        if old.exists():
            shutil.rmtree(old)
    paths.DIRECT_ROOT.mkdir(parents=True, exist_ok=True)
    from .game_icons import ensure_icons
    manifest["gameIcons"] = ensure_icons(root)
    return manifest


def plugin_prepare(game_root: Path, data_root: Path, progress: Progress) -> dict:
    """Adapter for the shared launcher preparation contract."""
    os.environ["LEXEDITOR_FF8_ROOT"] = str(game_root)
    os.environ["LEXEDITOR_FF8_DATA_ROOT"] = str(data_root)
    manifest = prepare(game_root, data_root, progress)
    from .gameplay_settings import ensure as ensure_gameplay_patch
    from .ffnx_manager import ensure_ffnx
    from .runtime_layout import catalog, compose
    gameplay = ensure_gameplay_patch(
        game_root, paths.PROJECT_ROOT, runtime_root=paths.RUNTIME_ROOT,
    )
    composition = compose(
        paths.PROJECT_ROOT, paths.RUNTIME_ROOT,
        catalog(paths.PROJECT_ROOT, paths.MODS_ROOT),
        paths.BASELINE_ROOT, formats.SECTIONS,
    )
    helper = ensure_ffnx(game_root, paths.RUNTIME_DIRECT_ROOT, progress)
    from theme_sounds import ensure_theme_sounds
    sounds = ensure_theme_sounds(game_root, data_root, ("Data/Sound",), {
        "confirm": 1, "move": 1, "back": 9, "exit": 9,
        "launch": 29, "save": 37,
    })
    return {**manifest, "gameplay": gameplay, "composition": composition,
            "ffnx": helper, "themeSounds": sounds}
