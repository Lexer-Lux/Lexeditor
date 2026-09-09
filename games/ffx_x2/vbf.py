"""Read-only Virtuos Big File (VBF) archive support for FFX/X-2 HD Remaster.

The layout is implemented from the BSD-licensed ``michivi/vbf-fs`` reference.
Lexeditor never rebuilds or mutates the installed VBF archives.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import struct
import zlib


SIGNATURE = b"SRYK"
BLOCK_SIZE = 65536
HASH_SIZE = 16
MAX_FILES = 1_000_000


class VBFError(ValueError):
    """Raised when an archive violates the proved VBF layout."""


@dataclass(frozen=True)
class VBFEntry:
    path: str
    path_hash: bytes
    size: int
    offset: int
    start_block: int
    block_sizes: tuple[int, ...]

    @property
    def block_count(self) -> int:
        return len(self.block_sizes)


@dataclass(frozen=True)
class VBFIndex:
    path: Path
    header_length: int
    header_md5: str
    entries: tuple[VBFEntry, ...]

    @property
    def file_count(self) -> int:
        return len(self.entries)

    def find(self, archive_path: str) -> VBFEntry:
        wanted = normalize_archive_path(archive_path).casefold()
        matches = [entry for entry in self.entries if entry.path.casefold() == wanted]
        if not matches:
            raise FileNotFoundError(archive_path)
        if len(matches) != 1:
            raise VBFError(f"Archive contains ambiguous case-insensitive path: {archive_path}")
        return matches[0]


def normalize_archive_path(value: str) -> str:
    """Return a safe VBF-relative path using forward slashes."""
    source = str(value).replace("\\", "/")
    if source.startswith("/"):
        raise VBFError(f"Unsafe VBF path: {value!r}")
    raw = source.strip("/")
    pure = PurePosixPath(raw)
    if (not raw or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts)
            or any(":" in part for part in pure.parts)):
        raise VBFError(f"Unsafe VBF path: {value!r}")
    return "/".join(pure.parts)


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def read_index(path: Path) -> VBFIndex:
    """Parse and validate the archive header without reading the data payload."""
    path = Path(path)
    size_on_disk = path.stat().st_size
    if size_on_disk < 32:
        raise VBFError(f"VBF is too small: {path}")

    with path.open("rb") as stream:
        prefix = stream.read(16)
        if len(prefix) != 16 or prefix[:4] != SIGNATURE:
            raise VBFError(f"Invalid VBF signature: {path}")
        header_length = _u32(prefix, 4)
        file_count = _u64(prefix, 8)
        if file_count > MAX_FILES:
            raise VBFError(f"Unreasonable VBF file count: {file_count}")
        minimum = 16 + file_count * 48 + 4
        if header_length < minimum or header_length > size_on_disk - HASH_SIZE:
            raise VBFError(f"Invalid VBF header length: {header_length}")
        stream.seek(0)
        header = stream.read(header_length)
        if len(header) != header_length:
            raise VBFError("Truncated VBF header")
        stream.seek(-HASH_SIZE, 2)
        expected_header_hash = stream.read(HASH_SIZE)

    actual_header_hash = hashlib.md5(header).digest()
    if actual_header_hash != expected_header_hash:
        raise VBFError("VBF header MD5 does not match the trailing archive hash")

    cursor = 16
    hashes_end = cursor + file_count * HASH_SIZE
    path_hashes = [header[pos:pos + HASH_SIZE] for pos in range(cursor, hashes_end, HASH_SIZE)]
    cursor = hashes_end

    raw_entries: list[tuple[int, int, int, int]] = []
    for _ in range(file_count):
        if cursor + 32 > len(header):
            raise VBFError("Truncated VBF entry table")
        start_block = _u32(header, cursor)
        entry_size = _u64(header, cursor + 8)
        entry_offset = _u64(header, cursor + 16)
        name_offset = _u64(header, cursor + 24)
        raw_entries.append((start_block, entry_size, entry_offset, name_offset))
        cursor += 32

    if cursor + 4 > len(header):
        raise VBFError("Missing VBF name-table length")
    name_section_length = _u32(header, cursor)
    if name_section_length < 4:
        raise VBFError("Invalid VBF name-table length")
    name_table_length = name_section_length - 4
    cursor += 4
    if cursor + name_table_length > len(header):
        raise VBFError("Truncated VBF name table")
    name_table = header[cursor:cursor + name_table_length]
    cursor += name_table_length

    total_blocks = sum((entry_size + BLOCK_SIZE - 1) // BLOCK_SIZE for _, entry_size, _, _ in raw_entries)
    if cursor + total_blocks * 2 != header_length:
        raise VBFError("VBF block table does not end at the declared header boundary")
    block_sizes = struct.unpack_from(f"<{total_blocks}H", header, cursor) if total_blocks else ()

    entries: list[VBFEntry] = []
    seen_paths: set[str] = set()
    data_limit = size_on_disk - HASH_SIZE
    for index, ((start_block, entry_size, entry_offset, name_offset), path_hash) in enumerate(zip(raw_entries, path_hashes)):
        block_count = (entry_size + BLOCK_SIZE - 1) // BLOCK_SIZE
        if start_block + block_count > total_blocks:
            raise VBFError(f"Entry {index} references blocks outside the VBF block table")
        if name_offset >= len(name_table):
            raise VBFError(f"Entry {index} has an invalid name offset")
        nul = name_table.find(b"\0", name_offset)
        if nul < 0:
            raise VBFError(f"Entry {index} path is not NUL terminated")
        archive_path = normalize_archive_path(name_table[name_offset:nul].decode("utf-8", errors="replace"))
        folded = archive_path.casefold()
        if folded in seen_paths:
            raise VBFError(f"Duplicate VBF path: {archive_path}")
        seen_paths.add(folded)
        if entry_offset < header_length or entry_offset > data_limit:
            raise VBFError(f"Entry {archive_path} has an invalid data offset")
        entry_blocks = tuple(block_sizes[start_block:start_block + block_count])
        raw_length = 0
        for block_index, descriptor in enumerate(entry_blocks):
            remaining = entry_size - block_index * BLOCK_SIZE
            logical = min(BLOCK_SIZE, remaining)
            if descriptor == 0:
                raw_length += BLOCK_SIZE
            elif block_index == block_count - 1 and logical < BLOCK_SIZE and descriptor == logical:
                raw_length += logical
            else:
                raw_length += descriptor
        if entry_offset + raw_length > data_limit:
            raise VBFError(f"Entry {archive_path} extends beyond the VBF data section")
        entries.append(VBFEntry(
            path=archive_path,
            path_hash=path_hash,
            size=entry_size,
            offset=entry_offset,
            start_block=start_block,
            block_sizes=entry_blocks,
        ))

    return VBFIndex(path=path, header_length=header_length,
                    header_md5=actual_header_hash.hex(), entries=tuple(entries))


def read_entry(index: VBFIndex, entry: VBFEntry) -> bytes:
    """Extract and decompress one VBF entry without modifying the archive."""
    output = bytearray()
    raw_offset = entry.offset
    remaining = entry.size
    with index.path.open("rb") as stream:
        for block_index, descriptor in enumerate(entry.block_sizes):
            logical_length = min(BLOCK_SIZE, remaining)
            is_partial = (block_index == len(entry.block_sizes) - 1
                          and logical_length < BLOCK_SIZE and descriptor == logical_length)
            if descriptor == 0:
                raw_length = BLOCK_SIZE
            else:
                raw_length = descriptor
            stream.seek(raw_offset)
            raw = stream.read(raw_length)
            if len(raw) != raw_length:
                raise VBFError(f"Truncated VBF data block for {entry.path}")
            raw_offset += raw_length
            if descriptor == 0 or is_partial:
                decoded = raw[:logical_length]
            else:
                try:
                    decoded = zlib.decompress(raw)
                except zlib.error as error:
                    raise VBFError(f"Corrupt compressed VBF block for {entry.path}") from error
                if len(decoded) != logical_length:
                    raise VBFError(
                        f"Unexpected decompressed block length for {entry.path}: "
                        f"{len(decoded)} != {logical_length}"
                    )
            output.extend(decoded)
            remaining -= logical_length
    if len(output) != entry.size:
        raise VBFError(f"Extracted size mismatch for {entry.path}")
    return bytes(output)


def extract_to(index: VBFIndex, entry: VBFEntry, target: Path) -> dict:
    """Write one extracted entry atomically, refusing to overwrite user changes."""
    target = Path(target)
    data = read_entry(index, entry)
    digest = hashlib.sha256(data).hexdigest()
    if target.exists():
        if not target.is_file():
            raise VBFError(f"Project target is not a file: {target}")
        existing = hashlib.sha256(target.read_bytes()).hexdigest()
        if existing != digest:
            raise FileExistsError(f"Project file already contains edits: {target}")
        return {"path": str(target), "sha256": digest, "bytes": len(data), "created": False}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(target), "sha256": digest, "bytes": len(data), "created": True}
