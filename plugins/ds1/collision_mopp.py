"""Build the spatial index used by DSR's triangle collision shapes.

The bytecode layout is documented by soulstruct-havok's utilities/mopp.py
(v1.5.0). This independent encoder uses root-space bounds and relative jump
trampolines; it needs neither Havok's proprietary compiler nor a new Python.
https://github.com/Grimrukh/soulstruct-havok/blob/v1.5.0/src/soulstruct/havok/utilities/mopp.py
"""
import math
import struct

from .formats import FormatError

MAX_CODE = 32 * 1024 * 1024
ROOT_MAX = (1 << 24) - 1


def _float32(value):
    try:
        result, = struct.unpack('<f', struct.pack('<f', value))
    except (OverflowError, struct.error, TypeError):
        raise FormatError('Collision coordinates exceed the supported range') from None
    if not math.isfinite(result):
        raise FormatError('Collision coordinates must be finite')
    return result


def build(subparts, *, radius=0., subpart_bits=12):
    """Return (bytecode, origin/scale) for (vertices, four-index faces) pairs.

    Shape keys retain the original face and subpart indices. The fourth index
    is metadata, not a vertex. Degenerate faces keep their slot in the mesh
    but are omitted from the index, as they have no collision surface.
    """
    if type(subpart_bits) is not int or not 1 <= subpart_bits <= 16:
        raise FormatError('Collision shape-key subdivision is invalid')
    if not math.isfinite(radius) or radius < 0:
        raise FormatError('Collision triangle radius is invalid')
    if not subparts or len(subparts) > 1 << subpart_bits:
        raise FormatError('Collision has an invalid number of mesh subparts')
    triangle_bits = 32 - subpart_bits
    bounds = []
    for part, (vertices, faces) in enumerate(subparts):
        if len(faces) > 1 << triangle_bits:
            raise FormatError('Collision has too many faces for its shape keys')
        if (len(bounds) + len(faces)) * 80 > MAX_CODE:
            raise FormatError('Collision spatial index is too large')
        points = []
        for vertex in vertices:
            if len(vertex) not in (3, 4):
                raise FormatError('Collision vertices need three coordinates')
            points.append(tuple(_float32(value) for value in vertex[:3]))
        for face_id, face in enumerate(faces):
            if len(face) not in (3, 4) or any(type(i) is not int or not 0 <= i < len(points)
                                           for i in face[:3]):
                raise FormatError('Collision face points outside its vertices')
            triangle = [points[i] for i in face[:3]]
            a = [triangle[1][i] - triangle[0][i] for i in range(3)]
            b = [triangle[2][i] - triangle[0][i] for i in range(3)]
            cross = (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])
            if sum(value*value for value in cross) <= 1e-12:
                continue
            low = tuple(min(p[i] for p in triangle) - radius for i in range(3))
            high = tuple(max(p[i] for p in triangle) + radius for i in range(3))
            bounds.append(((part << triangle_bits) | face_id, low, high))
    if not bounds:
        raise FormatError('Collision needs at least one non-degenerate face')
    low = [min(row[1][i] for row in bounds) for i in range(3)]
    high = [max(row[2][i] for row in bounds) for i in range(3)]
    span = max(max(high[i] - low[i] for i in range(3)), 1e-6)
    margin = max(span * 1e-5, max(abs(v) for v in low + high) * 2e-7, 1e-6)
    origin = tuple(_float32(value - margin) for value in low)
    scale = _float32(254 * 65536 / (span + 2 * margin))
    if scale <= 0:
        raise FormatError('Collision coordinates exceed the supported range')

    def quantize(values, padding):
        # The multiply and subtract round separately on the game's float32
        # path. Include both that result and exact arithmetic before padding.
        result = []
        for i, value in enumerate(values):
            exact = (value - origin[i]) * scale
            rounded = _float32(_float32(value - origin[i]) * scale)
            q = math.floor(min(exact, rounded) if padding < 0 else max(exact, rounded)) + padding
            if q < 0 or q > ROOT_MAX:
                raise FormatError('Collision cannot fit the Havok spatial-index bounds')
            result.append(q)
        return tuple(result)

    rows = [(key, quantize(lo, -4), quantize(hi, 4)) for key, lo, hi in bounds]

    def tree(items):
        minimum = tuple(min(row[1][i] for row in items) for i in range(3))
        maximum = tuple(max(row[2][i] for row in items) for i in range(3))
        code = bytearray()
        for axis in range(3):
            code.append(0x29 + axis)
            code += minimum[axis].to_bytes(3, 'big') + maximum[axis].to_bytes(3, 'big')
        if len(items) == 1:
            key = items[0][0]
            # A 32-bit terminal offset plus the zero terminal covers every
            # subpart without relying on an undocumented TERMINAL32 opcode.
            code += b'\x0b' + key.to_bytes(4, 'big') + b'\x30'
            return bytes(code)
        centers = [[row[1][i] + row[2][i] for row in items] for i in range(3)]
        axis = max(range(3), key=lambda i: max(centers[i]) - min(centers[i]))
        items = sorted(items, key=lambda row: row[1][axis] + row[2][axis])
        split = len(items) // 2
        first, second = items[:split], items[split:]
        left, right = tree(first), tree(second)
        # Both branches point to a JUMP24. This keeps branch addressing
        # independent of subtree size, including indices larger than 64 KiB.
        code += bytes((0x10 + axis, max(row[2][axis] for row in first) >> 16,
                       min(row[1][axis] for row in second) >> 16, 4))
        code += b'\x07\x00\x00\x04'
        code += b'\x07' + len(left).to_bytes(3, 'big')
        code += left + right
        if len(code) > MAX_CODE:
            raise FormatError('Collision spatial index is too large')
        return bytes(code)

    return tree(rows), (*origin, scale)
