"""Prepare installed RDR editor data without writing to a game archive."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .paths import RPF6_TOOL


TUNING_ARCHIVE_RELATIVE = Path("game") / "tune_d11generic.rpf"
CONTENT_ARCHIVE_RELATIVE = Path("game") / "content.rpf"
GRINGO_ARCHIVE_RELATIVE = Path("game") / "gringores.rpf"
TUNING_CACHE_NAME = "tune_d11generic"
CONTENT_CACHE_NAME = "content"
GRINGO_PACKED_CACHE_NAME = "gringores"
GRINGO_UNPACKED_CACHE_NAME = "gringores-unpacked"
KNOWN_TUNING_XML = Path("tune") / "ai" / "motives.xml"
INVENTORY_XML = Path("content") / "init" / "inventory" / "inventory.xml"
DLC_INVENTORY_XML = Path("content") / "init" / "inventory" / "dlc_inventory.xml"
MINIMUM_FILE_COUNT = 1000
GRINGO_FILE_COUNT = 39


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _source_record(archive: Path) -> dict:
    stat = archive.stat()
    return {
        "path": str(archive.resolve()),
        "size": stat.st_size,
        "mtimeNs": stat.st_mtime_ns,
        "sha256": sha256(archive),
    }


def _valid_cache(data_root: Path, records: dict, tool: dict, manifest: dict) -> bool:
    if manifest.get("version") != 3 or manifest.get("sources") != records:
        return False
    if manifest.get("tool") != tool:
        return False
    counts = manifest.get("fileCounts", {})
    if (counts.get("tuning", 0) < MINIMUM_FILE_COUNT or counts.get("inventory") != 2
            or counts.get("gringoPacked") != GRINGO_FILE_COUNT
            or counts.get("gringoUnpacked") != GRINGO_FILE_COUNT):
        return False
    xml_targets = (
        data_root / TUNING_CACHE_NAME / KNOWN_TUNING_XML,
        data_root / CONTENT_CACHE_NAME / INVENTORY_XML,
        data_root / CONTENT_CACHE_NAME / DLC_INVENTORY_XML,
    )
    packed_wgd = data_root / GRINGO_PACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    unpacked_wgd = (
        data_root / GRINGO_UNPACKED_CACHE_NAME / "gringores" / "armadillo.wgd"
    )
    targets = (*xml_targets, packed_wgd, unpacked_wgd)
    if not all(target.is_file() for target in targets):
        return False
    try:
        for target in xml_targets:
            ET.parse(target)
        with packed_wgd.open("rb") as stream:
            if stream.read(3) != b"RSC":
                return False
        if unpacked_wgd.stat().st_size == 0:
            return False
    except (OSError, ET.ParseError):
        return False
    return True


def _extract(archive: Path, output: Path, wildcard: str, timeout: int,
             command: str = "extract") -> None:
    result = subprocess.run(
        [str(RPF6_TOOL), command, str(archive), str(output), wildcard],
        cwd=str(RPF6_TOOL.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"RPF6 extraction failed for {archive.name}: {detail}")


def _install_cache(source: Path, target: Path, data_root: Path) -> None:
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        previous = data_root / f"{target.name}.previous-{stamp}-{uuid.uuid4().hex[:8]}"
        target.replace(previous)
    source.replace(target)


def ensure_rdr_data(game_root: Path, data_root: Path, progress) -> dict:
    """Extract RDR tuning, inventory, and shop data into Lexeditor's private cache."""
    game_root = Path(game_root).resolve()
    data_root = Path(data_root).resolve()
    archives = {
        "tuning": (game_root / TUNING_ARCHIVE_RELATIVE).resolve(),
        "content": (game_root / CONTENT_ARCHIVE_RELATIVE).resolve(),
        "gringores": (game_root / GRINGO_ARCHIVE_RELATIVE).resolve(),
    }
    for label, archive in archives.items():
        if not archive.is_file():
            raise FileNotFoundError(f"Missing RDR {label} archive: {archive}")
        with archive.open("rb") as stream:
            if stream.read(4) != b"RPF6":
                raise ValueError(f"Expected an RPF6 archive: {archive}")
    if not RPF6_TOOL.is_file():
        raise FileNotFoundError(f"Missing RPF6 read-only bridge: {RPF6_TOOL}")

    data_root.mkdir(parents=True, exist_ok=True)
    manifest_path = data_root / "manifest.json"
    progress(0, 7, "Checking the installed RDR data archives…")
    sources_before = {label: _source_record(path) for label, path in archives.items()}
    tool = {
        "path": str(RPF6_TOOL),
        "sha256": sha256(RPF6_TOOL),
    }
    current_manifest = _manifest(manifest_path)
    if _valid_cache(data_root, sources_before, tool, current_manifest):
        progress(7, 7, "RDR editor data is ready")
        return current_manifest

    temporary_root = data_root / f".prepare-{uuid.uuid4().hex}"
    tuning_temporary = temporary_root / TUNING_CACHE_NAME
    content_temporary = temporary_root / CONTENT_CACHE_NAME
    gringo_packed_temporary = temporary_root / GRINGO_PACKED_CACHE_NAME
    gringo_unpacked_temporary = temporary_root / GRINGO_UNPACKED_CACHE_NAME
    temporary_root.mkdir()
    try:
        progress(1, 7, "Extracting editable RDR tuning data…")
        _extract(archives["tuning"], tuning_temporary, "**", 180)
        tuning_files = [path for path in tuning_temporary.rglob("*") if path.is_file()]
        if len(tuning_files) < MINIMUM_FILE_COUNT:
            raise RuntimeError(
                f"RPF6 tuning extraction returned only {len(tuning_files)} files; "
                f"expected at least {MINIMUM_FILE_COUNT}."
            )
        ET.parse(tuning_temporary / KNOWN_TUNING_XML)

        progress(2, 7, "Extracting RDR inventory definitions…")
        _extract(archives["content"], content_temporary, "*inventory.xml", 60)
        inventory_files = [path for path in content_temporary.rglob("*") if path.is_file()]
        expected_inventory = (
            content_temporary / INVENTORY_XML,
            content_temporary / DLC_INVENTORY_XML,
        )
        if len(inventory_files) != 2 or not all(path.is_file() for path in expected_inventory):
            raise RuntimeError(
                "RPF6 content extraction did not return the two inventory XML files."
            )
        for target in expected_inventory:
            ET.parse(target)

        progress(3, 7, "Extracting packed RDR shop dictionaries…")
        _extract(archives["gringores"], gringo_packed_temporary, "**/*.wgd", 60)
        gringo_packed = [path for path in gringo_packed_temporary.rglob("*.wgd")]
        if len(gringo_packed) != GRINGO_FILE_COUNT:
            raise RuntimeError(
                f"RPF6 shop extraction returned {len(gringo_packed)} dictionaries; "
                f"expected {GRINGO_FILE_COUNT}."
            )

        progress(4, 7, "Unpacking editable RDR shop dictionaries…")
        _extract(
            archives["gringores"], gringo_unpacked_temporary,
            "**/*.wgd", 60, command="unpack",
        )
        gringo_unpacked = [path for path in gringo_unpacked_temporary.rglob("*.wgd")]
        if len(gringo_unpacked) != GRINGO_FILE_COUNT:
            raise RuntimeError(
                f"RPF6 shop unpack returned {len(gringo_unpacked)} dictionaries; "
                f"expected {GRINGO_FILE_COUNT}."
            )

        progress(5, 7, "Verifying the installed archives stayed unchanged…")
        sources_after = {label: _source_record(path) for label, path in archives.items()}
        if sources_after != sources_before:
            raise RuntimeError("An installed RDR archive changed during preparation.")

        _install_cache(tuning_temporary, data_root / TUNING_CACHE_NAME, data_root)
        _install_cache(content_temporary, data_root / CONTENT_CACHE_NAME, data_root)
        _install_cache(
            gringo_packed_temporary, data_root / GRINGO_PACKED_CACHE_NAME, data_root)
        _install_cache(
            gringo_unpacked_temporary, data_root / GRINGO_UNPACKED_CACHE_NAME, data_root)
        payload = {
            "version": 3,
            "preparedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": sources_before,
            "tool": tool,
            "fileCounts": {
                "tuning": len(tuning_files),
                "inventory": len(inventory_files),
                "gringoPacked": len(gringo_packed),
                "gringoUnpacked": len(gringo_unpacked),
            },
            "caches": {
                "tuning": str(data_root / TUNING_CACHE_NAME),
                "content": str(data_root / CONTENT_CACHE_NAME),
                "gringores": str(data_root / GRINGO_PACKED_CACHE_NAME),
                "gringoresUnpacked": str(data_root / GRINGO_UNPACKED_CACHE_NAME),
            },
        }
        manifest_temporary = manifest_path.with_suffix(".json.tmp")
        manifest_temporary.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(manifest_temporary, manifest_path)
        progress(
            7, 7,
            f"Prepared {len(tuning_files)} tuning files, 2 inventory files, "
            f"and {len(gringo_unpacked)} shop dictionaries",
        )
        return payload
    finally:
        if temporary_root.exists():
            shutil.rmtree(temporary_root)
