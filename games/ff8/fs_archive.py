"""Read selected files from FF8's FS/FI/FL archives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import struct

from .vendor.ff8ue.lzs import Lzs


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

    def find(self, basename: str) -> ArchiveEntry:
        wanted = basename.casefold()
        matches = [entry for entry in self.entries if entry.basename == wanted]
        if len(matches) != 1:
            raise KeyError(f"Expected one {basename} entry in {self.prefix.name}; found {len(matches)}")
        return matches[0]

    def matching(self, prefix: str, suffix: str) -> list[ArchiveEntry]:
        prefix, suffix = prefix.casefold(), suffix.casefold()
        return [entry for entry in self.entries
                if entry.basename.startswith(prefix) and entry.basename.endswith(suffix)]

    def extract(self, entry: ArchiveEntry) -> bytes:
        # FL order is not storage order in field.fs. Deling and OpenVIII both
        # derive an entry's stored extent from the next greater FI offset.
        # Using the next FL row can cross backwards and reject valid entries.
        later_offsets = [candidate.offset for candidate in self.entries
                         if candidate.offset > entry.offset]
        end = min(later_offsets) if later_offsets else self.fs_path.stat().st_size
        if end <= entry.offset or (entry.compressed and end <= entry.offset + 4):
            raise ValueError(f"Invalid archive extent for {entry.name}")
        with self.fs_path.open("rb") as source:
            source.seek(entry.offset)
            if entry.compressed:
                stored_length = struct.unpack("<I", source.read(4))[0]
                payload = source.read(end - entry.offset - 4)
                if stored_length > len(payload):
                    raise ValueError(f"Stored size for {entry.name} exceeds its archive extent")
                data = bytes(Lzs().decode(payload[:stored_length]))
            else:
                # Uncompressed FI entries point straight at their bytes and do
                # not carry the four-byte compressed-length prefix.
                data = source.read(entry.unpacked_length)
        if len(data) != entry.unpacked_length:
            raise ValueError(
                f"{entry.name} decoded to {len(data)} bytes; expected {entry.unpacked_length}"
            )
        return data
