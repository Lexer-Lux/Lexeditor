"""Remastered Havok animation files (TAG0 tagfiles), read-only.

Container layout and field meanings: SoulsAssetPipeline by Meowmaritus
(GPL-3.0-or-later), Havoc/IO/Tagfile/Binary (HkBinaryTagfileReader,
HkBinaryTypeReader, HkSection) and SoulsAssetPipeline/Animation/HKX
(HKX.GenFakeFromTagFile) at commit d11caf9 (2026-05-19):
https://github.com/Meowmaritus/SoulsAssetPipeline
The spline sampler follows its SplineCompressedAnimation, itself
adapted from HavokLib by PredatorCZ (GPL-3.0-or-later):
https://github.com/PredatorCZ/HavokLib
No upstream code is redistributed: this is a from-scratch reader of
the same layout.
"""
import math
import struct

from .formats import FormatError

# Object-count ceilings no real game file reaches; corrupt counts stop here.
MAX_FILE = 64 * 1024 * 1024
MAX_COUNT = 65536
# One item's byte extent is a different quantity: a long motion packs its
# whole spline curve set into a single hkUint8 blob, and the game ships
# blobs near 500 KiB, so the flat object count cannot gate them.
MAX_ITEM_BYTES = 1024 * 1024
# The sampler only blends curves up to this degree.
MAX_SPLINE_DEGREE = 4
SDK_VERSIONS = frozenset({'20150100', '20160100', '20160200', '20180100', '20190100'})
MAX_DEPTH = 100

VOID, OPAQUE, BOOL, STRING, INT, FLOAT, PTR, CLASS, ARRAY = range(9)

FLAG_FORMAT = 1
FLAG_SUBTYPE = 2
FLAG_VERSION = 4
FLAG_SIZE = 8
FLAG_UNKNOWN = 16
FLAG_FIELDS = 32
FLAG_INTERFACES = 64


class HkxError(FormatError):
    """A Havok file Lexeditor cannot safely read."""


def _u8(data, off):
    if not 0 <= off < len(data):
        raise HkxError('A Havok file ends early')
    return data[off], off + 1


def _i32(data, off):
    if not 0 <= off <= len(data) - 4:
        raise HkxError('A Havok file ends early')
    return struct.unpack_from('<i', data, off)[0], off + 4


def _u32(data, off):
    if not 0 <= off <= len(data) - 4:
        raise HkxError('A Havok file ends early')
    return struct.unpack_from('<I', data, off)[0], off + 4


def _section(data, off):
    """One TAG0 section: big-endian size word, 4-letter signature, then
    subsections when the top two flag bits are clear, else raw bytes."""
    if not 0 <= off <= len(data) - 8:
        raise HkxError('A Havok section is out of bounds')
    flags = struct.unpack_from('>I', data, off)[0]
    try:
        sig = data[off + 4:off + 8].decode('ascii')
    except UnicodeDecodeError:
        raise HkxError('A Havok section has no signature') from None
    pos = off + 8
    length = (flags & 0x3FFFFFFF) - 8
    if length < 0 or pos + length > len(data):
        raise HkxError('A Havok section runs past the end')
    subs = []
    if not flags & 0xC0000000:
        cursor = pos
        while cursor < pos + length:
            sub, cursor = _section(data, cursor)
            subs.append(sub)
        if cursor != pos + length:
            raise HkxError('A Havok section has a ragged end')
    return {'sig': sig, 'pos': pos, 'length': length, 'subs': subs}, pos + length


def _packed(data, off):
    """Havok's packed integer: 1 to 9 bytes, length in the top bits."""
    first, off = _u8(data, off)
    if not first & 0x80:
        return first, off
    head = first >> 3
    if 0x10 <= head <= 0x17:
        second, off = _u8(data, off)
        return ((first << 8) | second) & 0x3FFF, off
    if 0x18 <= head <= 0x1B:
        if not 0 <= off <= len(data) - 2:
            raise HkxError('A Havok file ends early')
        raw = (first << 16) | (data[off] << 8) | data[off + 1]
        return raw & 0x1FFFFF, off + 2
    if head == 0x1C:
        if not 0 <= off <= len(data) - 3:
            raise HkxError('A Havok file ends early')
        raw = (first << 24) | (data[off] << 16) | (data[off + 1] << 8) | data[off + 2]
        return raw & 0x7FFFFFF, off + 3
    if head in (0x1D, 0x1E):
        if not 0 <= off <= len(data) - 4:
            raise HkxError('A Havok file ends early')
        raw = (int(first) << 32) | (data[off] << 24) | (data[off + 1] << 16) \
            | (data[off + 2] << 8) | data[off + 3]
        return raw & 0x7FFFFFFFFFFFFFF, off + 4
    if head == 0x1F:
        if first & 7 == 0:
            if not 0 <= off <= len(data) - 5:
                raise HkxError('A Havok file ends early')
            raw = (int(first) << 40) | (data[off] << 32) | (data[off + 1] << 24) \
                | (data[off + 2] << 16) | (data[off + 3] << 8) | data[off + 4]
            return raw & 0xFFFFFFFFFF, off + 5
        if first & 7 == 1:
            if not 0 <= off <= len(data) - 8:
                raise HkxError('A Havok file ends early')
            raw = int.from_bytes(data[off:off + 8], 'big')
            return raw, off + 8
    raise HkxError('A Havok packed integer has an unknown form')


def _cstr(data, off, end):
    stop = data.find(b'\0', off, end)
    if stop < 0:
        raise HkxError('A Havok string is unterminated')
    return data[off:stop].decode('utf-8', 'replace'), stop + 1


class _Type:
    __slots__ = ('name', 'parent', 'flags', 'format_info', 'subtype',
                 'version', 'byte_size', 'align', 'fields')

    def __init__(self):
        self.name = ''
        self.parent = None
        self.flags = 0
        self.format_info = 0
        self.subtype = None
        self.version = 0
        self.byte_size = 0
        self.align = 0
        self.fields = []

    def info(self):
        if self.flags & FLAG_FORMAT or self.parent is None:
            return self.format_info
        return self.parent.info()

    @property
    def kind(self):
        return self.info() & 0xF

    @property
    def signed(self):
        return self.kind in (BOOL, INT) and bool(self.info() & 0x200)

    @property
    def bits(self):
        return self.info() >> 10 if self.kind in (BOOL, INT) else 0

    @property
    def fixed(self):
        return self.kind in (STRING, ARRAY) and bool(self.info() & 0x20)

    @property
    def fixed_size(self):
        if not self.fixed:
            return 0
        return self.info() >> 16 if self.kind == STRING else self.info() >> 8

    def float_kind(self):
        code = self.info() >> 8
        if code == 0x746:
            return 'half'
        if code == 0x1746:
            return 'single'
        if code == 0x345E:
            return 'double'
        raise HkxError('A Havok float has an unknown width')

    def resolve_subtype(self):
        seen, lineage = self, {id(self)}
        while True:
            if seen.flags & FLAG_SUBTYPE or seen.parent is None:
                return seen.subtype
            if id(seen.parent) in lineage:
                raise HkxError('Havok types loop back on themselves')
            lineage.add(id(seen.parent))
            seen = seen.parent

    def resolve_size(self):
        seen, lineage = self, {id(self)}
        while True:
            if seen.flags & FLAG_SIZE or seen.parent is None:
                return seen.byte_size
            if id(seen.parent) in lineage:
                raise HkxError('Havok types loop back on themselves')
            lineage.add(id(seen.parent))
            seen = seen.parent

    def all_fields(self):
        if self.parent is None:
            return list(self.fields)
        return self.parent.all_fields() + self.fields


def _read_types(data, section):
    """The TYPE section: type and field string pools, type names, then
    one body per type (parent, flags, format, subtype, size, fields)."""
    type_names, field_names, types = [], [], []
    bodies = None
    for sub in section['subs']:
        if sub['sig'] in ('TPTR', 'TPAD'):
            continue
        if sub['sig'] in ('TSTR', 'TST1'):
            off, end = sub['pos'], sub['pos'] + sub['length']
            while off < end:
                text, off = _cstr(data, off, end)
                type_names.append(text)
        elif sub['sig'] in ('TNAM', 'TNA1'):
            off = sub['pos']
            count, off = _packed(data, off)
            if count > MAX_COUNT:
                raise HkxError('A Havok file names too many types')
            types = [_Type() for _ in range(count)]
            for entry in types:
                name_at, off = _packed(data, off)
                entry.name = type_names[name_at]
                params, off = _packed(data, off)
                if params >= 0x40:
                    params &= 0x3F
                for _ in range(params):
                    template_at, off = _packed(data, off)
                    # A template starting with 't' is a type index and
                    # anything else a number; neither is read further.
                    if type_names[template_at].startswith('t'):
                        _, off = _packed(data, off)
                    else:
                        _, off = _packed(data, off)
        elif sub['sig'] in ('FSTR', 'FST1'):
            off, end = sub['pos'], sub['pos'] + sub['length']
            while off < end:
                text, off = _cstr(data, off, end)
                field_names.append(text)
        elif sub['sig'] in ('TBOD', 'TBDY'):
            bodies = sub
        elif sub['sig'] == 'THSH':
            off = sub['pos']
            count, off = _packed(data, off)
            if count > MAX_COUNT:
                raise HkxError('A Havok file names too many hashes')
            for _ in range(count):
                _, off = _packed(data, off)
                _, off = _i32(data, off)
        else:
            raise HkxError(f'A Havok type section holds {sub["sig"]}')
    if bodies is None:
        raise HkxError('A Havok file has no type bodies')

    def index(off, given=-1):
        at, stepped = (given, off) if given >= 0 else _packed(data, off)
        if at == 0:
            return None, stepped
        if not 1 <= at <= len(types):
            raise HkxError('A Havok type index is out of range')
        return types[at - 1], stepped

    off, end = bodies['pos'], bodies['pos'] + bodies['length']
    while off < end:
        entry, off = index(off)
        if entry is None:
            continue
        entry.parent, off = index(off)
        entry.flags, off = _packed(data, off)
        if entry.flags & FLAG_FORMAT:
            entry.format_info, off = _packed(data, off)
        if entry.flags & FLAG_SUBTYPE:
            entry.subtype, off = index(off)
        if entry.flags & FLAG_VERSION:
            entry.version, off = _packed(data, off)
        if entry.flags & FLAG_SIZE:
            entry.byte_size, off = _packed(data, off)
            entry.align, off = _packed(data, off)
        if entry.flags & FLAG_UNKNOWN:
            _, off = _packed(data, off)
        if entry.flags & FLAG_FIELDS:
            first, off = _u8(data, off)
            if first == 0xC3:
                first, off = _u8(data, off)
                if first == 0:
                    first, off = _packed(data, off)
            for _ in range(first & 0x3F):
                name_at, off = _packed(data, off)
                _, off = _packed(data, off)
                field_off, off = _packed(data, off)
                field_at, off = _packed(data, off)
                field_type, _ = index(0, field_at)
                entry.fields.append({'name': field_names[name_at], 'offset': field_off,
                                     'type': field_type})
        if entry.flags & FLAG_INTERFACES:
            count, off = _packed(data, off)
            if count > MAX_COUNT:
                raise HkxError('A Havok type names too many interfaces')
            for _ in range(count):
                _, off = index(off)
                _, off = _packed(data, off)
    return types


class _TagReader:
    """Typed objects over the DATA bytes. Items name one type, one
    offset and one count; pointers and arrays name items by index."""

    def __init__(self, data, data_off, types, items):
        self.data = data
        self.data_off = data_off
        self.types = types
        self.items = items
        self.cache = {}

    def item_objects(self, at):
        if at not in self.cache:
            entry = self.items[at]
            found = []
            for num in range(entry['count']):
                off = entry['pos'] + num * entry['type'].resolve_size()
                found.append(self._value(entry['type'], off, 0)[0])
            self.cache[at] = found
        return self.cache[at]

    def _item_index(self, off):
        at, off = _i32(self.data, off)
        if not 0 <= at < len(self.items):
            raise HkxError('A Havok item index is out of range')
        if at == 0:
            return None, off
        return self.item_objects(at), off

    def _value(self, kind, off, depth):
        if depth > MAX_DEPTH:
            raise HkxError('A Havok object nests too deep')
        data = self.data
        form = kind.kind
        if form in (VOID, OPAQUE):
            return None, off
        if form == BOOL:
            bits = kind.bits
            if bits == 8:
                value, off = _u8(data, off)
                return value != 0, off
            if bits == 16:
                if not 0 <= off <= len(data) - 2:
                    raise HkxError('A Havok file ends early')
                return struct.unpack_from('<h', data, off)[0] != 0, off + 2
            if bits == 32:
                value, off = _i32(data, off)
                return value != 0, off
            if bits == 64:
                if not 0 <= off <= len(data) - 8:
                    raise HkxError('A Havok file ends early')
                return struct.unpack_from('<q', data, off)[0] != 0, off + 8
            raise HkxError('A Havok boolean has an unknown width')
        if form == STRING:
            if kind.fixed:
                size = kind.fixed_size
                if not 0 <= off <= len(data) - size:
                    raise HkxError('A Havok file ends early')
                raw = data[off:off + size].split(b'\0')[0]
                return raw.decode('utf-8', 'replace'), off + size
            found, off = self._item_index(off)
            if not found:
                return None, off
            raw = bytes(value & 0xFF for value in found[:-1])
            return raw.decode('utf-8', 'replace'), off
        if form == INT:
            bits, signed = kind.bits, kind.signed
            if bits not in (8, 16, 32, 64):
                raise HkxError('A Havok integer has an unknown width')
            code = {8: 'b', 16: 'h', 32: 'i', 64: 'q'}[bits] if signed else \
                {8: 'B', 16: 'H', 32: 'I', 64: 'Q'}[bits]
            size = bits // 8
            if not 0 <= off <= len(data) - size:
                raise HkxError('A Havok file ends early')
            return struct.unpack_from('<' + code, data, off)[0], off + size
        if form == FLOAT:
            wide = kind.float_kind()
            if wide == 'half':
                if not 0 <= off <= len(data) - 2:
                    raise HkxError('A Havok file ends early')
                return struct.unpack_from('<e', data, off)[0], off + 2
            if wide == 'single':
                if not 0 <= off <= len(data) - 4:
                    raise HkxError('A Havok file ends early')
                return struct.unpack_from('<f', data, off)[0], off + 4
            if not 0 <= off <= len(data) - 8:
                raise HkxError('A Havok file ends early')
            return struct.unpack_from('<d', data, off)[0], off + 8
        if form == PTR:
            found, off = self._item_index(off)
            if not found:
                return None, off
            return found[0], off
        if form == CLASS:
            out = {'__class__': kind.name}
            for field in kind.all_fields():
                out[field['name']], _ = self._value(field['type'], off + field['offset'],
                                                    depth + 1)
            return out, off
        if form == ARRAY:
            sub = kind.resolve_subtype()
            if not kind.fixed:
                return self._item_index(off)
            if kind.fixed_size > MAX_COUNT:
                raise HkxError('A Havok array is too long')
            return ([self._value(sub, off + num * sub.resolve_size(), depth + 1)[0]
                     for num in range(kind.fixed_size)], off)
        raise HkxError('A Havok value has an unknown shape')


def _items(data, section, data_off, data_end, types):
    found = []
    off, end = section['pos'], section['pos'] + section['length']
    while off < end:
        at, off = _i32(data, off)
        at &= 0xFFFFFF
        pos, off = _u32(data, off)
        count, off = _i32(data, off)
        if count < 0:
            raise HkxError('A Havok item count is out of range')
        if at == 0:
            found.append({'type': None, 'pos': 0, 'count': 0})
        else:
            if not 1 <= at <= len(types):
                raise HkxError('A Havok item names no type')
            kind = types[at - 1]
            extent = count * kind.resolve_size()
            if extent > MAX_ITEM_BYTES or pos + extent > data_end - data_off:
                raise HkxError('A Havok item runs past its data')
            found.append({'type': kind, 'pos': pos + data_off, 'count': count})
    return found


def _vec4(entry, what):
    if not isinstance(entry, (list, tuple)) or len(entry) != 4:
        raise HkxError(f'A Havok {what} is not four floats')
    return [float(value) for value in entry]


class _PeekUnsupported(Exception):
    """A layout the scalar peek does not map; the caller reads it fully."""


def _peek_tables(data):
    """Sections, types and item table: the same preamble a full read
    walks, kept separate so the tested full path stays untouched."""
    root, _ = _section(data, 0)
    if root['sig'] != 'TAG0':
        raise HkxError('Expected a Havok TAG0 file')
    data_off, types, items = None, None, None
    for sub in root['subs']:
        if sub['sig'] == 'SDKV':
            version = data[sub['pos']:sub['pos'] + 8].decode('ascii', 'replace')
            if version not in SDK_VERSIONS:
                raise HkxError(f'A Havok file needs SDK {version}')
        elif sub['sig'] == 'DATA':
            data_off = sub['pos']
            data_end = sub['pos'] + sub['length']
        elif sub['sig'] == 'TYPE':
            types = _read_types(data, sub)
        elif sub['sig'] == 'INDX':
            for part in sub['subs']:
                if part['sig'] == 'ITEM':
                    items = (part, types)
                elif part['sig'] != 'PTCH':
                    raise HkxError(f'A Havok index holds {part["sig"]}')
        elif sub['sig'] == 'TCRF':
            raise HkxError('A Havok file needs a type compendium it does not carry')
        else:
            raise HkxError(f'A Havok file holds {sub["sig"]}')
    if data_off is None or types is None or items is None:
        raise HkxError('A Havok file is missing its data, types or items')
    entries = _items(data, items[0], data_off, data_end, items[1])
    if len(entries) < 2:
        raise HkxError('A Havok file names no root object')
    return entries


def _peek_field(node_type, name):
    for field in node_type.all_fields():
        if field['name'] == name:
            return field
    return None


def _peek_scalar(data, field_type, off):
    """One integer or float where the full reader would walk a value."""
    form = field_type.kind
    if form == INT:
        bits, signed = field_type.bits, field_type.signed
        if bits not in (8, 16, 32, 64):
            raise HkxError('A Havok integer has an unknown width')
        code = {8: 'b', 16: 'h', 32: 'i', 64: 'q'}[bits] if signed else \
            {8: 'B', 16: 'H', 32: 'I', 64: 'Q'}[bits]
        size = bits // 8
        if not 0 <= off <= len(data) - size:
            raise HkxError('A Havok file ends early')
        return struct.unpack_from('<' + code, data, off)[0]
    if form == FLOAT:
        wide = field_type.float_kind()
        size = {'half': 2, 'single': 4, 'double': 8}[wide]
        if not 0 <= off <= len(data) - size:
            raise HkxError('A Havok file ends early')
        return struct.unpack_from('<' + {'half': 'e', 'single': 'f', 'double': 'd'}[wide],
                                  data, off)[0]
    raise _PeekUnsupported(form)


def _peek_ref(data, entries, field_type, off):
    """An object reference as (type, address, count): pointers hop to
    their item, dynamic arrays read their item index, fixed arrays and
    inline objects read in place. A null pointer is None."""
    form = field_type.kind
    if form in (PTR, ARRAY) and (form == PTR or not field_type.fixed):
        at, _ = _i32(data, off)
        if at == 0:
            return None
        if not 0 <= at < len(entries):
            raise HkxError('A Havok item index is out of range')
        target = entries[at]
        if target['type'] is None:
            return None
        return target['type'], target['pos'], target['count']
    if form == ARRAY:
        sub = field_type.resolve_subtype()
        if sub is None:
            raise _PeekUnsupported('untyped-array')
        if field_type.fixed_size > MAX_COUNT:
            raise HkxError('A Havok array is too long')
        return sub, off, field_type.fixed_size
    if form == CLASS:
        return field_type, off, 1
    if form in (VOID, OPAQUE):
        return None
    raise _PeekUnsupported(form)


def _peek_element(data, entries, ref, num):
    """One element's (type, address): pointer slots hop per element."""
    node_type, pos, _count = ref
    if node_type.kind == PTR:
        at, _ = _i32(data, pos + num * node_type.resolve_size())
        if at == 0:
            return None
        if not 0 <= at < len(entries):
            raise HkxError('A Havok item index is out of range')
        target = entries[at]
        if target['type'] is None:
            return None
        return target['type'], target['pos']
    return node_type, pos + num * node_type.resolve_size()


def peek_animation(source):
    """A motion file's headline (duration, frames) without its curves.

    The motion list only names files; parsing every track array to
    list them wedged the Animations tab for half a minute on the
    player's binder. The peek walks to the first animation object and
    reads its scalar header, never materializing an array, with the
    same header checks the full reader applies. Files with no
    animation or no binding are None, skipped like the full reader
    skips them. A file whose header is sound but whose curves are
    corrupt lists as playable and fails loudly when sampled.
    """
    try:
        if len(source) > MAX_FILE:
            raise HkxError('The Havok file is too large')
        data = bytes(source)
        entries = _peek_tables(data)
        root = entries[1]
        if root['type'] is None or root['type'].name != 'hkRootLevelContainer':
            raise HkxError('A Havok file has no animation container')
        field = _peek_field(root['type'], 'namedVariants')
        if field is None:
            return None
        variants = _peek_ref(data, entries, field['type'], root['pos'] + field['offset'])
        if variants is None:
            return None
        first, bound = None, False
        for num in range(variants[2]):
            element = _peek_element(data, entries, variants, num)
            if element is None:
                continue
            node_type, addr = element
            field = _peek_field(node_type, 'variant')
            if field is None:
                continue
            target = _peek_ref(data, entries, field['type'], addr + field['offset'])
            if target is None:
                continue
            container_type, container_addr, _ = target
            anims_field = _peek_field(container_type, 'animations')
            binds_field = _peek_field(container_type, 'bindings')
            if anims_field is None or binds_field is None:
                continue
            anims = _peek_ref(data, entries, anims_field['type'],
                              container_addr + anims_field['offset'])
            binds = _peek_ref(data, entries, binds_field['type'],
                              container_addr + binds_field['offset'])
            if binds is not None and binds[2] > 0:
                bound = True
            if first is None and anims is not None and anims[2] > 0:
                element = _peek_element(data, entries, anims, 0)
                if element is not None:
                    first = element
        if first is None or not bound:
            return None
        kind, addr = first[0].name, first[1]
        fields = {field['name']: field for field in first[0].all_fields()}

        def scalar(name, default):
            field = fields.get(name)
            if field is None:
                return default
            return _peek_scalar(data, field['type'], addr + field['offset'])

        if kind == 'hkaSplineCompressedAnimation':
            if scalar('numberOfFloatTracks', 0):
                raise HkxError('A Havok animation has float tracks, which playback does not read')
            frames = scalar('numFrames', 0)
            blocks = scalar('numBlocks', 0)
            per_block = scalar('maxFramesPerBlock', 0)
            if frames < 2 or blocks < 1 or per_block < 2:
                raise HkxError('A Havok animation has no frames to play')
            tracks = scalar('numberOfTransformTracks', 0)
            if tracks < 1:
                raise HkxError('A Havok animation names no tracks')
            if tracks > MAX_COUNT:
                raise HkxError('A Havok animation names too many tracks')
            return {'duration': float(scalar('duration', 0.0)), 'frames': frames}
        if kind == 'hkaInterleavedUncompressedAnimation':
            tracks = scalar('numberOfTransformTracks', 0)
            if tracks > MAX_COUNT:
                raise HkxError('A Havok animation names too many tracks')
            count = 0
            field = fields.get('transforms')
            if field is not None:
                ref = _peek_ref(data, entries, field['type'], addr + field['offset'])
                count = ref[2] if ref is not None else 0
            frames = count // tracks if tracks else 0
            if frames < 2 or not tracks:
                raise HkxError('A Havok animation has no frames to play')
            return {'duration': float(scalar('duration', 0.0)), 'frames': frames}
        raise HkxError(f'A Havok animation is {kind}, which playback does not read')
    except _PeekUnsupported:
        raise
    except HkxError:
        raise
    except RecursionError:
        raise HkxError('Havok types loop back on themselves') from None
    except (IndexError, struct.error, UnicodeDecodeError,
            ValueError, TypeError, KeyError, AttributeError,
            MemoryError) as error:
        raise HkxError(f'A Havok file is malformed: {error}') from error


def _skeleton(node):
    bones = [{'name': bone.get('name')} for bone in node.get('bones') or []]
    pose = []
    for entry in node.get('referencePose') or []:
        pose.append({'t': _vec4(entry.get('translation'), 'translation')[:3],
                     'q': _vec4(entry.get('rotation'), 'rotation'),
                     's': _vec4(entry.get('scale'), 'scale')[:3]})
    return {'name': node.get('name'), 'parents': list(node.get('parentIndices') or []),
            'bones': bones, 'pose': pose}


def _motion(node):
    if node is None:
        return None
    return {'up': _vec4(node.get('up'), 'up'),
            'forward': _vec4(node.get('forward'), 'forward'),
            'duration': float(node.get('duration', 0.0)),
            'samples': [_vec4(entry, 'root sample')
                        for entry in node.get('referenceFrameSamples') or []]}


def _animation(node):
    kind = node.get('__class__')
    if kind == 'hkaSplineCompressedAnimation':
        floats = node.get('numberOfFloatTracks', 0)
        if floats:
            raise HkxError('A Havok animation has float tracks, which playback does not read')
        frames = node.get('numFrames', 0)
        blocks = node.get('numBlocks', 0)
        per_block = node.get('maxFramesPerBlock', 0)
        if frames < 2 or blocks < 1 or per_block < 2:
            raise HkxError('A Havok animation has no frames to play')
        tracks = node.get('numberOfTransformTracks', 0)
        if tracks < 1:
            raise HkxError('A Havok animation names no tracks')
        if tracks > MAX_COUNT:
            raise HkxError('A Havok animation names too many tracks')
        return {'kind': 'spline', 'duration': float(node.get('duration', 0.0)),
                'tracks': tracks,
                'frames': frames, 'blocks': blocks, 'per_block': per_block,
                'block_duration': float(node.get('blockDuration', 0.0)),
                'frame_duration': float(node.get('frameDuration', 0.0)),
                'offsets': list(node.get('blockOffsets') or []),
                'data': bytes(node.get('data') or []),
                'motion': _motion(node.get('extractedMotion'))}
    if kind == 'hkaInterleavedUncompressedAnimation':
        transforms = []
        for entry in node.get('transforms') or []:
            transforms.append({'t': _vec4(entry.get('translation'), 'translation')[:3],
                               'q': _vec4(entry.get('rotation'), 'rotation'),
                               's': _vec4(entry.get('scale'), 'scale')[:3]})
        tracks = node.get('numberOfTransformTracks', 0)
        if tracks > MAX_COUNT:
            raise HkxError('A Havok animation names too many tracks')
        frames = len(transforms) // tracks if tracks else 0
        if frames < 2 or not tracks:
            raise HkxError('A Havok animation has no frames to play')
        duration = float(node.get('duration', 0.0))
        return {'kind': 'interleaved', 'duration': duration, 'tracks': tracks,
                'frames': frames, 'frame_duration': duration / (frames - 1),
                'transforms': transforms,
                'motion': _motion(node.get('extractedMotion'))}
    raise HkxError(f'A Havok animation is {kind}, which playback does not read')


def _binding(node):
    return {'skeleton': node.get('originalSkeletonName'),
            'track_to_bone': list(node.get('transformTrackToBoneIndices') or []),
            'blend': node.get('blendHint', 0)}


class HkxDocument:
    """Skeletons, animations and track bindings from one TAG0 file."""

    def __init__(self, source):
        try:
            if len(source) > MAX_FILE:
                raise HkxError('The Havok file is too large')
            data = bytes(source)
            self.skeletons, self.animations, self.bindings = self._read(data)
        except HkxError:
            raise
        except RecursionError:
            raise HkxError('Havok types loop back on themselves') from None
        except (IndexError, struct.error, UnicodeDecodeError,
                ValueError, TypeError, KeyError, AttributeError,
                MemoryError) as error:
            raise HkxError(f'A Havok file is malformed: {error}') from error

    @staticmethod
    def _read(data):
        root, _ = _section(data, 0)
        if root['sig'] != 'TAG0':
            raise HkxError('Expected a Havok TAG0 file')
        data_off, types, items = None, None, None
        for sub in root['subs']:
            if sub['sig'] == 'SDKV':
                version = data[sub['pos']:sub['pos'] + 8].decode('ascii', 'replace')
                if version not in SDK_VERSIONS:
                    raise HkxError(f'A Havok file needs SDK {version}')
            elif sub['sig'] == 'DATA':
                data_off = sub['pos']
                data_end = sub['pos'] + sub['length']
            elif sub['sig'] == 'TYPE':
                types = _read_types(data, sub)
            elif sub['sig'] == 'INDX':
                for part in sub['subs']:
                    if part['sig'] == 'ITEM':
                        items = (part, types)
                    elif part['sig'] != 'PTCH':
                        raise HkxError(f'A Havok index holds {part["sig"]}')
            elif sub['sig'] == 'TCRF':
                raise HkxError('A Havok file needs a type compendium it does not carry')
            else:
                raise HkxError(f'A Havok file holds {sub["sig"]}')
        if data_off is None or types is None or items is None:
            raise HkxError('A Havok file is missing its data, types or items')
        entries = _items(data, items[0], data_off, data_end, items[1])
        if len(entries) < 2:
            raise HkxError('A Havok file names no root object')
        reader = _TagReader(data, data_off, types, entries)
        top = reader.item_objects(1)[0]
        if not isinstance(top, dict) or top.get('__class__') != 'hkRootLevelContainer':
            raise HkxError('A Havok file has no animation container')
        skeletons, animations, bindings = [], [], []
        for variant in top.get('namedVariants') or []:
            inner = (variant or {}).get('variant')
            if not isinstance(inner, dict):
                continue
            for skel in inner.get('skeletons') or []:
                if isinstance(skel, dict):
                    skeletons.append(_skeleton(skel))
            for anim in inner.get('animations') or []:
                if isinstance(anim, dict):
                    animations.append(_animation(anim))
            for link in inner.get('bindings') or []:
                if isinstance(link, dict):
                    bindings.append(_binding(link))
        return skeletons, animations, bindings


def _quat_polar32(data, off):
    packed = struct.unpack_from('<I', data, off)[0]
    radius = ((packed >> 18) & 0x3FF) * (1.0 / 1023.0)
    radius = 1.0 - radius * radius
    both = float(packed & 0x3FFFF)
    phi = math.floor(math.sqrt(both))
    theta = 0.0
    if phi > 0.0:
        theta = (math.pi / 4.0) * (both - phi * phi) / phi
        phi = (math.pi / 2.0 / 511.0) * phi
    size = math.sqrt(max(0.0, 1.0 - radius * radius))
    x = math.sin(phi) * math.cos(theta) * size
    y = math.sin(phi) * math.sin(theta) * size
    z = math.cos(phi) * size
    if packed & 0x10000000:
        x = -x
    if packed & 0x20000000:
        y = -y
    if packed & 0x40000000:
        z = -z
    if packed & 0x80000000:
        radius = -radius
    return (x, y, z, radius), off + 4


def _quat_small(a, b, c, missing, sign):
    rest = max(0.0, 1.0 - (a * a + b * b + c * c))
    out = [a, b, c]
    out.insert(missing, math.sqrt(rest) * sign)
    return tuple(out)


def _quat_40(data, off):
    packed = int.from_bytes(data[off:off + 5], 'little')
    frac = 0.000345436
    a = ((packed & 0xFFF) - 2047) * frac
    b = (((packed >> 12) & 0xFFF) - 2047) * frac
    c = (((packed >> 24) & 0xFFF) - 2047) * frac
    return _quat_small(a, b, c, (packed >> 36) & 3,
                       -1.0 if (packed >> 38) & 1 else 1.0), off + 5


def _quat_48(data, off):
    x, y, z = struct.unpack_from('<3H', data, off)
    frac = 0.000043161
    missing = ((y >> 14) & 2) | ((x >> 15) & 1)
    sign = -1.0 if z & 0x8000 else 1.0
    a = ((x & 0x7FFF) - 16383) * frac
    b = ((y & 0x7FFF) - 16383) * frac
    c = ((z & 0x7FFF) - 16383) * frac
    return _quat_small(a, b, c, missing, sign), off + 6


def _quat(data, off, qtype):
    if qtype == 0:
        return _quat_polar32(data, off)
    if qtype == 1:
        return _quat_40(data, off)
    if qtype == 2:
        return _quat_48(data, off)
    if qtype == 5:
        return tuple(struct.unpack_from('<4f', data, off)), off + 16
    raise HkxError(f'A Havok rotation uses quantization {qtype}, which playback does not read')


def _knot_span(degree, frame, count, knots, frames):
    if frame < 0:
        frame += frames * math.ceil(abs(frame) / frames)
        if frame < 0:
            frame += frames
    if frame >= knots[count]:
        return count - 1
    low, high = degree, count
    mid = (low + high) // 2
    while frame < knots[mid] or frame >= knots[mid + 1]:
        if frame < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def _basis(span, degree, frame, knots):
    out = [1.0, 0.0, 0.0, 0.0, 0.0]
    for i in range(1, degree + 1):
        for j in range(i - 1, -1, -1):
            gap = knots[span + i - j] - knots[span - j]
            ratio = (frame - knots[span - j]) / gap if gap else 0.0
            tmp = out[j] * ratio
            out[j + 1] += out[j] - tmp
            out[j] = tmp
    return out


def _eval_scalar(points, degree, knots, frame, frames):
    if len(points) == 1:
        return points[0]
    span = _knot_span(degree, frame, len(points), knots, frames)
    weights = _basis(span, degree, frame, knots)
    return sum(points[span - i] * weights[i] for i in range(degree + 1))


def _eval_quat(points, degree, knots, frame, frames):
    span = _knot_span(degree, frame, len(points), knots, frames)
    weights = _basis(span, degree, frame, knots)
    x = y = z = w = 0.0
    for i in range(degree + 1):
        point, scale = points[span - i], weights[i]
        x += point[0] * scale
        y += point[1] * scale
        z += point[2] * scale
        w += point[3] * scale
    size = math.sqrt(x * x + y * y + z * z + w * w)
    if size > 1e-8:
        x, y, z, w = x / size, y / size, z / size, w / size
    return (x, y, z, w)


def _align(off, size):
    rest = off % size
    return off if not rest else off + size - rest


class _VecTrack:
    __slots__ = ('comps', 'degree', 'knots')

    def value(self, frame, frames):
        return tuple(None if part is None else part if isinstance(part, float)
                     else _eval_scalar(part, self.degree, self.knots, frame, frames)
                     for part in self.comps)


class _QuatTrack:
    __slots__ = ('static', 'points', 'degree', 'knots')

    def value(self, frame, frames):
        if self.static is not None:
            return self.static
        return _eval_quat(self.points, self.degree, self.knots, frame, frames)


def _parse_vec(data, off, static, spline, qtype, default):
    track = _VecTrack()
    if not spline:
        track.degree, track.knots = 0, b''
        comps = []
        for axis in range(3):
            if static & (1 << axis):
                value, off = struct.unpack_from('<f', data, off)[0], off + 4
                comps.append(value)
            else:
                comps.append(default)
        track.comps = comps
        return track, off
    count = struct.unpack_from('<H', data, off)[0]
    degree = data[off + 2]
    off += 3
    if degree > MAX_SPLINE_DEGREE:
        raise HkxError('A Havok motion curve is too complex to play')
    track.degree = degree
    track.knots = data[off:off + count + degree + 2]
    off = _align(off + count + degree + 2, 4)
    bounds, comps = [None] * 3, [None] * 3
    for axis in range(3):
        bit = 1 << axis
        if spline & bit:
            bounds[axis] = struct.unpack_from('<2f', data, off)
            off += 8
            comps[axis] = [0.0] * (count + 1)
        elif static & bit:
            comps[axis], off = struct.unpack_from('<f', data, off)[0], off + 4
        else:
            comps[axis] = default
    if qtype == 0:
        for num in range(count + 1):
            for axis in range(3):
                if spline & (1 << axis):
                    low, high = bounds[axis]
                    comps[axis][num] = low + (high - low) * (data[off] / 255.0)
                    off += 1
    elif qtype == 1:
        for num in range(count + 1):
            for axis in range(3):
                if spline & (1 << axis):
                    low, high = bounds[axis]
                    raw = struct.unpack_from('<H', data, off)[0]
                    comps[axis][num] = low + (high - low) * (raw / 65535.0)
                    off += 2
    else:
        raise HkxError(f'A Havok channel uses quantization {qtype}, which playback does not read')
    track.comps = comps
    return track, _align(off, 4)


def _parse_quat(data, off, static, spline, qtype):
    track = _QuatTrack()
    if not spline:
        track.static, track.points, track.degree, track.knots = None, [], 0, b''
        if static:
            align = {0: 4, 1: 1, 2: 2, 5: 4}.get(qtype)
            if align is None:
                raise HkxError(f'A Havok rotation uses quantization {qtype}, '
                               'which playback does not read')
            track.static, off = _quat(data, _align(off, align), qtype)
        else:
            track.static = (0.0, 0.0, 0.0, 1.0)
        return track, off
    count = struct.unpack_from('<H', data, off)[0]
    degree = data[off + 2]
    off += 3
    track.static = None
    if degree > MAX_SPLINE_DEGREE:
        raise HkxError('A Havok motion curve is too complex to play')
    track.degree = degree
    track.knots = data[off:off + count + degree + 2]
    off += count + degree + 2
    align = {0: 4, 1: 1, 2: 2, 5: 4}.get(qtype)
    if align is None:
        raise HkxError(f'A Havok rotation uses quantization {qtype}, which playback does not read')
    off = _align(off, align)
    points = []
    for _ in range(count + 1):
        quat, off = _quat(data, off, qtype)
        points.append(quat)
    track.points = points
    return track, off


def _parse_block(data, off, tracks):
    masks = [tuple(data[off + 4 * num:off + 4 * num + 4]) for num in range(tracks)]
    off = _align(off + 4 * tracks, 4)
    parsed = []
    for quant, pos, rot, scale in masks:
        pos_q, rot_q, scale_q = quant & 3, (quant >> 2) & 0xF, (quant >> 6) & 3
        position, off = _parse_vec(data, off, pos & 7, (pos >> 4) & 7, pos_q, 0.0)
        off = _align(off, 4)
        rotation, off = _parse_quat(data, off, rot & 0xF, rot & 0xF0, rot_q)
        off = _align(off, 4)
        # Missing scale channels fall back to the skeleton's own scale
        # at sample time, so they stay None here.
        scaling, off = _parse_vec(data, off, scale & 7, (scale >> 4) & 7, scale_q, None)
        off = _align(off, 4)
        parsed.append((position, rotation, scaling))
    return parsed, _align(off, 16)


def sample_frames(anim, skeleton, binding):
    """Every frame's local transform per skeleton bone: a list over
    frames of lists over bones of (translation, rotation, scale).
    Bones no track drives keep the skeleton's reference pose."""
    if anim['kind'] == 'interleaved':
        return _sample_interleaved(anim, skeleton, binding)
    blocks, offsets = [], anim['offsets']
    if len(offsets) != anim['blocks']:
        raise HkxError('A Havok animation has lost a block offset')
    for at in offsets:
        if not 0 <= at <= len(anim['data']) - 4 * anim['tracks']:
            raise HkxError('A Havok animation block is out of range')
    try:
        for at in offsets:
            parsed, _ = _parse_block(anim['data'], at, anim['tracks'])
            blocks.append(parsed)
    except (IndexError, struct.error) as error:
        raise HkxError(f'A Havok animation block is malformed: {error}') from error
    bone_tracks = [-1] * len(skeleton['bones'])
    for track, bone in enumerate(binding['track_to_bone']):
        if 0 <= bone < len(bone_tracks):
            bone_tracks[bone] = track
    if any(track >= anim['tracks'] for track in bone_tracks if track >= 0):
        raise HkxError('A Havok binding points past its tracks')
    frames, per_block = anim['frames'], anim['per_block']
    out = []
    for num in range(frames):
        block = (num % (frames - 1)) // (per_block - 1)
        local = min(num, frames) % (per_block - 1)
        if block >= len(blocks):
            raise HkxError('A Havok animation has lost a block')
        pose = []
        for bone, entry in enumerate(skeleton['pose']):
            track = bone_tracks[bone] if bone < len(bone_tracks) else -1
            if track < 0:
                pose.append((tuple(entry['t']), tuple(entry['q']), tuple(entry['s'])))
                continue
            position, rotation, scaling = blocks[block][track]
            scale = tuple(found if found is not None else entry['s'][axis]
                          for axis, found in enumerate(scaling.value(local, frames)))
            if any(part != part for part in scale):
                scale = (1.0, 1.0, 1.0)
            pose.append((position.value(local, frames), rotation.value(local, frames), scale))
        out.append(pose)
    return out


def _sample_interleaved(anim, skeleton, binding):
    bone_tracks = [-1] * len(skeleton['bones'])
    for track, bone in enumerate(binding['track_to_bone']):
        if 0 <= bone < len(bone_tracks):
            bone_tracks[bone] = track
    frames, tracks = anim['frames'], anim['tracks']
    if any(track >= tracks for track in bone_tracks if track >= 0):
        raise HkxError('A Havok binding points past its tracks')
    out = []
    for num in range(frames):
        pose = []
        for bone, entry in enumerate(skeleton['pose']):
            track = bone_tracks[bone] if bone < len(bone_tracks) else -1
            if track < 0:
                pose.append((tuple(entry['t']), tuple(entry['q']), tuple(entry['s'])))
                continue
            found = anim['transforms'][num * tracks + track]
            pose.append((tuple(found['t']), tuple(found['q']), tuple(found['s'])))
        out.append(pose)
    return out
