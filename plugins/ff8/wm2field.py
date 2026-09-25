"""Read and write wm2field.tbl, the world-map to field table.

The audit in codex/ff8/editability.md lists this as a gap: the plugin had the
field-to-world direction (wmset section 9) and nothing for the other way.

Layout, read from the installed Steam release (`Data/lang-en/main.fs`, entry
`wm2field.tbl`, 1728 bytes) and matching Rinoa's Toolset's own reader
(`SerahToolkit_SharpGL/wm2field.cs`): 72 entries of 24 bytes. Each entry is a
signed 16-bit X, a signed 16-bit Y, an unsigned 16-bit Z, an unsigned 16-bit
field ID, one more byte, then fifteen bytes the other tool does not name. The
X and Y are the two words that carry values wider than a field ID, the field
ID sits in the 1..1200 range the field archive uses, and every other byte is
preserved exactly.

The game multiplies the stored coordinates by 4096 before comparing them
(`shl ecx, 0Ch` in the other tool's comments), which is why they read as small
numbers here. That scale comes from that tool, not from this plugin's own
measurement, and the editor says so.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

from . import paths, runtime_layout
from .fs_archive import FsArchive


MAIN_PREFIX = "main"
MAIN_ENTRY = "wm2field.tbl"
# FFNx reads a replacement from the direct tree by the archive entry's name.
LOGICAL_PATH = "direct/wm2field.tbl"
DIRECT_RELATIVE = Path("wm2field.tbl")
BASELINE_RELATIVE = Path("main/wm2field.tbl")
ENTRY_COUNT = 72
ENTRY_SIZE = 24
# (name, offset, struct code, readable label)
FIELDS = (("x", 0, "h"), ("y", 2, "h"), ("z", 4, "H"), ("fieldId", 6, "H"))
POINTER_OFFSET = 8
RESERVED_OFFSET = 9


def _archive_prefix() -> Path:
    return paths.GAME_ROOT / "Data" / "lang-en" / MAIN_PREFIX


def _fingerprint(prefix: Path) -> dict:
    return {
        suffix: {
            "size": prefix.with_suffix(suffix).stat().st_size,
            "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns,
        }
        for suffix in (".fs", ".fi", ".fl")
    }


def ensure_baseline() -> Path:
    """Extract wm2field.tbl once, and again when the archive changes."""
    destination = paths.BASELINE_ROOT / BASELINE_RELATIVE
    metadata = destination.with_suffix(destination.suffix + ".source.json")
    prefix = _archive_prefix()
    current = _fingerprint(prefix)
    if destination.is_file() and metadata.is_file():
        try:
            if json.loads(metadata.read_text(encoding="utf-8")) == current:
                return destination
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(prefix)
    data = archive.extract(archive.find(MAIN_ENTRY))
    parse(data)  # Reject a corrupt or unexpected entry before caching it.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    metadata.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return destination


def source_path(dataset: str = "current") -> Path:
    baseline = ensure_baseline()
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / DIRECT_RELATIVE
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference_root = paths.PROJECT_ROOT / "references" / reference_id
        candidates = (reference_root / "direct" / DIRECT_RELATIVE,
                      reference_root / DIRECT_RELATIVE)
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        if target is None:
            raise ValueError(f"wm2field.tbl is absent from reference {reference_id}")
        return target
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def parse(raw: bytes) -> dict:
    """Every entry, with the bytes it occupies so a rewrite can stay exact."""
    if len(raw) != ENTRY_COUNT * ENTRY_SIZE:
        raise ValueError(
            f"wm2field.tbl is {len(raw)} bytes; expected "
            f"{ENTRY_COUNT * ENTRY_SIZE} ({ENTRY_COUNT} entries of {ENTRY_SIZE})")
    rows = []
    for index in range(ENTRY_COUNT):
        base = index * ENTRY_SIZE
        entry = {"id": index, "token": f"wm2field:{index}"}
        for name, offset, code in FIELDS:
            entry[name] = struct.unpack_from(f"<{code}", raw, base + offset)[0]
        entry["pointer"] = raw[base + POINTER_OFFSET]
        rows.append(entry)
    return {"count": ENTRY_COUNT, "entrySize": ENTRY_SIZE, "rows": rows,
            "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a whole number") from error
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be {minimum} to {maximum}")
    return number


def apply_edits(raw: bytes, edits: list[dict]) -> bytes:
    """Write the named fields of each entry and leave every other byte alone."""
    document = parse(raw)
    known = {row["id"] for row in document["rows"]}
    data = bytearray(raw)
    seen: set[int] = set()
    for edit in edits:
        try:
            index = int(edit["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("A wm2field.tbl edit needs an id") from error
        if index not in known:
            raise ValueError(f"wm2field.tbl has no entry {index}")
        if index in seen:
            raise ValueError(f"wm2field.tbl received two edits for entry {index}")
        seen.add(index)
        values = {
            "x": _bounded(edit.get("x"), -32768, 32767, f"Entry {index} X"),
            "y": _bounded(edit.get("y"), -32768, 32767, f"Entry {index} Y"),
            "z": _bounded(edit.get("z"), 0, 65535, f"Entry {index} Z"),
            "fieldId": _bounded(edit.get("fieldId"), 0, 65535, f"Entry {index} field ID"),
        }
        base = index * ENTRY_SIZE
        for name, offset, code in FIELDS:
            struct.pack_into(f"<{code}", data, base + offset, values[name])
    return bytes(data)


def rows(dataset: str = "current") -> dict:
    path = source_path(dataset)
    raw = path.read_bytes()
    document = parse(raw)
    document["path"] = str(path)
    document["source"] = dataset
    document["mode"] = dataset
    return document


def _write(destination: Path, raw: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        # One rolling backup, like the other direct-tree writers.
        shutil.copy2(destination, destination.with_name(f"{destination.name}.bak"))
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp",
                                         dir=destination.parent)
    try:
        with open(handle, "wb", closefd=True) as stream:
            stream.write(raw)
        Path(temp_name).replace(destination)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def save(edits: list[dict]) -> dict:
    """Apply edits to the project's copy of wm2field.tbl and read it back."""
    rebuilt = apply_edits(source_path("current").read_bytes(), edits)
    _write(paths.DIRECT_ROOT / DIRECT_RELATIVE, rebuilt)
    return rows("current")
