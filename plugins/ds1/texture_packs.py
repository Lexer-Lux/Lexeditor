"""PC TPF textures merged by name, preserving metadata and DDS payload bytes.

The PC header is 16 bytes, with 20-byte texture records. Layout reference:
SoulsFormats/Formats/TPF/TPF.cs (GPL-3.0), Read and Texture.WriteHeader.
Console headers, optional float records and per-texture compression are
intentionally refused rather than guessed or reconstructed as PC data.
"""
from dataclasses import dataclass
import struct

from .formats import FormatError
from .assets import MAX_ASSET_BYTES


@dataclass(frozen=True)
class Texture:
    name: str
    encoded_name: bytes
    metadata: bytes
    data: bytes


def read(data):
    """Return archive metadata and ordered, uniquely named PC texture records."""
    if not 16 <= len(data) <= MAX_ASSET_BYTES or data[:4] != b'TPF\0':
        raise FormatError('Expected a PC TPF texture pack')
    count = struct.unpack_from('<I', data, 8)[0]
    if data[12] != 0 or data[13] not in (0, 1, 2, 3) or data[14] not in (0, 1, 2) or data[15]:
        raise FormatError('Unsupported TPF platform or archive metadata')
    end = 16 + count * 20
    if count > 10000 or end > len(data):
        raise FormatError('Invalid TPF texture count or table')
    encoding = 'utf-16-le' if data[14] == 1 else 'shift_jis'
    width = 2 if data[14] == 1 else 1
    entries, names, spans = [], set(), []
    for index in range(count):
        at = 16 + index * 20
        offset, size = struct.unpack_from('<II', data, at)
        metadata = bytes(data[at + 8:at + 12])
        name_at, extra = struct.unpack_from('<II', data, at + 12)
        if extra or metadata[1] not in (0, 1, 2) or metadata[3] not in (0, 1):
            raise FormatError('Unsupported TPF texture metadata or compression')
        if offset < end or size < 128 or offset + size > len(data) or data[offset:offset + 4] != b'DDS ':
            raise FormatError('Invalid TPF DDS payload bounds or signature')
        if not end <= name_at < len(data) or (width == 2 and name_at % 2):
            raise FormatError('Invalid TPF texture name offset')
        name_end = name_at
        limit = min(len(data), name_at + 512 * width)
        while name_end + width <= limit and data[name_end:name_end + width] != b'\0' * width:
            name_end += width
        if name_end == name_at or name_end + width > limit:
            raise FormatError('Missing or unterminated TPF texture name')
        encoded = bytes(data[name_at:name_end])
        try:
            name = encoded.decode(encoding)
        except UnicodeError as error:
            raise FormatError('Invalid TPF texture name encoding') from error
        if name in names:
            raise FormatError(f'Duplicate TPF texture name: {name}')
        names.add(name)
        spans.append((offset, offset + size, 'pixels'))
        spans.append((name_at, name_end + width, 'name'))
        entries.append(Texture(name, encoded, metadata, bytes(data[offset:offset + size])))
    # Sharing a name string or identical pixel span is harmless; partial
    # overlaps or a name stored inside pixels cannot be safely rebuilt.
    ordered = sorted(set(spans))
    for previous, current in zip(ordered, ordered[1:]):
        if previous[1] > current[0]:
            raise FormatError('Overlapping TPF names or texture payloads')
    return bytes(data[12:16]), entries


def write(header, textures):
    """Relocate directory offsets; never decode or re-encode DDS pixels."""
    if len(textures) > 10000:
        raise FormatError('Combined TPF names too many textures')
    width = 2 if header[2] == 1 else 1
    size = 16 + 20 * len(textures) + sum(len(row.encoded_name) + width for row in textures)
    for row in textures:
        size = (size + 15) // 16 * 16 + len(row.data)
    if size > MAX_ASSET_BYTES:
        raise FormatError('Combined TPF exceeds the texture pack size limit')
    result = bytearray(b'TPF\0' + b'\0' * 8 + header)
    struct.pack_into('<I', result, 8, len(textures))
    result.extend(b'\0' * (20 * len(textures)))
    for index, texture in enumerate(textures):
        struct.pack_into('<I', result, 16 + index * 20 + 12, len(result))
        result.extend(texture.encoded_name + b'\0' * width)
    start = len(result)
    for index, texture in enumerate(textures):
        result.extend(b'\0' * (-len(result) % 16))
        at = 16 + index * 20
        struct.pack_into('<II', result, at, len(result), len(texture.data))
        result[at + 8:at + 12] = texture.metadata
        result.extend(texture.data)
    # The shared DS1 DCX reader requires at least 32 uncompressed bytes.
    # Keep an empty directory valid in that wrapper as well.
    if not textures:
        result.extend(b'\0' * 16)
    struct.pack_into('<I', result, 4, len(result) - start)
    return bytes(result)


def merge(original, variants, *, conflicts_only=False):
    """Independent additions, edits and deletions; last owner wins collisions."""
    header, base_rows = read(original)
    base = {entry.name: entry for entry in base_rows}
    result, owners, conflicts = dict(base), {}, {}
    for owner, payload in variants:
        metadata, rows = read(payload)
        if metadata != header:
            raise FormatError(f'{owner}: TPF archive metadata differs from vanilla')
        theirs = {entry.name: entry for entry in rows}
        for name in base.keys() | theirs.keys():
            entry = theirs.get(name)
            if entry == base.get(name):
                continue
            claims = owners.setdefault(name, [])
            claims.append((owner, entry))
            if any(previous != entry for _, previous in claims):
                conflicts[name] = list(dict.fromkeys(mod for mod, _ in claims))
            elif name in conflicts:
                conflicts[name] = list(dict.fromkeys(mod for mod, _ in claims))
            if entry is None:
                result.pop(name, None)
            else:
                result[name] = entry
    ordered = [result[entry.name] for entry in base_rows if entry.name in result]
    ordered.extend(result[name] for name in sorted(result.keys() - base.keys()))
    if result == base or conflicts_only:
        return original, conflicts
    return write(header, ordered), conflicts
