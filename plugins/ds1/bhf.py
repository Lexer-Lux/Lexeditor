"""Split texture archives: BHF3 headers plus BDT data files.

Map and character textures too big for their binder ship separately:
a small .tpfbhd/.chrtpfbhd header names each member's offset and size
inside a huge .tpfbdt/.chrtpfbdt data file. Every member is one
DCX-compressed TPF in the same DCX the binders use. Read-only; the
huge data file is never fully loaded, members are seek-read by
(offset, size).

Header layout, probed from the game files (no public spec matched):
a 28-byte header (magic BHF307D7R6, a word at byte 16 that looks like
a member count but is not trusted, then slot 0 whose path word at byte
48 starts the string table), then dense 24-byte slots: (previous member's
size, flags 64, member size, BDT offset, index, path offset). Slots
pack from byte 28 with sequential indices; the scan takes every slot
that validates, so stray partial words can only drop a texture, never
misread the data file. A material's diffuse stem names its member
directly (m10_00_wall_01 -> m10_00_wall_01.tpf).
"""
import struct
from pathlib import Path

from .formats import MAX_ARCHIVE, FormatError, inflate

MAGIC = b'BHF307D7R6\x00\x00'
HEADER_SIZE = 28
PATH_BASE_AT = 48
SLOT_SIZE = 24
FLAGS = 64
MAX_NAME = 160
MAX_MEMBERS = 100000


class BhfError(FormatError):
    """A split texture archive (or one member) cannot be read."""


def _u32(raw, at):
    return struct.unpack_from('<I', raw, at)[0]


def parse_bhf(bhd, suffix='.tpf'):
    """Member lookup: filename-minus-.tpf, lowercased, to (BDT offset,
    size). Slots that fail any check are skipped, so a stray partial
    slot can only drop a texture, never misread the data file."""
    raw = bytes(bhd)
    if len(raw) < PATH_BASE_AT + 4 or raw[:12] != MAGIC:
        raise BhfError('That is not a split texture archive')
    path_base = _u32(raw, PATH_BASE_AT)
    if not HEADER_SIZE < path_base < len(raw):
        raise BhfError('That split texture archive names no members')
    found = {}
    for at in range(HEADER_SIZE, path_base - SLOT_SIZE + 1, SLOT_SIZE):
        _prev, flags, size, offset, index, path_off = struct.unpack_from('<6I', raw, at)
        if flags != FLAGS or not 76 < size <= MAX_ARCHIVE:
            continue
        if not 0 <= index < MAX_MEMBERS:
            continue
        if offset > 0xFFFFFFFF - size:
            continue
        if not path_base <= path_off < len(raw):
            continue
        end = raw.find(b'\x00', path_off, path_off + MAX_NAME)
        if end <= path_off:
            continue
        name = raw[path_off:end].decode('ascii', 'replace')
        if name.lower().endswith('.dcx'):
            name = name[:-4]
        stem = name.replace('\\', '/').rsplit('/', 1)[-1]
        if not stem.lower().endswith(suffix):
            continue
        stem = stem[:-len(suffix)]
        if stem:
            found.setdefault(stem.lower(), (offset, size))
    return found


def read_member(bdt, offset, size):
    """The member's bytes, seek-read; the data file stays on disk."""
    path = Path(bdt)
    try:
        total = path.stat().st_size
    except OSError as error:
        raise BhfError(f'Cannot read {path.name}') from error
    if not 76 < size <= MAX_ARCHIVE or offset + size > total:
        raise BhfError(f'{path.name} has no member there')
    try:
        with open(path, 'rb') as handle:
            handle.seek(offset)
            blob = handle.read(size)
    except OSError as error:
        raise BhfError(f'Cannot read {path.name}') from error
    if len(blob) != size:
        raise BhfError(f'{path.name} ends inside its member')
    return blob


def inflate_member(bdt, offset, size):
    """One member seek-read and inflated to its TPF."""
    try:
        return inflate(read_member(bdt, offset, size))
    except FormatError as error:
        raise BhfError(f'{Path(bdt).name} has an unreadable member: {error}') from error


def member_tpf(bhd, bdt, stem):
    """One member inflated to its TPF, or None when the archive does
    not carry that stem. Anything unreadable raises BhfError."""
    table = parse_bhf(bhd)
    slot = table.get((stem or '').lower())
    if slot is None:
        return None
    offset, size = slot
    return inflate_member(bdt, offset, size)
