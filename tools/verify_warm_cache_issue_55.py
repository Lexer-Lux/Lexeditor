"""Warm-cache regression checks for GitHub issue #55."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import extractor as ff8
from games.ff8 import game_icons as ff8_icons
from games.ff8 import paths as ff8_paths
from games.rdr import extractor as rdr


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def verify_ff8(root: Path) -> None:
    game = root / "game"
    data = root / "data"
    archives = {}
    for name in ff8.BASE_TARGETS:
        prefix = game / "Data" / "lang-en" / name
        archives[name] = prefix
        for suffix in (".fs", ".fi", ".fl"):
            write(prefix.with_suffix(suffix), f"{name}{suffix}".encode())

    files = {
        "en/main/kernel.bin": b"kernel",
        "en/menu/mitem.bin": b"items",
        "en/battle/scene.out": b"scene",
    }
    for relative, payload in files.items():
        write(data / "baseline" / relative, payload)
    manifest = {
        "format": ff8.BASELINE_FORMAT,
        "source": {
            name: {
                suffix: {
                    "size": prefix.with_suffix(suffix).stat().st_size,
                    "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns,
                }
                for suffix in (".fs", ".fi", ".fl")
            }
            for name, prefix in archives.items()
        },
        "files": {relative: {"size": len(payload)} for relative, payload in files.items()},
    }
    manifest_path = data / "baseline" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    old_archives, old_root = ff8_paths.ARCHIVES, ff8_paths.DIRECT_ROOT
    old_game_root = ff8_paths.GAME_ROOT
    old_data_root, old_baseline_root = ff8_paths.DATA_ROOT, ff8_paths.BASELINE_ROOT
    old_problems, old_icons = ff8_paths.game_problems, ff8_icons.ensure_icons
    old_archive_class = ff8.FsArchive
    calls = []
    try:
        ff8_paths.ARCHIVES = archives
        ff8_paths.DIRECT_ROOT = root / "direct"
        ff8_paths.game_problems = lambda: []
        ff8_icons.ensure_icons = lambda _root=None: {"available": False}

        class ExtractionTrap:
            def __init__(self, *_args, **_kwargs):
                calls.append("extractor-created")
                raise AssertionError("FF8 warm cache launched an extractor")

        ff8.FsArchive = ExtractionTrap
        assert ff8.baseline_ready(data)
        before = manifest_path.stat().st_mtime_ns
        first = ff8.prepare(game, data)
        second = ff8.prepare(game, data)
        assert first["format"] == ff8.BASELINE_FORMAT and second["format"] == ff8.BASELINE_FORMAT
        assert not calls
        assert manifest_path.stat().st_mtime_ns == before
        missing = data / "baseline" / "en" / "main" / "kernel.bin"
        missing.unlink()
        assert not ff8.baseline_ready(data)
    finally:
        ff8.FsArchive = old_archive_class
        ff8_paths.ARCHIVES = old_archives
        ff8_paths.DIRECT_ROOT = old_root
        ff8_paths.GAME_ROOT = old_game_root
        ff8_paths.DATA_ROOT = old_data_root
        ff8_paths.BASELINE_ROOT = old_baseline_root
        ff8_paths.game_problems = old_problems
        ff8_icons.ensure_icons = old_icons


def verify_rdr(root: Path) -> None:
    game = root / "game-root"
    data = root / "data"
    archives = {
        "tuning": game / rdr.TUNING_ARCHIVE_RELATIVE,
        "content": game / rdr.CONTENT_ARCHIVE_RELATIVE,
        "gringores": game / rdr.GRINGO_ARCHIVE_RELATIVE,
    }
    for path in archives.values():
        write(path, b"RPF6-test")
    tool = root / "rpf6-tool.exe"
    write(tool, b"tool")
    write(data / rdr.TUNING_CACHE_NAME / rdr.KNOWN_TUNING_XML, b"<root/>")
    write(data / rdr.CONTENT_CACHE_NAME / rdr.INVENTORY_XML, b"<inventory/>")
    write(data / rdr.CONTENT_CACHE_NAME / rdr.DLC_INVENTORY_XML, b"<inventory/>")
    packed = data / rdr.GRINGO_PACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    unpacked = data / rdr.GRINGO_UNPACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    write(packed, b"RSC-packed")
    write(unpacked, b"unpacked")
    sources = {name: rdr._source_record(path) for name, path in archives.items()}
    tool_record = {"path": str(tool), "sha256": rdr.sha256(tool)}
    manifest = {
        "version": 3,
        "sources": sources,
        "tool": tool_record,
        "fileCounts": {"tuning": 1000, "inventory": 2,
                       "gringoPacked": 39, "gringoUnpacked": 39},
    }
    manifest_path = data / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    old_tool, old_extract = rdr.RPF6_TOOL, rdr._extract
    progress = []
    try:
        rdr.RPF6_TOOL = tool
        rdr._extract = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("RDR1 warm cache launched an extractor"))
        assert rdr._valid_cache(data, sources, tool_record, manifest)
        before = manifest_path.stat().st_mtime_ns
        first = rdr.ensure_rdr_data(game, data, lambda *value: progress.append(value))
        second = rdr.ensure_rdr_data(game, data, lambda *value: progress.append(value))
        assert first == manifest and second == manifest
        assert manifest_path.stat().st_mtime_ns == before
        assert not any("Extracting" in str(value) or "Unpacking" in str(value)
                       for value in progress)
        packed.write_bytes(b"BAD")
        assert not rdr._valid_cache(data, sources, tool_record, manifest)
    finally:
        rdr.RPF6_TOOL = old_tool
        rdr._extract = old_extract


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lexeditor-warm-cache-55-", ignore_cleanup_errors=True) as name:
        root = Path(name)
        verify_ff8(root / "ff8")
        verify_rdr(root / "rdr")
    print("FF8 and RDR1 warm caches validate without extraction or manifest rewrites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
