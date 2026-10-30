"""DS1 NVM triangle geometry. Header and face layout: SoulsFormats NVM."""
import base64
import math
import struct

from .formats import FormatError


def geometry(source):
    data = bytes(source)
    if len(data) < 128:
        raise FormatError('Navigation mesh header is truncated')
    version, vertices, vertex_at, faces, face_at = struct.unpack_from('<5i', data)
    if version != 1 or vertex_at != 128 or face_at != 128+vertices*12:
        raise FormatError('Unsupported navigation mesh header')
    if not 0 <= vertices <= 1_000_000 or not 0 <= faces <= 1_000_000 or face_at+28*faces > len(data):
        raise FormatError('Navigation geometry is outside the file')
    positions = data[vertex_at:face_at]
    if not all(math.isfinite(value[0]) for value in struct.iter_unpack('<f', positions)):
        raise FormatError('Navigation mesh has invalid coordinates')
    indices = []
    for offset in range(face_at, face_at+28*faces, 28):
        triangle = struct.unpack_from('<3i', data, offset)
        if not all(0 <= index < vertices for index in triangle):
            raise FormatError('Navigation face points outside its vertices')
        indices.extend(triangle)
    return {'meshes': [{'positions': base64.b64encode(positions).decode('ascii'),
                        'indices': base64.b64encode(struct.pack(f'<{len(indices)}I', *indices)).decode('ascii'),
                        'normals': '', 'layer': 'navigation', 'mat_def': '', 'cull': False}], 'notes': []}
