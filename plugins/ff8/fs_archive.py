"""Read selected files from FF8's FS/FI/FL archives."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import struct

from .lzs_decode import decode_lzs


@dataclass(frozen=True)
class ArchiveEntry:
    name: str
    unpacked_length: int
    offset: int
    compressed: bool
    index: int

    @property
    def basename(self) -> str:
        return PureWindowsPath(self.name).name.casefold()


# Parsed .fl/.fi indexes, keyed by prefix plus both files' size and mtime so
# a rebuilt archive is never served stale. The Models tab opens battle.fs
# once per row without this.
_ARCHIVE_CACHE: dict[tuple, "FsArchive"] = {}


def open_archive(prefix: Path) -> "FsArchive":
    """Return the cached index for one archive triplet."""
    fl_path, fi_path = prefix.with_suffix(".fl"), prefix.with_suffix(".fi")
    try:
        fl_stat, fi_stat = fl_path.stat(), fi_path.stat()
    except OSError:
        return FsArchive(prefix)
    key = (str(prefix), fl_stat.st_size, fl_stat.st_mtime_ns,
           fi_stat.st_size, fi_stat.st_mtime_ns)
    archive = _ARCHIVE_CACHE.get(key)
    if archive is None:
        archive = _ARCHIVE_CACHE[key] = FsArchive(prefix)
    return archive


def clear_archive_cache() -> None:
    """Drop cached indexes (tests that rewrite an archive in place)."""
    _ARCHIVE_CACHE.clear()


class FsArchive:
    """One FF8 archive triplet."""

    def __init__(self, prefix: Path):
        self.prefix = prefix
        self.fs_path = prefix.with_suffix(".fs")
        self.fi_path = prefix.with_suffix(".fi")
        self.fl_path = prefix.with_suffix(".fl")
        names = self.fl_path.read_text(encoding="utf-8", errors="strict").splitlines()
        index = self.fi_path.read_bytes()
        if len(index) != len(names) * 12:
            raise ValueError(f"{self.fi_path.name} does not match {self.fl_path.name}")
        self.entries = []
        for i, name in enumerate(names):
            unpacked, offset, compression = struct.unpack_from("<III", index, i * 12)
            if compression not in (0, 1):
                raise ValueError(f"Unsupported FS compression {compression} for {name}")
            self.entries.append(ArchiveEntry(name, unpacked, offset, bool(compression), i))
        # Basename lookup and storage-order offsets, precomputed once: find()
        # and extract() run per model row.
        self._by_basename: dict[str, list[ArchiveEntry]] = {}
        for entry in self.entries:
            self._by_basename.setdefault(entry.basename, []).append(entry)
        self._sorted_offsets = sorted(entry.offset for entry in self.entries)

    def find(self, basename: str) -> ArchiveEntry:
        matches = self._by_basename.get(basename.casefold(), [])
        if len(matches) != 1:
            raise KeyError(f"Expected one {basename} entry in {self.prefix.name}; found {len(matches)}")
        return matches[0]

    def matching(self, prefix: str, suffix: str) -> list[ArchiveEntry]:
        prefix, suffix = prefix.casefold(), suffix.casefold()
        return [entry for entry in self.entries
                if entry.basename.startswith(prefix) and entry.basename.endswith(suffix)]

    def extent_end(self, entry: ArchiveEntry) -> int:
        """End of an entry's stored extent (see extract for why)."""
        position = bisect.bisect_right(self._sorted_offsets, entry.offset)
        if position < len(self._sorted_offsets):
            return self._sorted_offsets[position]
        return self.fs_path.stat().st_size

    def extract(self, entry: ArchiveEntry) -> bytes:
        # FL order is not storage order in field.fs. Deling and OpenVIII both
        # derive an entry's stored extent from the next greater FI offset.
        # Using the next FL row can cross backwards and reject valid entries.
        end = self.extent_end(entry)
        if end <= entry.offset or (entry.compressed and end <= entry.offset + 4):
            raise ValueError(f"Invalid archive extent for {entry.name}")
        with self.fs_path.open("rb") as source:
            source.seek(entry.offset)
            if entry.compressed:
                stored_length = struct.unpack("<I", source.read(4))[0]
                payload = source.read(end - entry.offset - 4)
                if stored_length > len(payload):
                    raise ValueError(f"Stored size for {entry.name} exceeds its archive extent")
                data = decode_lzs(payload[:stored_length])
            else:
                # Uncompressed FI entries point straight at their bytes and do
                # not carry the four-byte compressed-length prefix.
                data = source.read(entry.unpacked_length)
        if len(data) != entry.unpacked_length:
            raise ValueError(
                f"{entry.name} decoded to {len(data)} bytes; expected {entry.unpacked_length}"
            )
        return data
