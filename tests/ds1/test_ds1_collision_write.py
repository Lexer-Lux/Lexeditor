"""Collision writes retain geometry and a queryable Havok spatial index."""
import math
import random
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ds1 import collision_archive, collision_merge, collision_mopp, hkx, hkx_write
from plugins.ds1.collision_write import CollisionDocument
from plugins.ds1.formats import FormatError


def query(code, info, low, high):
    """Independent interpreter of the encoded MOPP instruction families.

    Quantize queries with the game's float32 arithmetic; use high-byte tests
    for splits and full root coordinates for the BOUNDS24 instructions.
    """
    def f32(value):
        return struct.unpack('<f', struct.pack('<f', value))[0]

    lo = [math.floor(f32(f32(f32(low[i]) - info[i]) * info[3])) for i in range(3)]
    hi = [math.floor(f32(f32(f32(high[i]) - info[i]) * info[3])) for i in range(3)]
    pending, result, steps = [(0, 0)], set(), 0
    while pending:
        pc, offset = pending.pop()
        while True:
            steps += 1
            assert steps < 1000000, 'MOPP bytecode loops'
            op = code[pc]
            pc += 1
            if op == 0:
                break
            if op == 7:
                jump = int.from_bytes(code[pc:pc+3], 'big')
                pc += 3 + jump
            elif 0x10 <= op <= 0x12:
                axis = op - 0x10
                left_max, right_min, jump = code[pc:pc+3]
                pc += 3
                if hi[axis] >> 16 >= right_min:
                    pending.append((pc + jump, offset))
                if lo[axis] >> 16 > left_max:
                    break
            elif 0x29 <= op <= 0x2b:
                axis = op - 0x29
                minimum = int.from_bytes(code[pc:pc+3], 'big')
                maximum = int.from_bytes(code[pc+3:pc+6], 'big')
                pc += 6
                if hi[axis] < minimum or lo[axis] > maximum:
                    break
            elif op == 0x0b:
                offset = int.from_bytes(code[pc:pc+4], 'big')
                pc += 4
            elif 0x30 <= op <= 0x4f:
                result.add(offset + op - 0x30)
                break
            else:
                pytest.fail(f'Unexpected MOPP opcode {op:x}')
    return result


def test_spatial_index_matches_brute_force_for_large_mesh_and_subparts():
    rng = random.Random(77102)
    subparts, aabbs = [], {}
    for part in range(2):
        vertices, faces = [], []
        for face_id in range(1200):
            x, y, z = [rng.uniform(-4000, 4000) for _ in range(3)]
            edge = rng.uniform(.01, 40)
            at = len(vertices)
            vertices.extend([(x, y, z), (x+edge, y, z), (x, y+edge, z+edge)])
            faces.append((at, at+1, at+2, 65535))
            aabbs[(part << 20) | face_id] = ((x, y, z), (x+edge, y+edge, z+edge))
        subparts.append((vertices, faces))
    code, info = collision_mopp.build(subparts)
    assert len(code) > 65536  # Exercise branches larger than a 16-bit jump.
    for key, (low, high) in aabbs.items():
        found = query(code, info, low, high)
        assert key in found
    for _ in range(80):
        low = [rng.uniform(-5000, 5000) for _ in range(3)]
        high = [value + rng.uniform(0, 1000) for value in low]
        expected = {key for key, (a, b) in aabbs.items()
                    if all(low[i] <= b[i] and high[i] >= a[i] for i in range(3))}
        assert expected <= query(code, info, low, high)
    assert query(code, info, [-10000]*3, [10000]*3) == set(aabbs)
    assert not query(code, info, [20000]*3, [20001]*3)


def test_index_keeps_face_ids_after_degenerate_faces_and_covers_radius():
    vertices = [(0., 0., 0.), (1., 0., 0.), (0., 0., 1.)]
    code, info = collision_mopp.build([(vertices, [(0, 0, 0, 0), (0, 1, 2, 999)])], radius=.5)
    assert query(code, info, [-.4]*3, [-.3]*3) == {1}
    assert not query(code, info, [-1.]*3, [-.6]*3)


@pytest.mark.parametrize('vertices,faces', [
    ([(0, 0, float('nan'))], [(0, 0, 0)]),
    ([(0, 0, float('inf'))], [(0, 0, 0)]),
    ([(0, 0, 1e40)], [(0, 0, 0)]),
    ([(0, 0)], [(0, 0, 0)]),
    ([(0, 0, 0)], [(0, 1, 2)]),
    ([(0, 0, 0)], [(True, 0, 0)]),
    ([(0, 0, 0)], [(0, 0, 0)]),
])
def test_invalid_mesh_cannot_produce_runtime_bytecode(vertices, faces):
    with pytest.raises(FormatError):
        collision_mopp.build([(vertices, faces)])


def tagged_fixture():
    sys.path.insert(0, str(Path(__file__).parent))
    from hkx_fixture import build_tag0, _section
    source = build_tag0()
    root, _ = hkx._section(source, 0)
    parts = []
    # Root's namedVariants is a reference at DATA offset zero. Populate a
    # real PTCH record so a successful reader round-trip cannot hide an
    # invalid loader fixup table.
    for section in root['subs']:
        payload = source[section['pos']:section['pos']+section['length']]
        if section['sig'] == 'INDX':
            children = []
            for child in section['subs']:
                raw = source[child['pos']:child['pos']+child['length']]
                if child['sig'] == 'PTCH':
                    raw = struct.pack('<3I', 1, 1, 0)
                children.append(_section(child['sig'].encode(), raw, False))
            payload = b''.join(children)
        parts.append(_section(section['sig'].encode(), payload, bool(section['subs'])))
    return _section(b'TAG0', b''.join(parts), True)


def test_item_resize_preserves_other_objects_and_relocates_loader_fixups():
    source = tagged_fixture()
    entries = hkx._peek_tables(source)
    # Resize a string referenced from several independent objects. Their
    # item indices stay stable while all DATA addresses and PTCH move.
    master = next(i for i, entry in enumerate(entries)
                  if entry['type'] and source[entry['pos']:entry['pos']+7] == b'Master\0')
    renamed = b'A much longer skeleton name\0'
    output = hkx_write.replace_items(source, {master: (renamed, len(renamed))})
    before, after = hkx.HkxDocument(source), hkx.HkxDocument(output)
    assert before.skeletons[0]['name'] == 'Master'
    assert after.skeletons[0]['name'] == renamed[:-1].decode()
    assert before.animations == after.animations
    assert before.skeletons[0]['bones'] == after.skeletons[0]['bones']
    assert after.bindings[0]['skeleton'] == renamed[:-1].decode()
    root, _ = hkx._section(output, 0)
    data_at = next(part['pos'] for part in root['subs'] if part['sig'] == 'DATA')
    ptch = next(child for part in root['subs'] if part['sig'] == 'INDX'
                for child in part['subs'] if child['sig'] == 'PTCH')
    assert struct.unpack_from('<3I', output, ptch['pos']) == (
        1, 1, hkx._peek_tables(output)[1]['pos']-data_at)
    # Repeated saves compact arrays instead of retaining their previous
    # payloads on disk indefinitely.
    again = hkx_write.replace_items(output, {master: (renamed, len(renamed))})
    assert again == output


def test_resizing_objects_or_arrays_containing_fixups_is_refused():
    source = tagged_fixture()
    with pytest.raises(hkx.HkxError, match='primitive'):
        hkx_write.replace_items(source, {1: (bytes(4), 1)})
    entries = hkx._peek_tables(source)
    primitive = next(i for i, item in enumerate(entries)
                     if item['type'] and item['type'].name == 'hkUint8')
    with pytest.raises(hkx.HkxError, match='size'):
        hkx_write.replace_items(source, {primitive: (b'abc', 20)})


def test_pointer_arrays_use_the_declared_eight_byte_stride():
    integer, pointer = hkx._Type(), hkx._Type()
    integer.flags = pointer.flags = hkx.FLAG_FORMAT | hkx.FLAG_SIZE
    integer.format_info, integer.byte_size = 0x8004, 4
    pointer.format_info, pointer.byte_size = hkx.PTR, 8
    data = struct.pack('<i4xi4xII', 2, 3, 17, 29)
    entries = [{'type': None, 'pos': 0, 'count': 0},
               {'type': pointer, 'pos': 0, 'count': 2},
               {'type': integer, 'pos': 16, 'count': 1},
               {'type': integer, 'pos': 20, 'count': 1}]
    assert hkx._TagReader(data, 0, [], entries).item_objects(1) == [17, 29]
    assert hkx._peek_element(data, entries, (pointer, 0, 2), 1) == (integer, 20)


@pytest.fixture
def collision_source(monkeypatch):
    import hkx_fixture as fixture
    extra = [
        ('prim', 'T*', 8, hkx.PTR),
        ('array', 'A_Ptr', 'T*'), ('array', 'A_Vector', 'hkVector4f'),
        ('array', 'A_Part', 'hkpExtendedMeshShape::TrianglesSubpart'),
        ('class', 'hkpExtendedMeshShape::TrianglesSubpart', 80,
         [('numTriangleShapes', 0, 'hkInt32'), ('numVertices', 4, 'hkInt32'),
          ('extrusion', 16, 'hkVector4f'), ('transform', 32, 'hkQsTransformf')]),
        ('class', 'hkpStorageExtendedMeshShape::MeshSubpartStorage', 64,
         [('vertices', 0, 'A_Vector'), ('indices16', 16, 'A_i16'),
          ('materialIndices', 32, 'A_u8'), ('materialIndices16', 48, 'A_i16')]),
        ('class', 'CustomMeshParameter', 40,
         [('vertexDataBuffer', 0, 'A_u8'), ('vertexDataStride', 16, 'hkInt32'),
          ('primitiveDataBuffer', 20, 'A_u8'), ('materialNameData', 36, 'hkUint32')]),
        ('class', 'hkpMoppCode::CodeInfo', 16, [('offset', 0, 'hkVector4f')]),
        ('class', 'hkpMoppCode', 32,
         [('info', 0, 'hkpMoppCode::CodeInfo'), ('data', 16, 'A_u8')]),
        ('class', 'CustomParamStorageExtendedMeshShape', 188,
         [('embeddedTrianglesSubpart', 0, 'hkpExtendedMeshShape::TrianglesSubpart'),
          ('aabbHalfExtents', 80, 'hkVector4f'), ('aabbCenter', 96, 'hkVector4f'),
          ('numBitsForSubpartIndex', 112, 'hkInt32'), ('trianglesSubparts', 116, 'A_Part'),
          ('weldingInfo', 132, 'A_i16'), ('cachedNumChildShapes', 148, 'hkInt32'),
          ('triangleRadius', 152, 'float'), ('meshstorage', 156, 'A_Ptr'),
          ('materialArray', 172, 'A_Ptr')]),
    ]
    types = fixture.TYPES + extra
    monkeypatch.setattr(fixture, 'TYPES', types)
    monkeypatch.setattr(fixture, 'TIDS', {entry[1]: i+1 for i, entry in enumerate(types)})
    base = fixture.build_tag0()
    entries = hkx._peek_tables(base)
    first = len(entries)
    names = ('shape', 'code', 'parts', 'storage_refs', 'material_refs', 'storage0', 'storage1',
             'material0', 'material1', 'vertices0', 'vertices1', 'faces0', 'faces1',
             'flags0', 'flags1', 'mopp')
    ids = {name: first+i for i, name in enumerate(names)}

    def ref(blob, at, name):
        struct.pack_into('<i', blob, at, ids[name])

    part = bytearray(80)
    struct.pack_into('<ii', part, 0, 1, 3)
    struct.pack_into('<12f', part, 32, 0,0,0,0, 0,0,0,1, 1,1,1,1)
    shape = bytearray(188)
    shape[:80] = part
    struct.pack_into('<i', shape, 112, 12)
    struct.pack_into('<i', shape, 148, 2)
    for at, name in ((116, 'parts'), (156, 'storage_refs'), (172, 'material_refs')):
        ref(shape, at, name)
    code = bytearray(32)
    ref(code, 16, 'mopp')
    blobs = [('CustomParamStorageExtendedMeshShape', 1, shape), ('hkpMoppCode', 1, code),
             ('hkpExtendedMeshShape::TrianglesSubpart', 2, part+part),
             ('T*', 2, struct.pack('<i4xi4x', ids['storage0'], ids['storage1'])),
             ('T*', 2, struct.pack('<i4xi4x', ids['material0'], ids['material1']))]
    for i in range(2):
        storage = bytearray(64)
        ref(storage, 0, f'vertices{i}')
        ref(storage, 16, f'faces{i}')
        blobs.append(('hkpStorageExtendedMeshShape::MeshSubpartStorage', 1, storage))
    for i in range(2):
        material = bytearray(40)
        ref(material, 0, f'flags{i}')
        struct.pack_into('<i', material, 16, 1)
        struct.pack_into('<I', material, 36, 21+i)
        blobs.append(('CustomMeshParameter', 1, material))
    blobs += [('hkVector4f', 3, struct.pack('<12f', 0,0,0,0, 1,0,0,0, 0,0,1,0)),
              ('hkVector4f', 3, struct.pack('<12f', 10,0,0,0, 11,0,0,0, 10,0,1,0)),
              ('hkInt16', 4, struct.pack('<4h', 0,1,2,555)),
              ('hkInt16', 4, struct.pack('<4h', 0,1,2,666)),
              ('hkUint8', 3, bytes([17,18,19])), ('hkUint8', 3, bytes([27,28,29])),
              ('hkUint8', 1, b'\0')]
    root, _ = hkx._section(base, 0)
    data_part = next(section for section in root['subs'] if section['sig'] == 'DATA')
    payload = bytearray(base[data_part['pos']:data_part['pos']+data_part['length']])
    records, refs = bytearray(), []
    for (kind, count, blob), name in zip(blobs, names):
        payload += bytes((-len(payload)) % 16)
        at = len(payload)
        if name == 'shape':
            refs += [at+116, at+156, at+172]
        elif name == 'code':
            refs += [at+16]
        elif name in ('storage_refs', 'material_refs'):
            refs += [at, at+8]
        elif name.startswith('storage'):
            refs += [at, at+16]
        elif name.startswith('material'):
            refs += [at]
        records += struct.pack('<3I', fixture.TIDS[kind], at, count)
        payload += blob
    parts = []
    for section in root['subs']:
        raw = base[section['pos']:section['pos']+section['length']]
        if section['sig'] == 'DATA':
            raw = bytes(payload)
        elif section['sig'] == 'INDX':
            children = []
            for child in section['subs']:
                content = base[child['pos']:child['pos']+child['length']]
                if child['sig'] == 'ITEM':
                    content += records
                elif child['sig'] == 'PTCH':
                    content = struct.pack('<2I', fixture.TIDS['T*'], len(refs))
                    content += struct.pack('<' + str(len(refs)) + 'I', *refs)
                children.append(fixture._section(child['sig'].encode(), content, False))
            raw = b''.join(children)
        parts.append(fixture._section(section['sig'].encode(), raw, bool(section['subs'])))
    return fixture._section(b'TAG0', b''.join(parts), True)


def test_vertex_face_lifecycle_preserves_materials_and_other_subparts(collision_source):
    before = CollisionDocument(collision_source)
    assert len(before.meshes) == 2
    output = before.export({0: {'vertices': [[0,2,0], [1,0,0], [0,0,1], [0,2,0]],
                                'faces': [[0,1,2], [3,1,2]],
                                'vertex_sources': [0,1,2,0], 'face_sources': [0,0]}})
    edited = CollisionDocument(output)
    assert edited.meshes[0]['vertices'] == [[0,2,0,0], [1,0,0,0], [0,0,1,0], [0,2,0,0]]
    assert edited.meshes[0]['faces'] == [[0,1,2,555], [3,1,2,555]]
    assert edited.meshes[1] == before.meshes[1]
    old_material = before._value(before.materials[1])
    assert edited._value(edited.materials[1]) == old_material
    assert edited._value(edited.materials[0])['vertexDataBuffer'] == [17,18,19,17]
    assert edited._value(edited._field(edited.shape, 'cachedNumChildShapes')) == 3
    mopp = edited._value(edited.code)
    assert query(bytes(mopp['data']), mopp['info']['offset'], [-100]*3, [100]*3) == {0, 1, 1 << 20}
    removed = edited.export({0: {'vertices': [[0,2,0], [1,0,0], [0,0,1]], 'faces': [[0,1,2]]}})
    reloaded = CollisionDocument(removed)
    assert len(reloaded.meshes[0]['vertices']) == 3
    assert len(reloaded.meshes[0]['faces']) == 1
    assert reloaded._value(reloaded.materials[0])['vertexDataBuffer'] == [17,18,19]
    assert before.export({}) == collision_source


def test_bad_collision_edit_keeps_original_document_usable(collision_source):
    document = CollisionDocument(collision_source)
    with pytest.raises(FormatError, match='vertex range'):
        document.export({0: {'faces': [[100, 1, 2]]}})
    assert document.export({}) == collision_source
    output = document.export({0: {'vertices': [[0,5,0], [1,0,0], [0,0,1]]}})
    assert CollisionDocument(output).meshes[0]['vertices'][0][1] == 5


def test_missing_subpart_is_a_format_error(collision_source):
    document = CollisionDocument(collision_source)
    _, at = document._field(document.shape, 'meshstorage')
    index, = struct.unpack_from('<i', document.data, at)
    data = bytearray(document.data)
    struct.pack_into('<i', data, document.entries[index]['pos']+8, 0)
    with pytest.raises(FormatError, match='missing mesh subpart'):
        CollisionDocument(data)


def test_same_mesh_independent_coordinates_and_metadata_combine(collision_source):
    document = CollisionDocument(collision_source)
    a = document.export({0: {'vertices': [[2,0,0], [1,0,0], [0,0,1]]}})
    b = document.export({0: {'vertices': [[0,3,0], [1,0,0], [0,0,1]],
                             'vertex_flags': [[99], [18], [19]], 'face_tags': [777]}})
    output, conflicts = collision_merge.merge(collision_source, [('A', a), ('B', b)])
    merged = CollisionDocument(output)
    assert not conflicts
    assert merged.meshes[0]['vertices'][0] == [2,3,0,0]
    assert merged.meshes[0]['faces'][0][3] == 777
    assert merged._value(merged.materials[0])['vertexDataBuffer'] == [99,18,19]
    assert merged.meshes[1] == document.meshes[1]


def test_collision_conflicts_report_exact_owners_and_use_load_order(collision_source):
    document = CollisionDocument(collision_source)
    a = document.export({0: {'vertices': [[2,0,0], [1,0,0], [0,0,1]]}})
    b = document.export({0: {'vertices': [[3,0,0], [1,0,0], [0,0,1]]}})
    output, conflicts = collision_merge.merge(collision_source, [('A', a), ('B', b)])
    assert conflicts == [('Collision mesh 1, vertices 0:0', ['A', 'B'])]
    assert CollisionDocument(output).meshes[0]['vertices'][0][0] == 3
    added = document.export({0: {'faces': [[0,1,2], [0,1,2]], 'face_sources': [0,0]}})
    output, conflicts = collision_merge.merge(collision_source, [('A', a), ('Add', added)])
    assert conflicts == [('Collision mesh 1', ['A', 'Add'])]
    assert len(CollisionDocument(output).meshes[0]['faces']) == 2


def split_fixture(source):
    header = bytearray(b'BHF307D7R6\0\0\x74\0\0\0' + struct.pack('<4I', 2,0,0,0) + bytes(48))
    body = bytearray(b'BDF307D7R6\0\0' + bytes(4))
    for index in range(2):
        body += bytes((-len(body)) % 16)
        offset = len(body)
        body += source
        path_at = len(header)
        header += f'map/h000{index}a10.hkx'.encode() + b'\0'
        struct.pack_into('<6I', header, 32+index*24, 64,len(source),offset,index,path_at,len(source))
    return bytes(header), bytes(body)


def test_split_collision_members_compose_without_overwriting_each_other(collision_source):
    header, body = split_fixture(collision_source)
    archive = collision_archive.CollisionArchive(header, body)
    a = CollisionDocument(collision_source).export({0: {'vertices': [[2,0,0], [1,0,0], [0,0,1]]}})
    b = CollisionDocument(collision_source).export({0: {'vertices': [[0,3,0], [1,0,0], [0,0,1]]}})
    first = archive.replace({'h0000a10': a})
    second = archive.replace({'h0001a10': b})
    output_header, output_body, conflicts = collision_archive.compose(header, body, [('A', *first), ('B', *second)])
    combined = collision_archive.CollisionArchive(output_header, output_body)
    assert not conflicts
    assert CollisionDocument(combined.member('h0000a10')).meshes[0]['vertices'][0][0] == 2
    assert CollisionDocument(combined.member('h0001a10')).meshes[0]['vertices'][0][1] == 3
    assert [(key, row['name'], row['id']) for key, row in combined.members.items()] == [
        (key, row['name'], row['id']) for key, row in archive.members.items()]
    assert combined.replace({}) == (output_header, output_body)


def test_split_collision_bad_bounds_and_missing_members_fail_locally(collision_source):
    header, body = split_fixture(collision_source)
    damaged = bytearray(header)
    struct.pack_into('<I', damaged, 40, len(body)+100)
    with pytest.raises(FormatError, match='bounds'):
        collision_archive.CollisionArchive(damaged, body)
    archive = collision_archive.CollisionArchive(header, body)
    with pytest.raises(FormatError, match='Unknown'):
        archive.replace({'h_missing': collision_source})
    assert archive.replace({}) == (header, body)


def test_collision_pair_targets_are_canonical():
    header = Path('map/m10_00_00_00/h10_00_00_00.hkxbhd')
    body = header.with_suffix('.hkxbdt')
    assert collision_archive.pair(header) == (header, body)
    assert collision_archive.pair(body) == (header, body)
    assert collision_archive.header_for(Path('map/m10_00_00_00/h11_00_00_00.hkxbhd')) is None


def test_conflict_inspection_never_rebuilds_collision_physics(collision_source, monkeypatch, tmp_path):
    from plugins.ds1 import mod_loader
    header = Path('map/m10_00_00_00/h10_00_00_00.hkxbhd')
    body = header.with_suffix('.hkxbdt')
    raw_header, raw_body = split_fixture(collision_source)
    archive = collision_archive.CollisionArchive(raw_header, raw_body)
    variants = []
    for name, value in (('A', 2), ('B', 3)):
        changed = CollisionDocument(collision_source).export({0: {'vertices': [[value,0,0], [1,0,0], [0,0,1]]}})
        other_header, other_body = archive.replace({'h0000a10':changed})
        variants.append(mod_loader.Mod(name, tmp_path/name, {header:other_header, body:other_body}))

    def no_export(*args, **kwargs):
        raise AssertionError('Inspecting conflicts must not compile physics')

    monkeypatch.setattr(CollisionDocument, 'export', no_export)
    result = mod_loader.compose({header:raw_header, body:raw_body}, variants, conflicts_only=True)
    assert not result.files
    assert result.conflicts[0].mods == ['A', 'B']


def test_installed_collision_pair_uses_shared_memory_and_disk_cache(collision_source, tmp_path, monkeypatch):
    from collections import OrderedDict
    from plugins.ds1 import mod_loader
    header = Path('map/m10_00_00_00/h10_00_00_00.hkxbhd')
    body = header.with_suffix('.hkxbdt')
    original_header, original_body = split_fixture(collision_source)
    game = tmp_path/'game'
    (game/header).parent.mkdir(parents=True)
    (game/header).write_bytes(original_header)
    (game/body).write_bytes(original_body)
    archive = collision_archive.CollisionArchive(original_header, original_body)
    changed = CollisionDocument(collision_source).export({0: {'vertices': [[2,0,0], [1,0,0], [0,0,1]]}})
    new_header, new_body = archive.replace({'h0000a10': changed})
    mod = mod_loader.Mod('Collision', tmp_path/'mod', {header:new_header, body:new_body})
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    first = mod_loader.compose_installed(game, [mod], cache_root=tmp_path/'cache')
    assert header in first.files and body in first.files
    expected = dict(first.files)

    def no_rebuild(*args, **kwargs):
        raise AssertionError('Unchanged collision pair must reuse its composed output')

    monkeypatch.setattr(collision_archive, 'compose', no_rebuild)
    assert mod_loader.compose_installed(game, [mod], cache_root=tmp_path/'cache').files == expected
    mod_loader._compose_cache.clear()
    assert mod_loader.compose_installed(game, [mod], cache_root=tmp_path/'cache').files == expected
    assert (game/header).read_bytes() == original_header
    assert (game/body).read_bytes() == original_body


def test_one_broken_collision_owner_does_not_implicate_healthy_mod(collision_source, tmp_path):
    from core.mod_builds import ModBuildError
    from plugins.ds1 import mod_loader
    header = Path('map/m10_00_00_00/h10_00_00_00.hkxbhd')
    body = header.with_suffix('.hkxbdt')
    raw_header, raw_body = split_fixture(collision_source)
    game = tmp_path/'game'
    (game/header).parent.mkdir(parents=True)
    (game/header).write_bytes(raw_header)
    (game/body).write_bytes(raw_body)
    healthy = mod_loader.Mod('Healthy', tmp_path/'healthy', {header:raw_header, body:raw_body})
    broken = mod_loader.Mod('Broken', tmp_path/'broken', {header:b'bad header', body:raw_body})
    with pytest.raises(ModBuildError) as caught:
        mod_loader.compose_installed(game, [healthy, broken])
    assert caught.value.folders == (broken.folder,)
    assert not mod_loader.compose_installed(game, [healthy]).files
    assert (game/header).read_bytes() == raw_header
    assert (game/body).read_bytes() == raw_body


@pytest.mark.parametrize('files', [
    [['opaque.bin', -1]], [['opaque.bin', 999]], [['elsewhere.bin', 3]],
    [['opaque.bin', 1], ['opaque.bin', 2]], [['opaque.bin', True]],
])
def test_bad_group_cache_file_table_is_disposable(tmp_path, monkeypatch, files):
    from collections import OrderedDict
    from plugins.ds1 import composition_cache, mod_loader
    relative = Path('opaque.bin')
    monkeypatch.setattr(mod_loader, '_compose_cache', OrderedDict())
    monkeypatch.setattr(mod_loader, '_compose_cache_bytes', 0)
    monkeypatch.setattr(composition_cache, 'load', lambda *_: json_bytes(files))
    monkeypatch.setattr(composition_cache, 'store', lambda *_: None)
    mod = mod_loader.Mod('Healthy', tmp_path, {relative:b'fresh'})
    assert mod_loader._compose_files({relative:None}, [mod], False, tmp_path).files == {relative:b'fresh'}


def json_bytes(files):
    import json
    return json.dumps({'files':files, 'conflicts':[]}).encode() + b'\ncached'
