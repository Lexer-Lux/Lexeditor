"""Edit DSR collision vertices/faces without replacing its physics metadata."""
import math
import struct

from . import collision_mopp, hkx, hkx_write, map_collision
from .formats import FormatError, deflate, inflate


class CollisionDocument:
    def __init__(self, source):
        if len(source) > hkx.MAX_FILE:
            raise FormatError('Collision geometry is too large')
        self.source = bytes(source)
        self.data = inflate(source) if source[:4] == b'DCX\0' else bytes(source)
        self.entries = hkx._peek_tables(self.data)
        self.reader = hkx._TagReader(self.data, 0, [], self.entries)
        self.patches, self.replacements = [], {}
        shapes = [entry for entry in self.entries if entry['type'] is not None
                  and entry['type'].name == 'CustomParamStorageExtendedMeshShape']
        codes = [entry for entry in self.entries if entry['type'] is not None
                 and entry['type'].name == 'hkpMoppCode']
        if len(shapes) != 1 or len(codes) != 1:
            raise FormatError('Collision editing needs one extended mesh and its spatial index')
        self.shape = (shapes[0]['type'], shapes[0]['pos'])
        self.code = (codes[0]['type'], codes[0]['pos'])
        self.storage = self._objects(self.shape, 'meshstorage')
        self.parts = self._objects(self.shape, 'trianglesSubparts')
        self.materials = self._objects(self.shape, 'materialArray')
        if not self.storage or len(self.storage) != len(self.parts) or len(self.materials) != len(self.parts):
            raise FormatError('Collision mesh subparts do not match their physics metadata')
        if any(owner is None for owners in (self.storage, self.parts, self.materials) for owner in owners):
            raise FormatError('Collision metadata contains a missing mesh subpart')
        self.meshes = []
        for storage in self.storage:
            values = self._value(storage)
            index_field = next((key for key in ('indices8', 'indices16', 'indices32') if values.get(key)), None)
            if index_field is None:
                raise FormatError('Collision mesh has no triangle indices')
            indices = values[index_field]
            vertices = values.get('vertices') or []
            if not vertices or any(len(vertex) != 4 for vertex in vertices) or len(indices) % 4:
                raise FormatError('Collision mesh has invalid triangle storage')
            self.meshes.append({'vertices': vertices,
                                'faces': [indices[i:i+4] for i in range(0, len(indices), 4)],
                                'index_field': index_field})

    def _field(self, owner, name):
        field = hkx._peek_field(owner[0], name)
        if field is None:
            raise FormatError(f'Collision metadata is missing {name}')
        return field['type'], owner[1] + field['offset']

    def _value(self, owner):
        return self.reader._value(owner[0], owner[1], 0)[0]

    def _objects(self, owner, name):
        kind, at = self._field(owner, name)
        ref = hkx._peek_ref(self.data, self.entries, kind, at)
        if ref is None:
            return []
        return [hkx._peek_element(self.data, self.entries, ref, i) for i in range(ref[2])]

    def _array(self, owner, name, payload, count):
        kind, at = self._field(owner, name)
        if kind.kind != hkx.ARRAY or kind.fixed:
            raise FormatError('Collision metadata has an unexpected array layout')
        index, = struct.unpack_from('<i', self.data, at)
        if not 0 < index < len(self.entries):
            raise FormatError('Collision array has no storage item')
        value = (bytes(payload), count)
        if index in self.replacements and self.replacements[index] != value:
            raise FormatError('Collision subparts share incompatible edited arrays')
        self.replacements[index] = value

    def _patch(self, owner, name, values):
        kind, at = self._field(owner, name)
        if kind.kind == hkx.INT:
            code = {8: 'b', 16: 'h', 32: 'i', 64: 'q'}[kind.bits]
            if not kind.signed:
                code = code.upper()
            payload = struct.pack('<' + code, values)
        elif kind.kind == hkx.ARRAY and kind.fixed and kind.fixed_size == 4:
            payload = struct.pack('<4f', *values)
        else:
            raise FormatError('Collision metadata has an unexpected scalar layout')
        self.patches.append((at, payload))

    @staticmethod
    def _sources(update, key, old_count, new_count):
        found = update.get(key, list(range(new_count)))
        if (len(found) != new_count or any(type(i) is not int or not 0 <= i < old_count for i in found)):
            raise FormatError('Added collision elements need an existing element to copy metadata from')
        return found

    def export(self, updates):
        """updates maps mesh indices to vertices/faces and metadata source IDs.

        New vertices/faces copy their selected source element's game metadata;
        moving/deleting elements never silently changes its material flags.
        """
        if not updates:
            return self.source
        if any(type(i) is not int or not 0 <= i < len(self.meshes) for i in updates):
            raise FormatError('Unknown collision mesh')
        self.patches, self.replacements = [], {}
        welding = self._value(self._field(self.shape, 'weldingInfo'))
        if welding:
            raise FormatError('This collision uses welded edges that need regeneration before editing')
        final = []
        for index, (storage, part, material, old) in enumerate(zip(
                self.storage, self.parts, self.materials, self.meshes)):
            update = updates.get(index)
            if update is None:
                final.append((old['vertices'], old['faces']))
                continue
            vertices = update.get('vertices', old['vertices'])
            faces = update.get('faces', old['faces'])
            if not vertices or not faces:
                raise FormatError('A collision mesh needs vertices and faces')
            vertex_sources = self._sources(update, 'vertex_sources', len(old['vertices']), len(vertices))
            face_sources = self._sources(update, 'face_sources', len(old['faces']), len(faces))
            new_vertices = []
            for vertex, previous in zip(vertices, vertex_sources):
                if len(vertex) not in (3, 4):
                    raise FormatError('Collision vertices need three coordinates')
                coords = [collision_mopp._float32(value) for value in vertex[:3]]
                new_vertices.append(coords + [old['vertices'][previous][3]])
            width = {'indices8': 1, 'indices16': 2, 'indices32': 4}[old['index_field']]
            maximum = (1 << (width*8)) - 1
            new_faces = []
            for face, previous in zip(faces, face_sources):
                if len(face) not in (3, 4) or any(type(i) is not int or not 0 <= i < len(vertices)
                                               or i > maximum for i in face[:3]):
                    raise FormatError('Collision face points outside its supported vertex range')
                new_faces.append(list(face[:3]) + [old['faces'][previous][3]])
            tags = update.get('face_tags', [face[3] for face in new_faces])
            if len(tags) != len(new_faces) or any(type(value) is not int or not 0 <= value <= maximum for value in tags):
                raise FormatError('Collision face metadata is invalid')
            for face, tag in zip(new_faces, tags):
                face[3] = tag
            vertex_payload = b''.join(struct.pack('<4f', *vertex) for vertex in new_vertices)
            index_payload = b''.join(struct.pack('<4' + {1: 'B', 2: 'H', 4: 'I'}[width], *face)
                                     for face in new_faces)
            self._array(storage, 'vertices', vertex_payload, len(new_vertices))
            self._array(storage, old['index_field'], index_payload, len(new_faces)*4)
            parameter = self._value(material)
            stride = parameter['vertexDataStride']
            flags = parameter['vertexDataBuffer']
            if type(stride) is not int or not 1 <= stride <= 256 or len(flags) != len(old['vertices'])*stride:
                raise FormatError('Collision vertex metadata has an unsupported stride')
            flag_rows = update.get('vertex_flags', [flags[source*stride:(source+1)*stride]
                                                    for source in vertex_sources])
            if (len(flag_rows) != len(new_vertices) or any(len(row) != stride or any(
                    type(value) is not int or not 0 <= value <= 255 for value in row) for row in flag_rows)):
                raise FormatError('Collision vertex metadata is invalid')
            self._array(material, 'vertexDataBuffer', bytes(value for row in flag_rows for value in row),
                        len(vertex_sources)*stride)
            if parameter.get('primitiveDataBuffer') and len(new_faces) != len(old['faces']):
                raise FormatError('This collision has primitive metadata that cannot yet be resized')
            values = self._value(storage)
            for name, code in (('materialIndices', 'B'), ('materialIndices16', 'H')):
                if values.get(name):
                    if len(values[name]) != len(old['faces']):
                        raise FormatError('Collision face metadata has an unsupported layout')
                    payload = struct.pack('<' + str(len(face_sources)) + code,
                                          *(values[name][source] for source in face_sources))
                    self._array(storage, name, payload, len(face_sources))
            self._patch(part, 'numVertices', len(new_vertices))
            self._patch(part, 'numTriangleShapes', len(new_faces))
            if index == 0:
                embedded = self._field(self.shape, 'embeddedTrianglesSubpart')
                self._patch(embedded, 'numVertices', len(new_vertices))
                self._patch(embedded, 'numTriangleShapes', len(new_faces))
            final.append((new_vertices, new_faces))
        # FromSoft's map subparts normally use identity transforms. Build
        # bounds from the actual transform too, retaining it in the output.
        world = []
        for (vertices, faces), part in zip(final, self.parts):
            values = self._value(part)
            transform = values['transform']
            translation, scale, rotation = (transform[key] for key in ('translation', 'scale', 'rotation'))
            if any(not math.isfinite(value) for vector in (translation, scale, rotation) for value in vector):
                raise FormatError('Collision has a non-finite subpart transform')
            if any(values.get('extrusion', ())):
                raise FormatError('This collision uses extruded triangles that need regenerated bounds')
            qx, qy, qz, qw = rotation
            if abs(sum(value*value for value in rotation)-1) > 1e-4:
                raise FormatError('Collision has an invalid subpart rotation')
            points = []
            for vertex in vertices:
                x, y, z = [vertex[i]*scale[i] for i in range(3)]
                tx, ty, tz = 2*(qy*z-qz*y), 2*(qz*x-qx*z), 2*(qx*y-qy*x)
                points.append((x+qw*tx+qy*tz-qz*ty+translation[0],
                               y+qw*ty+qz*tx-qx*tz+translation[1],
                               z+qw*tz+qx*ty-qy*tx+translation[2]))
            world.append((points, faces))
        radius = self._value(self._field(self.shape, 'triangleRadius'))
        bits = self._value(self._field(self.shape, 'numBitsForSubpartIndex'))
        code, offset = collision_mopp.build(world, radius=radius, subpart_bits=bits)
        self._array(self.code, 'data', code, len(code))
        self._patch(self._field(self.code, 'info'), 'offset', offset)
        for name, vector in (('aabbCenter', [0]*4), ('aabbHalfExtents', [0]*4)):
            for axis in range(3):
                low = min(point[axis] for vertices, _ in world for point in vertices)
                high = max(point[axis] for vertices, _ in world for point in vertices)
                vector[axis] = (high+low)/2 if name == 'aabbCenter' else (high-low)/2+radius
            self._patch(self.shape, name, vector)
        self._patch(self.shape, 'cachedNumChildShapes', sum(len(faces) for _, faces in final))
        result = hkx_write.replace_items(self.data, self.replacements, self.patches)
        # Read the edited geometry before handing it to any project writer.
        map_collision.meshes(result)
        return deflate(self.source, result) if self.source[:4] == b'DCX\0' else result
