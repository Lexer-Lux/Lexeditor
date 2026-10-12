"""Dark Souls 1 models (FLVER2), read for viewing, hitboxes and animation.

Layout facts: GPL-3.0-or-later soulstruct by Grimrukh (flver/core.py,
mesh.py, face_set.py, vertex_array.py, vertex_array_layout.py,
layout_repair.py, bone.py, dummy.py, material.py, texture.py; see
credits.md). No soulstruct code is redistributed: this is a from-scratch
struct reader of the same byte layout, in the msb.py/tae.py style.
DS1 versions are 0x2000B-0x2000D; anything else is refused. Read-only:
models are viewed, never rewritten, so there is no pack path to keep
byte-exact.
"""
import struct

from .formats import FormatError, inflate

MAGIC = b'FLVER\0'
DS1_VERSIONS = frozenset({0x2000B, 0x2000C, 0x2000D})
UV_FACTOR = 1024
MAX_FILE = 64 * 1024 * 1024
MAX_VERTICES = 4 * 1024 * 1024
HEADER_SIZE = 128
DUMMY_SIZE = 64
MATERIAL_SIZE = 32
BONE_SIZE = 128
MESH_SIZE = 48
FACESET_SIZE = 32
ARRAY_HEADER_SIZE = 32
LAYOUT_SIZE = 16
MEMBER_SIZE = 20
TEXTURE_SIZE = 32

# Layout member semantics (soulstruct VertexDataType.type_int).
POS, WEIGHTS, BONE_IDS, NORMAL, UV, TANGENT, BITANGENT, COLOR = 0, 1, 2, 3, 5, 6, 7, 10

# Layout member storage formats (soulstruct VertexDataFormatEnum) to byte sizes.
FORMAT_SIZES = {0x01: 8, 0x02: 12, 0x03: 16, 0x10: 4, 0x11: 4, 0x12: 4,
                0x13: 4, 0x15: 4, 0x16: 8, 0x18: 8, 0x1A: 8, 0x2E: 8, 0x2F: 4}

# QLOC's DS1R layouts lie for these materials: the vertex data holds
# members the layout omits. (member semantic, format, ignore bytes).
# Facts from soulstruct's layout_repair.py; sizes verified by the reader.
QLOC_LAYOUTS = {
    'M[D].mtd': [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13), (None, 4),
                 (COLOR, 0x13), (UV, 0x15)],
    'M[D]_Edge.mtd': [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13), (None, 4),
                      (COLOR, 0x13), (UV, 0x15)],
    'A10_02_m9000_M[D].mtd': [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13),
                              (None, 8), (COLOR, 0x13), (UV, 0x15)],
    'A19_Division[D]_Alp.mtd': [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13),
                                (None, 32), (COLOR, 0x13), (UV, 0x15)],
    'A19_Fly[DSB]_edge.mtd': [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13),
                              (None, 32), (COLOR, 0x13), (UV, 0x15)],
}
QLOC_UNSHADED = frozenset({'A10_lightshaft[Dn]_Add.mtd', 'A10_BG_shaft[Dn]_Add_LS.mtd',
                           'A10_mist_02[Dn]_Alp.mtd', 'M_Sky[Dn].mtd', 'M_Tree[D]_Edge.mtd',
                           'S[NL].mtd'})
QLOC_UNSHADED_LAYOUT = [(POS, 0x02), (BONE_IDS, 0x11), (NORMAL, 0x13), (COLOR, 0x13), (UV, 0x15)]

# Two DSR map pieces whose vertex data starts with 32 broken bytes
# (soulstruct KNOWN_CORRUPTED_DS1R_ARRAYS): parsed, with a note.
CORRUPTED_PREFIXES = (
    (b'\0' * 16 + b'goz\xc3\x7fY\xf9\xff\x7fY\xf9\xff\0\0\0\0', 'm0208B0A14'),
    (b'\0' * 16 + b'\xde\xd1?\xc3\x7f1\x1a\xff\x7f1\x1a\xff\0\0\0\0', 'm0302B0A14'),
)


class FlverError(FormatError):
    """A model file Lexeditor cannot safely read."""


def _check(data, offset, size, what):
    if not 0 <= offset <= len(data) - size:
        raise FlverError(f'{what} runs past the end of the file')


def _cstr(data, offset, encoding, what):
    _check(data, offset, 1, what)
    if encoding == 'utf-16-le':
        end = offset
        while True:
            _check(data, end, 2, what)
            if data[end:end + 2] == b'\0\0':
                break
            end += 2
        raw = bytes(data[offset:end])
    else:
        end = data.find(b'\0', offset)
        if end < 0:
            raise FlverError(f'{what} is not terminated')
        raw = bytes(data[offset:end])
    try:
        return raw.decode(encoding)
    except UnicodeError as error:
        raise FlverError(f'{what} is not decodable') from error


def _triangulate(indices, strip):
    """Index triplets from a face set, expanding strips."""
    if not strip:
        if len(indices) % 3:
            raise FlverError('Triangle list length is not a multiple of three')
        return [tuple(indices[i:i + 3]) for i in range(0, len(indices), 3)]
    triangles = []
    flip = False
    for i in range(len(indices) - 2):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        if a == 0xFFFF or b == 0xFFFF or c == 0xFFFF:
            flip = False
            continue
        if a != b and b != c and a != c:
            triangles.append((c, b, a) if flip else (a, b, c))
        flip = not flip
    return triangles


def _decode_member(semantic, format_enum, chunk):
    """Float tuples from one layout member's bytes, or None to skip it."""
    if semantic == POS:
        if format_enum == 0x02:
            return [struct.unpack('<3f', chunk)]
        if format_enum == 0x03:
            x, y, z, _w = struct.unpack('<4f', chunk)
            return [(x, y, z)]
    elif semantic == NORMAL:
        if format_enum == 0x02:
            return [struct.unpack('<3f', chunk)]
        if format_enum == 0x03:
            x, y, z, _w = struct.unpack('<3fi', chunk)
            return [(x, y, z)]
        if format_enum in (0x10, 0x11, 0x13, 0x2F):
            x, y, z, _w = struct.unpack('<4B', chunk)
            return [((x - 127.0) / 127.0, (y - 127.0) / 127.0, (z - 127.0) / 127.0)]
        if format_enum == 0x12:
            _w, x, y, z = struct.unpack('<B3b', chunk)
            return [(x / 127.0, y / 127.0, z / 127.0)]
        if format_enum == 0x1A:
            x, y, z, _w = struct.unpack('<4h', chunk)
            return [((x - 32767.0) / 32767.0, (y - 32767.0) / 32767.0,
                     (z - 32767.0) / 32767.0)]
        if format_enum == 0x2E:
            x, y, z, _w = struct.unpack('<4H', chunk)
            return [((x - 32767.0) / 32767.0, (y - 32767.0) / 32767.0,
                     (z - 32767.0) / 32767.0)]
    elif semantic == UV:
        if format_enum == 0x01:
            return [struct.unpack('<2f', chunk)]
        if format_enum == 0x02:
            return [struct.unpack('<3f', chunk)[:2]]
        if format_enum == 0x03:
            u0, v0, _u1, _v1 = struct.unpack('<4f', chunk)
            return [(u0, v0)]
        if format_enum in (0x10, 0x11, 0x12, 0x13, 0x15):
            u, v = struct.unpack('<2h', chunk)
            return [(u / UV_FACTOR, v / UV_FACTOR)]
        if format_enum == 0x16:
            u, v, _u1, _v1 = struct.unpack('<4h', chunk)
            return [(u / UV_FACTOR, v / UV_FACTOR)]
        if format_enum in (0x1A, 0x2E):
            u, v, _a, _b = struct.unpack('<4h', chunk)
            return [(u / UV_FACTOR, v / UV_FACTOR)]
    elif semantic == WEIGHTS:
        if format_enum == 0x10:
            return [tuple(v / 127.0 for v in struct.unpack('<4b', chunk))]
        if format_enum == 0x13:
            return [tuple(v / 255.0 for v in struct.unpack('<4B', chunk))]
        if format_enum in (0x16, 0x1A):
            return [tuple(v / 32767.0 for v in struct.unpack('<4h', chunk))]
    elif semantic == BONE_IDS:
        if format_enum in (0x11, 0x2F):
            return [struct.unpack('<4B', chunk)]
        if format_enum == 0x18:
            return [struct.unpack('<4h', chunk)]
    elif semantic in (TANGENT, BITANGENT, COLOR):
        return None
    raise FlverError(f'Unsupported vertex member (semantic {semantic}, format 0x{format_enum:02X})')


class FlverDocument:
    """A parsed DS1 model: meshes, bones, dummies and materials."""

    def __init__(self, data):
        self.raw = bytes(data)
        self.notes = []
        data = self.raw
        if len(data) > MAX_FILE:
            raise FlverError('File is too large to be a model')
        if data[:4] == b'DCX\0':
            data = inflate(data)
        if len(data) < HEADER_SIZE or data[:6] != MAGIC:
            raise FlverError('Not a FLVER model')
        endian = data[6:8]
        if endian == b'L\0':
            self.big_endian = False
        elif endian == b'B\0':
            raise FlverError('Big-endian FLVER is not supported')
        else:
            raise FlverError('FLVER byte-order marker is invalid')
        (version, self.vertex_data_offset, vertex_data_size, dummy_count, material_count,
         bone_count, mesh_count, array_count) = struct.unpack_from('<8I', data, 8)
        if version not in DS1_VERSIONS:
            raise FlverError(f'Unsupported FLVER version 0x{version:X}')
        self.version = version
        self.bbox = (struct.unpack_from('<3f', data, 40), struct.unpack_from('<3f', data, 52))
        bit_size, unicode, _unk0 = struct.unpack_from('<3B', data, 72)
        if bit_size not in (0, 16, 32):
            raise FlverError(f'Unsupported index bit size {bit_size}')
        self.default_bit_size = bit_size
        self.encoding = 'utf-16-le' if unicode else 'shift_jis_2004'
        face_count, layout_count, texture_count = struct.unpack_from('<3I', data, 80)
        for what, count in (('dummies', dummy_count), ('materials', material_count),
                            ('bones', bone_count), ('meshes', mesh_count),
                            ('arrays', array_count), ('face sets', face_count),
                            ('layouts', layout_count), ('textures', texture_count)):
            if count > 65536:
                raise FlverError(f'Unreasonable {what} count {count}')
        cursor = HEADER_SIZE
        self.dummies = [self._dummy(data, cursor + i * DUMMY_SIZE) for i in range(dummy_count)]
        cursor += dummy_count * DUMMY_SIZE
        self.materials = [self._material(data, cursor + i * MATERIAL_SIZE)
                          for i in range(material_count)]
        cursor += material_count * MATERIAL_SIZE
        self.bones = [self._bone(data, cursor + i * BONE_SIZE) for i in range(bone_count)]
        cursor += bone_count * BONE_SIZE
        mesh_headers = [self._mesh_header(data, cursor + i * MESH_SIZE) for i in range(mesh_count)]
        cursor += mesh_count * MESH_SIZE
        face_sets = [self._face_set(data, cursor + i * FACESET_SIZE) for i in range(face_count)]
        cursor += face_count * FACESET_SIZE
        array_headers = [self._array_header(data, cursor + i * ARRAY_HEADER_SIZE)
                         for i in range(array_count)]
        cursor += array_count * ARRAY_HEADER_SIZE
        self.layouts = [self._layout(data, cursor + i * LAYOUT_SIZE) for i in range(layout_count)]
        cursor += layout_count * LAYOUT_SIZE
        textures = [self._texture(data, cursor + i * TEXTURE_SIZE) for i in range(texture_count)]
        for material in self.materials:
            first, count = material.pop('_first'), material.pop('_count')
            if first + count > len(textures):
                raise FlverError('Material texture range is invalid')
            material['textures'] = textures[first:first + count]
        self.meshes = []
        for index, header in enumerate(mesh_headers):
            self.meshes.append(self._mesh(data, index, header, face_sets, array_headers))
        _check(data, self.vertex_data_offset, 0, 'Vertex data')
        if self.vertex_data_offset + vertex_data_size > len(data):
            raise FlverError('Vertex data runs past the end of the file')

    def _dummy(self, data, offset):
        _check(data, offset, DUMMY_SIZE, 'Dummy')
        pos = struct.unpack_from('<3f', data, offset)
        color = struct.unpack_from('<4B', data, offset + 12)
        forward = struct.unpack_from('<3f', data, offset + 16)
        ref_id, parent = struct.unpack_from('<2h', data, offset + 28)
        upward = struct.unpack_from('<3f', data, offset + 32)
        attach, follows, use_up = struct.unpack_from('<h2B', data, offset + 44)
        return {'pos': pos, 'color': color, 'forward': forward, 'ref_id': ref_id,
                'parent_bone': parent, 'upward': upward, 'attach_bone': attach,
                'follows_bone': bool(follows), 'use_upward': bool(use_up)}

    def _material(self, data, offset):
        _check(data, offset, MATERIAL_SIZE, 'Material')
        name_off, mtd_off, count, first, flags, _gx, _unk0 = struct.unpack_from('<7I', data, offset)
        return {'name': _cstr(data, name_off, self.encoding, 'Material name'),
                'mat_def': _cstr(data, mtd_off, self.encoding, 'Material definition'),
                'flags': flags, '_first': first, '_count': count}

    def _bone(self, data, offset):
        _check(data, offset, BONE_SIZE, 'Bone')
        pos = struct.unpack_from('<3f', data, offset)
        name_off = struct.unpack_from('<I', data, offset + 12)[0]
        rot = struct.unpack_from('<3f', data, offset + 16)
        parent, child = struct.unpack_from('<2h', data, offset + 28)
        scale = struct.unpack_from('<3f', data, offset + 32)
        use = struct.unpack_from('<I', data, offset + 60)[0]
        box = (struct.unpack_from('<3f', data, offset + 48),
               struct.unpack_from('<3f', data, offset + 64))
        return {'name': _cstr(data, name_off, self.encoding, 'Bone name'), 'pos': pos,
                'rot': rot, 'scale': scale, 'parent': parent, 'child': child,
                'usage': use, 'bbox': box}

    def _mesh_header(self, data, offset):
        _check(data, offset, MESH_SIZE, 'Mesh')
        dynamic = data[offset] != 0
        material = struct.unpack_from('<I', data, offset + 4)[0]
        (default_bone, bone_count, box_off, bone_off, face_count, face_off,
         array_count, array_off) = struct.unpack_from('<8I', data, offset + 16)
        if material >= len(self.materials):
            raise FlverError('Mesh material index is invalid')
        if not 1 <= array_count <= 3:
            raise FlverError('Mesh vertex array count is invalid')
        return {'dynamic': dynamic, 'material': material, 'default_bone': default_bone,
                'bone_count': bone_count, 'box_off': box_off, 'bone_off': bone_off,
                'face_count': face_count, 'face_off': face_off,
                'array_count': array_count, 'array_off': array_off}

    def _face_set(self, data, offset):
        _check(data, offset, FACESET_SIZE, 'Face set')
        flags, strip, cull = struct.unpack_from('<3B', data, offset + 3)
        count, rel, _length = struct.unpack_from('<3I', data, offset + 8)
        bit_size = struct.unpack_from('<I', data, offset + 24)[0]
        if bit_size == 0:
            bit_size = self.default_bit_size
        if bit_size == 0:
            bit_size = 16
            self.notes.append('Face set index size defaulted to 16-bit')
        if bit_size not in (16, 32):
            raise FlverError(f'Unsupported face set index size {bit_size}')
        if count > MAX_VERTICES * 3:
            raise FlverError('Unreasonable face set index count')
        start = self.vertex_data_offset + rel
        width = bit_size // 8
        _check(data, start, count * width, 'Face set indices')
        fmt = '<%d%s' % (count, 'H' if bit_size == 16 else 'I')
        indices = struct.unpack_from(fmt, data, start)
        return {'flags': flags, 'strip': bool(strip), 'cull': bool(cull),
                'triangles': _triangulate(indices, strip)}

    def _array_header(self, data, offset):
        _check(data, offset, ARRAY_HEADER_SIZE, 'Vertex array')
        _index, layout, vsize, vcount = struct.unpack_from('<4I', data, offset)
        length, rel = struct.unpack_from('<2I', data, offset + 24)
        if vcount > MAX_VERTICES:
            raise FlverError('Unreasonable vertex count')
        return {'layout': layout, 'vsize': vsize, 'vcount': vcount,
                'length': length, 'offset': self.vertex_data_offset + rel}

    def _layout(self, data, offset):
        _check(data, offset, LAYOUT_SIZE, 'Vertex layout')
        count = struct.unpack_from('<I', data, offset)[0]
        types_off = struct.unpack_from('<I', data, offset + 12)[0]
        if count > 32:
            raise FlverError('Unreasonable layout member count')
        members = []
        for i in range(count):
            _check(data, types_off + i * MEMBER_SIZE, MEMBER_SIZE, 'Layout member')
            _unk, _doff, fmt, semantic, _inst = struct.unpack_from('<5I', data, types_off + i * MEMBER_SIZE)
            if fmt not in FORMAT_SIZES:
                raise FlverError(f'Unsupported vertex format 0x{fmt:02X}')
            members.append((semantic, fmt))
        return members

    def _texture(self, data, offset):
        _check(data, offset, TEXTURE_SIZE, 'Texture')
        path_off, type_off = struct.unpack_from('<2I', data, offset)
        scale = struct.unpack_from('<2f', data, offset + 8)
        return {'path': _cstr(data, path_off, self.encoding, 'Texture path'),
                'type': _cstr(data, type_off, self.encoding, 'Texture type'),
                'scale': scale}

    def _mesh(self, data, index, header, face_sets, array_headers):
        if header['material'] >= len(self.materials):
            raise FlverError('Mesh material index is invalid')
        faces = self._index_list(data, header['face_off'], header['face_count'],
                                 len(face_sets), 'face set')
        arrays = self._index_list(data, header['array_off'], header['array_count'],
                                  len(array_headers), 'vertex array')
        mesh = {'index': index, 'dynamic': header['dynamic'],
                'material': self.materials[header['material']],
                'default_bone': header['default_bone'], 'triangles': [],
                'cull': all(face_sets[face]['cull'] for face in faces) if faces else True,
                'positions': [], 'normals': [], 'uvs': [], 'weights': [], 'bone_ids': []}
        for face in faces:
            mesh['triangles'].extend(face_sets[face]['triangles'])
        mtd = mesh['material']['mat_def'].rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
        if sum(1 for array in arrays if array_headers[array]['vcount']) > 1:
            raise FlverError('Multi-array meshes are not supported')
        for array in arrays:
            self._array(data, mesh, mtd, array_headers[array])
        if header['box_off']:
            _check(data, header['box_off'], 24, 'Mesh bounding box')
            mesh['bbox'] = (struct.unpack_from('<3f', data, header['box_off']),
                            struct.unpack_from('<3f', data, header['box_off'] + 12))
        else:
            mesh['bbox'] = None
        if header['bone_count']:
            _check(data, header['bone_off'], header['bone_count'] * 4, 'Mesh bone indices')
            mesh['bone_list'] = list(struct.unpack_from('<%di' % header['bone_count'],
                                                        data, header['bone_off']))
        else:
            mesh['bone_list'] = []
        return mesh

    def _index_list(self, data, offset, count, total, what):
        if count > total:
            raise FlverError(f'Mesh {what} count is invalid')
        _check(data, offset, count * 4, f'Mesh {what} list')
        items = struct.unpack_from('<%di' % count, data, offset)
        if any(i < 0 or i >= total for i in items):
            raise FlverError(f'Mesh {what} index is invalid')
        return items

    def _array(self, data, mesh, mtd, header):
        if header['layout'] >= len(self.layouts):
            raise FlverError('Vertex array layout index is invalid')
        members = self.layouts[header['layout']]
        stride = sum(FORMAT_SIZES[fmt] for _sem, fmt in members)
        if stride != header['vsize']:
            members = self._repair(mtd, header, stride)
            if members is None:
                raise FlverError('Vertex size does not match its layout')
            stride = sum(fmt if sem is None else FORMAT_SIZES[fmt] for sem, fmt in members)
        _check(data, header['offset'], header['vcount'] * stride, 'Vertex data')
        blob = data[header['offset']:header['offset'] + header['vcount'] * stride]
        for prefix, piece in CORRUPTED_PREFIXES:
            if blob[:32] == prefix:
                self.notes.append(f'Known corrupted DSR vertex data ({piece}); values may be wrong')
        base = len(mesh['positions'])
        positions, normals, uvs, weights, bone_ids = [], [], [], [], []
        for v in range(header['vcount']):
            cursor = v * stride
            for semantic, fmt in members:
                if semantic is None:
                    cursor += fmt
                    continue
                size = FORMAT_SIZES[fmt]
                value = _decode_member(semantic, fmt, blob[cursor:cursor + size])
                cursor += size
                if value is None:
                    continue
                if semantic == POS:
                    positions.extend(value)
                elif semantic == NORMAL:
                    normals.extend(value)
                elif semantic == UV:
                    uvs.extend(value)
                elif semantic == WEIGHTS:
                    weights.extend(value)
                elif semantic == BONE_IDS:
                    bone_ids.extend(value)
        if len(positions) != header['vcount']:
            raise FlverError('Vertex array did not yield one position per vertex')
        mesh['positions'].extend(positions)
        mesh['normals'].extend(normals)
        mesh['uvs'].extend(uvs)
        mesh['weights'].extend(weights)
        mesh['bone_ids'].extend(bone_ids)
        return base

    def _repair(self, mtd, header, stride):
        table = QLOC_LAYOUTS.get(mtd)
        if table is None and mtd in QLOC_UNSHADED:
            table = QLOC_UNSHADED_LAYOUT
        if table is None:
            return None
        fixed = sum(FORMAT_SIZES[fmt] if sem is not None else fmt for sem, fmt in table)
        if fixed != header['vsize']:
            return None
        self.notes.append(f'Repaired QLOC vertex layout for {mtd} ({stride} -> {fixed})')
        return table

    def mesh_data(self, index):
        """Viewport-ready data for one mesh: triangles index into positions."""
        mesh = self.meshes[index]
        count = len(mesh['positions'])
        for triangle in mesh['triangles']:
            if max(triangle) >= count:
                raise FlverError('Face set index points past the vertices')
        return {'material': mesh['material']['name'], 'mat_def': mesh['material']['mat_def'],
                'dynamic': mesh['dynamic'], 'cull': mesh['cull'], 'bbox': mesh['bbox'],
                'positions': mesh['positions'], 'normals': mesh['normals'],
                'uvs': mesh['uvs'], 'weights': mesh['weights'],
                'bone_ids': mesh['bone_ids'], 'bone_list': mesh['bone_list'],
                'default_bone': mesh['default_bone'], 'triangles': mesh['triangles']}
