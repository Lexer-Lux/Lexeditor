"""DSR split collision binders: preserve identity, combine edited HKX records.

The BXF3 directory layout follows the public format described by SoulsFormats
(Formats/Binder/BXF3 and BinderFileHeader). No upstream code is included.
"""
import re
import struct
from pathlib import Path

from . import collision_merge
from .formats import FormatError

MAX_BYTES = 256 * 1024 * 1024
MAX_MEMBERS = 100000
MAX_HEADER = 8 * 1024 * 1024


def header_for(relative):
    relative = Path(relative)
    if (len(relative.parts) == 3 and relative.parts[0] == 'map'
            and re.fullmatch(r'm\d\d_\d\d_\d\d_\d\d', relative.parts[1])
            and re.fullmatch(r'[hl]\d\d_\d\d_\d\d_\d\d\.hkx(?:bhd|bdt)', relative.name)
            and relative.stem[1:] == relative.parts[1][1:]):
        return relative.with_suffix('.hkxbhd')
    return None


def pair(relative):
    header = header_for(relative)
    return (header, header.with_suffix('.hkxbdt')) if header is not None else (relative,)


class CollisionArchive:
    def __init__(self, header, body):
        if (len(header) < 32 or len(header) > MAX_HEADER or header[:4] != b'BHF3'
                or header[12:16] != b'\x74\0\0\0' or any(header[20:32])
                or len(body) < 16 or len(body) > MAX_BYTES or body[:4] != b'BDF3'
                or body[4:12] != header[4:12] or any(body[12:16])):
            raise FormatError('Unsupported split collision archive header')
        count, = struct.unpack_from('<I', header, 16)
        if not 0 < count <= MAX_MEMBERS or 32 + count*24 > len(header):
            raise FormatError('Invalid split collision member count')
        self.header, self.body = bytes(header), bytes(body)
        self.members = {}
        intervals = []
        for i in range(count):
            at = 32 + i*24
            flags, size, offset, member_id, path_at, unpacked_size = struct.unpack_from('<6I', header, at)
            if (flags != 64 or not 0 < size <= MAX_BYTES or size != unpacked_size
                    or offset < 16 or offset+size > len(body) or not 32+count*24 <= path_at < len(header)):
                raise FormatError('Invalid split collision member bounds')
            end = header.find(b'\0', path_at, min(len(header), path_at+1024))
            if end < 0:
                raise FormatError('Unterminated split collision member name')
            try:
                name = header[path_at:end].decode('shift_jis')
            except UnicodeDecodeError:
                raise FormatError('Invalid split collision member name') from None
            leaf = name.replace('\\', '/').rsplit('/', 1)[-1].lower()
            stem = leaf.removesuffix('.dcx').removesuffix('.hkx')
            if not leaf.removesuffix('.dcx').endswith('.hkx') or not re.fullmatch(r'[hl][a-z0-9_]+', stem):
                raise FormatError('Unsupported split collision member name')
            if stem in self.members:
                raise FormatError('Duplicate split collision member identity')
            self.members[stem] = {'at': at, 'offset': offset, 'size': size,
                                  'id': member_id, 'name': name}
            intervals.append((offset, offset+size))
        intervals.sort()
        if any(first[1] > second[0] for first, second in zip(intervals, intervals[1:])):
            raise FormatError('Split collision members overlap')

    def member(self, name):
        entry = self.members[name]
        return self.body[entry['offset']:entry['offset']+entry['size']]

    def identities(self):
        return tuple((key, row['id'], row['name']) for key, row in self.members.items())

    def replace(self, updates):
        if any(name not in self.members for name in updates):
            raise FormatError('Unknown split collision member')
        if all(self.member(name) == value for name, value in updates.items()):
            return self.header, self.body
        header, body = bytearray(self.header), bytearray(self.body[:16])
        for name, entry in self.members.items():
            payload = updates.get(name, self.member(name))
            if not payload or len(payload) > MAX_BYTES:
                raise FormatError('Collision member is too large or empty')
            body += bytes((-len(body)) % 16)
            offset = len(body)
            if offset + len(payload) > MAX_BYTES:
                raise FormatError('Split collision archive is too large')
            body += payload
            struct.pack_into('<II', header, entry['at']+4, len(payload), offset)
            struct.pack_into('<I', header, entry['at']+20, len(payload))
        return bytes(header), bytes(body)


def compose(header, body, variants, *, conflicts_only=False):
    """Combine matching directory members, returning header/body and conflicts."""
    original = CollisionArchive(header, body)
    archives = []
    for name, other_header, other_body in variants:
        other = CollisionArchive(other_header, other_body)
        if other.identities() != original.identities():
            raise FormatError(f'{name}: split collision directory identities changed')
        archives.append((name, other))
    updates, conflicts = {}, []
    for name in original.members:
        baseline = original.member(name)
        changed = [(owner, archive.member(name)) for owner, archive in archives
                   if archive.member(name) != baseline]
        if not changed:
            continue
        output, collisions = collision_merge.merge(baseline, changed, conflicts_only=conflicts_only)
        if output != baseline:
            updates[name] = output
        conflicts += [(f'{name}: {part}', owners) for part, owners in collisions]
    result_header, result_body = original.replace(updates)
    return result_header, result_body, conflicts
