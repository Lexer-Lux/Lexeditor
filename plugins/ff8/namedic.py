"""Read and write namedic.bin, the game's own list of names.

The layout is proved against the installed Steam release. In
`Data/lang-en/main.fs` the entry `namedic.bin` is 408 bytes: a 16-bit entry
count, that many 16-bit byte offsets, then one null-terminated name per entry.
The first offset equals the end of the offset table, the offsets increase, and
every name decodes with the same FF8 single-byte text encoding the kernel text
uses. The shipped 32 entries are place names (Galbadia, Esthar, Balamb, ...) and
the words the game's own text inserts (Restores, Junctions, Magic, ...).

Evidence for the writer: decoding all 32 shipped names and encoding them again
reproduces the stored bytes exactly, so a name of a different length is written
by rebuilding the offset table while every name the caller did not touch stays
byte-identical. This is the table Rinoa's Toolset edits as Namedic.bin.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

from . import kernel_text, paths, runtime_layout
from .fs_archive import FsArchive


MAIN_PREFIX = "main"
MAIN_ENTRY = "namedic.bin"
# FFNx reads a replacement from the direct tree by the archive entry's own name.
LOGICAL_PATH = "direct/namedic.bin"
DIRECT_RELATIVE = Path("namedic.bin")
BASELINE_RELATIVE = Path("main/namedic.bin")
COUNT_SIZE = 2
OFFSET_SIZE = 2
MAX_FILE_SIZE = 0xFFFF


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
    """Extract namedic.bin once, and again when the archive changes."""
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
            raise ValueError(f"namedic.bin is absent from reference {reference_id}")
        return target
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def parse(raw: bytes) -> dict:
    """One name list: its count, and each name with the bytes it occupies."""
    if len(raw) < COUNT_SIZE:
        raise ValueError("namedic.bin is too small for its entry count")
    count = struct.unpack_from("<H", raw, 0)[0]
    header_size = COUNT_SIZE + count * OFFSET_SIZE
    if count == 0 or header_size > len(raw):
        raise ValueError(f"namedic.bin declares {count} names but holds {len(raw)} bytes")
    offsets = list(struct.unpack_from(f"<{count}H", raw, COUNT_SIZE))
    if offsets[0] != header_size:
        raise ValueError(
            f"namedic.bin's first name starts at {offsets[0]}, not at the end of its "
            f"offset table ({header_size})")
    if any(left >= right for left, right in zip(offsets, offsets[1:])):
        raise ValueError("namedic.bin's name offsets are not in increasing order")
    if offsets[-1] >= len(raw):
        raise ValueError("namedic.bin's last name starts past the end of the file")
    entries = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < count else len(raw)
        payload = raw[start:end]
        terminator = payload.find(b"\x00")
        if terminator < 0:
            raise ValueError(f"namedic.bin's name {index} has no terminator")
        padding = payload[terminator + 1:]
        if any(padding):
            raise ValueError(
                f"namedic.bin's name {index} has {len(padding)} unexplained bytes "
                "after its terminator")
        entries.append({
            "index": index,
            "offset": start,
            "length": len(payload),
            "text": kernel_text.decode(payload[:terminator]),
            "padding": len(padding),
        })
    return {
        "count": count,
        "entries": entries,
        # Bytes after the last name's terminator, which are zeros. They are
        # preserved so an untouched file is written back byte-identical.
        "tail": entries[-1]["padding"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def rows(dataset: str = "current") -> dict:
    path = source_path(dataset)
    document = parse(path.read_bytes())
    document["path"] = str(path)
    document["source"] = dataset
    return document


def _entry_index(edits: list[dict], count: int) -> list[tuple[int, str]]:
    prepared: list[tuple[int, str]] = []
    seen: set[int] = set()
    for edit in edits:
        try:
            index = int(edit["index"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("A namedic.bin edit needs an index") from error
        if not 0 <= index < count:
            raise ValueError(f"namedic.bin has no name {index}")
        if index in seen:
            raise ValueError(f"namedic.bin received two edits for name {index}")
        seen.add(index)
        text = edit.get("text")
        if not isinstance(text, str):
            raise ValueError(f"namedic.bin's name {index} needs text")
        if "\x00" in text:
            raise ValueError(f"namedic.bin's name {index} cannot hold a null byte")
        prepared.append((index, text))
    return prepared


def apply_edits(raw: bytes, edits: list[dict]) -> bytes:
    """Write the names, rebuilding the offset table when a name changes length."""
    document = parse(raw)
    count = document["count"]
    texts = [entry["text"] for entry in document["entries"]]
    for index, text in _entry_index(edits, count):
        texts[index] = text
    encoded = [kernel_text.encode(text, compress=False) for text in texts]
    header_size = COUNT_SIZE + count * OFFSET_SIZE
    offsets: list[int] = []
    body = bytearray()
    position = header_size
    for payload in encoded:
        if position > MAX_FILE_SIZE:
            raise ValueError(
                f"These names need {position} bytes; namedic.bin holds 16-bit offsets")
        offsets.append(position)
        body += payload + b"\x00"
        position += len(payload) + 1
    output = bytearray(struct.pack("<H", count))
    output += struct.pack(f"<{count}H", *offsets)
    output += body
    output += b"\x00" * document["tail"]
    return bytes(output)


def _write(destination: Path, raw: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        # One rolling backup, like the other direct-tree writers: a timestamped
        # copy per save would fill the project with stale files.
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
    """Apply edits to the project's copy of namedic.bin and read it back."""
    source = source_path("current")
    rebuilt = apply_edits(source.read_bytes(), edits)
    _write(paths.DIRECT_ROOT / DIRECT_RELATIVE, rebuilt)
    return rows("current")
