"""Lossless TAG0 item resizing, retaining the file's type declarations.

Havok references in DATA are item indices. ITEM records locate those items;
PTCH records locate the reference slots that Havok fixes up when loading.
Moving an array therefore updates both tables, not the referenced indices.
"""
import bisect
import struct

from . import hkx


def _section(signature, payload, *, container=False):
    size = len(payload) + 8
    if size > hkx.MAX_FILE:
        raise hkx.HkxError('The edited Havok file is too large')
    return struct.pack('>I', size | (0 if container else 0x40000000)) + signature.encode('ascii') + payload


def replace_items(source, replacements, patches=()):
    """Resize primitive arrays and patch scalar fields without losing metadata.

    replacements maps item indices to (payload bytes, element count). patches
    contains (absolute source offset, payload bytes). Items containing Havok
    references cannot be resized here: their object layout must stay intact.
    """
    source = bytes(source)
    if len(source) > hkx.MAX_FILE:
        raise hkx.HkxError('The Havok file is too large')
    entries = hkx._peek_tables(source)
    root, end = hkx._section(source, 0)
    if end != len(source):
        raise hkx.HkxError('The Havok file has trailing data')
    data_section = next(part for part in root['subs'] if part['sig'] == 'DATA')
    data_start = data_section['pos']
    data_end = data_start + data_section['length']
    indices = sorted((i for i, entry in enumerate(entries) if entry['type'] is not None),
                     key=lambda i: entries[i]['pos'])
    starts = [entries[i]['pos'] for i in indices]
    if len(starts) != len(set(starts)):
        raise hkx.HkxError('Havok items overlap')
    stops = starts[1:] + [data_end]
    extents = {i: (start, stop) for i, start, stop in zip(indices, starts, stops)}
    changed = {}
    for index, (payload, count) in replacements.items():
        if type(index) is not int or index not in extents or type(count) is not int or count < 0:
            raise hkx.HkxError('The edited Havok item is invalid')
        kind = entries[index]['type']
        element = kind
        while element.kind == hkx.ARRAY and element.fixed:
            element = element.resolve_subtype()
        if element.kind not in (hkx.FLOAT, hkx.INT, hkx.BOOL):
            raise hkx.HkxError('Only primitive Havok arrays can be resized')
        payload = bytes(payload)
        if len(payload) != count * kind.resolve_size() or len(payload) > hkx.MAX_ITEM_BYTES:
            raise hkx.HkxError('The edited Havok array has an invalid size')
        changed[index] = (payload, count)
    patched = bytearray(source)
    for at, payload in patches:
        slot = bisect.bisect_right(starts, at) - 1
        if slot < 0 or not isinstance(payload, bytes) or at + len(payload) > stops[slot]:
            raise hkx.HkxError('An edited Havok field leaves its item')
        if indices[slot] in changed:
            raise hkx.HkxError('A Havok item cannot be resized and patched together')
        patched[at:at+len(payload)] = payload

    data = bytearray(source[data_start:starts[0]])
    offsets = {}
    for index in indices:
        start, stop = extents[index]
        data += bytes((-len(data)) % 16)
        offsets[index] = len(data)
        payload = changed[index][0] if index in changed else patched[start:stop]
        data += payload or bytes(16)
    data += bytes((-len(data)) % 16)
    if len(data) > hkx.MAX_FILE:
        raise hkx.HkxError('The edited Havok file is too large')

    def relocate(relative):
        absolute = data_start + relative
        slot = bisect.bisect_right(starts, absolute) - 1
        if slot < 0 or absolute + 4 > stops[slot]:
            raise hkx.HkxError('A Havok patch reference leaves its item')
        index = indices[slot]
        if index in changed:
            raise hkx.HkxError('A resized Havok array contains object references')
        return offsets[index] + absolute - starts[slot]

    sections = []
    for section in root['subs']:
        payload = source[section['pos']:section['pos']+section['length']]
        if section['sig'] == 'DATA':
            payload = bytes(data)
        elif section['sig'] == 'INDX':
            children = []
            for child in section['subs']:
                content = bytearray(source[child['pos']:child['pos']+child['length']])
                if child['sig'] == 'ITEM':
                    if len(content) != len(entries) * 12:
                        raise hkx.HkxError('The Havok item table has an invalid size')
                    for index in indices:
                        count = changed[index][1] if index in changed else entries[index]['count']
                        struct.pack_into('<II', content, index*12+4, offsets[index], count)
                elif child['sig'] == 'PTCH':
                    at = 0
                    while at < len(content):
                        if at + 8 > len(content):
                            raise hkx.HkxError('The Havok patch table ends early')
                        count, = struct.unpack_from('<I', content, at+4)
                        at += 8
                        if count > (len(content)-at)//4:
                            raise hkx.HkxError('The Havok patch table ends early')
                        for _ in range(count):
                            old, = struct.unpack_from('<I', content, at)
                            struct.pack_into('<I', content, at, relocate(old))
                            at += 4
                children.append(_section(child['sig'], bytes(content)))
            payload = b''.join(children)
        sections.append(_section(section['sig'], payload, container=bool(section['subs'])))
    result = _section('TAG0', b''.join(sections), container=True)
    hkx._peek_tables(result)
    return result
