"""Synthetic Havok TAG0 files; no proprietary game bytes."""
import struct


def append_items(base, blobs):
    """Append typed fixture items and their reference slots to a TAG0 file."""
    from plugins.ds1 import hkx
    root,_=hkx._section(base,0)
    data_part=next(part for part in root['subs'] if part['sig']=='DATA')
    data=bytearray(base[data_part['pos']:data_part['pos']+data_part['length']])
    records,refs=bytearray(),[]
    for kind,count,blob,slots in blobs:
        data+=bytes((-len(data))%16)
        at=len(data)
        records+=struct.pack('<3I',TIDS[kind],at,count)
        refs.extend(at+slot for slot in slots)
        data+=blob
    patch=struct.pack('<2I',TIDS['T*'],len(refs))+struct.pack('<'+str(len(refs))+'I',*refs) if refs else b''
    sections=[]
    for section in root['subs']:
        payload=base[section['pos']:section['pos']+section['length']]
        if section['sig']=='DATA':
            payload=bytes(data)
        elif section['sig']=='INDX':
            children=[]
            had_patch=False
            for child in section['subs']:
                raw=base[child['pos']:child['pos']+child['length']]
                if child['sig']=='ITEM':raw+=records
                if child['sig']=='PTCH':raw+=patch;had_patch=True
                children.append(_section(child['sig'].encode(),raw,False))
            if patch and not had_patch:children.append(_section(b'PTCH',patch,False))
            payload=b''.join(children)
        sections.append(_section(section['sig'].encode(),payload,bool(section['subs'])))
    return _section(b'TAG0',b''.join(sections),True)


def _pack(value):
    if value < 0x80:
        return bytes([value])
    if value <= 0x3FFF:
        return bytes([0x80 | (value >> 8), value & 0xFF])
    if value <= 0x1FFFFF:
        return bytes([0xC0 | (value >> 16), (value >> 8) & 0xFF, value & 0xFF])
    raise ValueError('fixture value too large')


def _section(sig, payload, container):
    flags = len(payload) + 8 if container else 0xC0000000 | (len(payload) + 8)
    return struct.pack('>I', flags) + sig + payload


def _vec4(values):
    return struct.pack('<4f', *values)


def _qstransform(trans, rot, scale):
    return _vec4(trans) + _vec4(rot) + _vec4(scale)


# (tag, display name, size, fields-or-format-or-subtype). Array entries
# share the display name hkArray with one subtype each.
TYPES = [
    ('class', 'hkRootLevelContainer', 4, [('namedVariants', 0, 'A_NamedVariant')]),
    ('class', 'hkRootLevelContainer::NamedVariant', 8, [('name', 0, 'hkStringPtr'),
                                                        ('variant', 4, 'hkRefVariant')]),
    ('class', 'hkaAnimationContainer', 12, [('skeletons', 0, 'A_Skel'),
                                            ('animations', 4, 'A_Anim'),
                                            ('bindings', 8, 'A_Bind')]),
    ('class', 'hkaSkeleton', 16, [('name', 0, 'hkStringPtr'), ('parentIndices', 4, 'A_i16'),
                                  ('bones', 8, 'A_Bone'), ('referencePose', 12, 'A_Qs')]),
    ('class', 'hkaBone', 4, [('name', 0, 'hkStringPtr')]),
    ('class', 'hkQsTransformf', 48, [('translation', 0, 'hkVector4f'),
                                     ('rotation', 16, 'hkVector4f'),
                                     ('scale', 32, 'hkVector4f')]),
    ('vec4', 'hkVector4f', 16, 'float'),
    ('class', 'hkaSplineCompressedAnimation', 48,
     [('duration', 0, 'float'), ('numberOfTransformTracks', 4, 'hkInt32'),
      ('numberOfFloatTracks', 8, 'hkInt32'), ('numFrames', 12, 'hkInt32'),
      ('numBlocks', 16, 'hkInt32'), ('maxFramesPerBlock', 20, 'hkInt32'),
      ('maskAndQuantizationSize', 24, 'hkUint32'), ('blockDuration', 28, 'float'),
      ('blockInverseDuration', 32, 'float'), ('frameDuration', 36, 'float'),
      ('blockOffsets', 40, 'A_u32'), ('data', 44, 'A_u8')]),
    ('class', 'hkaInterleavedUncompressedAnimation', 12,
     [('duration', 0, 'float'), ('numberOfTransformTracks', 4, 'hkInt32'),
      ('transforms', 8, 'A_Qs')]),
    ('class', 'hkaAnimationBinding', 9,
     [('originalSkeletonName', 0, 'hkStringPtr'),
      ('transformTrackToBoneIndices', 4, 'A_i16'), ('blendHint', 8, 'hkInt8')]),
    ('prim', 'hkInt16', 2, 0x4204),
    ('prim', 'hkInt32', 4, 0x8204),
    ('prim', 'hkUint32', 4, 0x8004),
    ('prim', 'hkUint8', 1, 0x2004),
    ('prim', 'float', 4, 0x174605),
    ('prim', 'hkInt8', 1, 0x2204),
    ('prim', 'hkStringPtr', 8, 0x03),
    ('prim', 'hkRefVariant', 8, 0x06),
    ('array', 'A_NamedVariant', 'hkRootLevelContainer::NamedVariant'),
    ('array', 'A_Skel', 'hkaSkeleton'),
    ('array', 'A_Anim', 'hkaSplineCompressedAnimation'),
    ('array', 'A_Bind', 'hkaAnimationBinding'),
    ('array', 'A_Bone', 'hkaBone'),
    ('array', 'A_Qs', 'hkQsTransformf'),
    ('array', 'A_i16', 'hkInt16'),
    ('array', 'A_u32', 'hkUint32'),
    ('array', 'A_u8', 'hkUint8'),
]

TIDS = {}
for _position, _entry in enumerate(TYPES):
    _key = _entry[1] if _entry[0] != 'array' else _entry[1]
    TIDS[_key] = _position + 1


def _spline_data():
    """One block, two tracks: track 0 fully static, track 1 with an
    X channel running 0 to 1 across the block's four frames."""
    out = bytearray()
    out += bytes([0x00, 0x07, 0x01, 0x00])  # track 0: static pos/rot, skeleton scale
    out += bytes([0x00, 0x16, 0x00, 0x00])  # track 1: spline X, static Y/Z
    out += struct.pack('<3f', 0.0, 1.0, 0.0)  # track 0 sits on the bind pose
    out += struct.pack('<I', 0)  # POLAR32 identity
    out += struct.pack('<H', 1) + bytes([1, 0, 0, 3, 3])
    out += b'\0'  # knots pad to 4
    out += struct.pack('<2f', 0.0, 1.0)  # X bounds
    out += struct.pack('<2f', 5.0, 6.0)  # static Y, Z
    out += bytes([0, 255])  # X samples
    out += b'\0\0'  # samples pad to 4
    while len(out) % 16:
        out += b'\0'
    return bytes(out)


def build_tag0(extra_data=0):
    """One skeleton (root/child), one static-plus-curve spline anim and
    one two-frame interleaved anim, each with a binding, in two variants.

    extra_data pads the spline curve blob, the way a long motion's whole
    curve set packs into one hkUint8 item past any object count."""
    pool = list(dict.fromkeys('hkArray' if tag == 'array' else name
                              for tag, name, *_ in TYPES))
    tnam = _pack(len(TYPES))
    for tag, name, *_ in TYPES:
        tnam += _pack(pool.index('hkArray' if tag == 'array' else name)) + _pack(0)
    tstr = b''.join(text.encode() + b'\0' for text in pool)
    fields = []
    for entry in TYPES:
        if entry[0] == 'class':
            for fname, _off, _ftype in entry[3]:
                if fname not in fields:
                    fields.append(fname)
    fstr = b''.join(text.encode() + b'\0' for text in fields)

    tbod = b''
    for entry in TYPES:
        tag, name = entry[0], entry[1]
        if tag == 'class':
            _size, spec = entry[2], entry[3]
            tbod += _pack(TIDS[name]) + _pack(0) + _pack(41) + _pack(0x7)
            tbod += _pack(_size) + _pack(4) + bytes([len(spec)])
            for fname, off, ftype in spec:
                tbod += _pack(fields.index(fname)) + _pack(0) + _pack(off) + _pack(TIDS[ftype])
        elif tag in ('vec4','fixed'):
            _size, sub = entry[2], entry[3]
            count = entry[4] if tag == 'fixed' else 4
            tbod += _pack(TIDS[name]) + _pack(0) + _pack(11) + _pack((count << 8)|0x28)
            tbod += _pack(TIDS[sub]) + _pack(_size) + _pack(4)
        elif tag == 'prim':
            _size, info = entry[2], entry[3]
            tbod += _pack(TIDS[name]) + _pack(0) + _pack(9) + _pack(info)
            tbod += _pack(_size) + _pack(_size)
        else:
            tbod += _pack(TIDS[name]) + _pack(0) + _pack(11) + _pack(0x8)
            tbod += _pack(TIDS[entry[2]]) + _pack(16) + _pack(4)

    spline = _spline_data() + bytes(extra_data)
    pose0 = _qstransform((0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (2.0, 2.0, 2.0, 1.0))
    pose1 = _qstransform((0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0))
    step0 = _qstransform((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0))
    step1 = _qstransform((1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), (1.0, 1.0, 1.0, 1.0))
    # (name, type, count, blob builder over item numbers).
    spec = [
        ('root', 'hkRootLevelContainer', 1, lambda m: struct.pack('<i', m['variants'])),
        ('variants', 'hkRootLevelContainer::NamedVariant', 2,
         lambda m: struct.pack('<4i', m['s_variant0'], m['container0'],
                               m['s_variant1'], m['container1'])),
        ('container0', 'hkaAnimationContainer', 1,
         lambda m: struct.pack('<3i', m['skels'], m['splines'], m['binds0'])),
        ('container1', 'hkaAnimationContainer', 1,
         lambda m: struct.pack('<3i', 0, m['inters'], m['binds1'])),
        ('skels', 'hkaSkeleton', 1, lambda m: struct.pack('<4i', m['s_master'], m['parents'],
                                                         m['bones'], m['pose'])),
        ('splines', 'hkaSplineCompressedAnimation', 1,
         lambda m: struct.pack('<f6i3f2i', 0.1, 2, 0, 4, 1, 4, 0, 0.1, 10.0, 1 / 30,
                               m['offsets'], m['data'])),
        ('binds0', 'hkaAnimationBinding', 1,
         lambda m: struct.pack('<2i', m['s_master'], m['map0']) + b'\0'),
        ('inters', 'hkaInterleavedUncompressedAnimation', 1,
         lambda m: struct.pack('<f', 1.0) + struct.pack('<2i', 1, m['transforms'])),
        ('binds1', 'hkaAnimationBinding', 1,
         lambda m: struct.pack('<2i', m['s_master'], m['map1']) + b'\0'),
        ('parents', 'hkInt16', 2, lambda m: struct.pack('<2h', -1, 0)),
        ('bones', 'hkaBone', 2, lambda m: struct.pack('<2i', m['s_root'], m['s_child'])),
        ('pose', 'hkQsTransformf', 2, lambda m: pose0 + pose1),
        ('offsets', 'hkUint32', 1, lambda m: struct.pack('<I', 0)),
        ('data', 'hkUint8', len(spline), lambda m: spline),
        ('transforms', 'hkQsTransformf', 2, lambda m: step0 + step1),
        ('map0', 'hkInt16', 2, lambda m: struct.pack('<2h', 0, 1)),
        ('map1', 'hkInt16', 1, lambda m: struct.pack('<h', 1)),
        ('s_variant0', 'hkUint8', 9, lambda m: b'Variant0\0'),
        ('s_variant1', 'hkUint8', 9, lambda m: b'Variant1\0'),
        ('s_master', 'hkUint8', 7, lambda m: b'Master\0'),
        ('s_root', 'hkUint8', 5, lambda m: b'root\0'),
        ('s_child', 'hkUint8', 6, lambda m: b'child\0'),
    ]
    numbers = {name: index + 1 for index, (name, _k, _c, _f) in enumerate(spec)}
    blobs = [fn(numbers) for _n, _k, _c, fn in spec]
    payload = b''.join(blobs)
    entries = [struct.pack('<iIi', 0, 0, 0)]
    offset = 0
    for (_name, kind, count, _fn), blob in zip(spec, blobs):
        entries.append(struct.pack('<iIi', TIDS[kind], offset, count))
        offset += len(blob)

    type_sec = (_section(b'TPTR', b'', False) + _section(b'TSTR', tstr, False)
                + _section(b'TNAM', tnam, False) + _section(b'FSTR', fstr, False)
                + _section(b'TBOD', tbod, False) + _section(b'THSH', _pack(0), False)
                + _section(b'TPAD', b'', False))
    index = _section(b'ITEM', b''.join(entries), False) + _section(b'PTCH', b'', False)
    return (_section(b'TAG0', _section(b'SDKV', b'20150100', False)
                     + _section(b'DATA', payload, False) + _section(b'TYPE', type_sec, True)
                     + _section(b'INDX', index, True), True))
