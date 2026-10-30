"""Unsaved map collision records; geometry is compiled only while saving."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
import struct

from . import collision_archive, collision_edits, collision_merge, collision_mopp, deployment, record_edits
from .collision_write import CollisionDocument
from .formats import FormatError
from .tweak_mods import checked

MAX_OPEN_BYTES = 256 * 1024 * 1024
POSITION_HELP = 'The vertex position inside the collision model. Each placement adds its own position and rotation.'
METADATA_HELP = 'The purpose of this value is unknown. Keep it unless you know what the game expects.'


def _sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _read(path, limit):
    path = checked(path)
    if not path.exists():
        return None
    size = path.stat().st_size
    if size > limit:
        raise FormatError(f'{path.name} is too large')
    with path.open('rb') as stream:
        data = stream.read(size+1)
        if len(data) != size or stream.read(1):
            raise FormatError(f'{path.name} changed while being read')
    return data


class CollisionStore:
    def __init__(self, game_root, project, writable):
        self.game_root, self.project = game_root, project
        self.writable = writable
        self.units = OrderedDict()

    @staticmethod
    def _header(map_name, model, layer):
        if (not re.fullmatch(r'm\d\d_\d\d_\d\d_\d\d\.msb', map_name or '')
                or not re.fullmatch(r'h[a-zA-Z0-9_]+', model or '') or layer not in ('high','low')):
            raise FormatError('Invalid map collision selection')
        stem = Path(map_name).stem
        prefix = 'h' if layer == 'high' else 'l'
        return Path('map')/stem/(prefix+stem[1:]+'.hkxbhd'), prefix+model[1:]

    @staticmethod
    def table(map_name, model, layer, mesh):
        return f'CollisionMesh|{map_name}|{model}|{layer}|{mesh}'

    @staticmethod
    def parse_table(table):
        parts = str(table).split('|')
        if len(parts) != 5 or parts[0] != 'CollisionMesh' or not parts[4].isdigit():
            raise FormatError('Invalid collision table')
        return (*parts[1:4], int(parts[4]))

    def _reserve(self, size, keep=None):
        if size > MAX_OPEN_BYTES:
            raise FormatError('This collision archive exceeds the editor memory limit')
        while sum(unit['size'] for unit in self.units.values())+size > MAX_OPEN_BYTES:
            unused = next((key for key,unit in self.units.items() if key != keep and not self._dirty(unit)),None)
            if unused is None:
                raise FormatError('Save or discard collision edits before opening more collision archives')
            del self.units[unused]

    def _unit(self, header):
        if header in self.units:
            self.units.move_to_end(header)
            return self.units[header]
        group = collision_archive.pair(header)
        originals, current, sources = {}, {}, []
        raw_paths = [checked(self.project/target) for target in group] if self.project else []
        raw = any(path.exists() for path in raw_paths)
        if raw and not all(path.is_file() for path in raw_paths):
            raise FormatError('A mod collision archive needs both header and data files')
        record_path = checked(self.project/record_edits.FILENAME) if self.project else None
        record_bytes = record_edits.read(record_path) if record_path and record_path.is_file() else None
        records = record_edits.decode(record_bytes) if record_bytes is not None else {}
        spec = records.get(header)
        if raw and spec is not None:
            raise FormatError('A collision cannot have both raw archives and portable records')
        for target in group:
            limit = collision_archive.MAX_HEADER if target == header else collision_archive.MAX_BYTES
            vanilla = checked(deployment.vanilla_source(self.game_root,target))
            original = _read(vanilla,limit)
            if original is None:
                raise FormatError(f'{target}: the installed collision archive is missing')
            originals[target] = original
            sources.append((vanilla,_sha(original),limit))
            if self.project:
                path = checked(self.project/target)
                payload = _read(path,limit)
                sources.append((path,_sha(payload),limit))
            else:
                payload = None
            current[target] = payload if payload is not None else original
        archive = collision_archive.CollisionArchive(*(current[p] for p in group))
        recipes = collision_edits.member_specs(archive,spec) if spec is not None else {}
        size = sum(len(data) for data in [*originals.values(),*current.values()])
        self._reserve(size)
        record_hash = _sha(record_bytes)
        unit = {'archive':archive,'originals':originals,'sources':sources,'spec':deepcopy(spec),
                'raw':raw,'recipes':recipes,'documents':{},'size':size,'record_path':record_path,'record_hash':record_hash}
        self.units[header] = unit
        return unit

    def _locate(self, map_name, model, layer):
        header, prefix = self._header(map_name,model,layer)
        unit = self._unit(header)
        matches = [name for name in unit['archive'].members if name == prefix.lower()
                   or name.startswith(prefix.lower()+'a')]
        if len(matches) != 1:
            raise FormatError(f'No unique {layer} collision member for {model}')
        return header,unit,matches[0]

    def _document(self, map_name, model, layer):
        from . import map_collision
        self._header(map_name,model,layer)
        wanted = 'collisionHigh' if layer == 'high' else 'collisionLow'
        source_info = map_collision.source(self.game_root,self.project,map_name,model,wanted)
        loose = source_info[0] if source_info is not None and source_info[1] is None else None
        header,unit,member = self._locate(map_name,model,layer)
        if member not in unit['documents']:
            source = unit['archive'].member(member)
            output = None
            sources = []
            if loose is not None:
                if member in unit['recipes'] or unit['raw']:
                    raise FormatError('A loose collision member cannot also declare its archive or portable records')
                source = _read(loose,map_collision.hkx.MAX_FILE)
                if source is None:
                    raise FormatError('The loose collision member disappeared')
                origin = self.project if self.project and loose.is_relative_to(self.project) else self.game_root
                output = checked(self.project/loose.relative_to(origin)) if self.project else None
                for path in dict.fromkeys([loose,output] if output is not None else [loose]):
                    raw = source if path == loose else _read(path,map_collision.hkx.MAX_FILE)
                    sources.append((path,_sha(raw),map_collision.hkx.MAX_FILE))
            if member in unit['recipes']:
                document,meshes = collision_edits.open_member(source,unit['recipes'][member])
            else:
                document = CollisionDocument(source)
                meshes = [collision_merge._mesh(document,i) for i in range(len(document.meshes))]
            original_archive = collision_archive.CollisionArchive(*(unit['originals'][p] for p in collision_archive.pair(header)))
            if member not in original_archive.members:
                raise FormatError('New collision members need archive-directory editing before they can be saved')
            original_source = original_archive.member(member)
            vanilla = document if original_source == document.source else CollisionDocument(original_source)
            if loose is not None:
                self._reserve(len(source),header)
                unit['size'] += len(source)
                unit['sources'].extend(sources)
            unit['documents'][member] = {'document':document,'baseline':meshes,'working':deepcopy(meshes),
                'vanilla':[collision_merge._mesh(vanilla,i) for i in range(len(vanilla.meshes))],
                'vanilla_document':vanilla,'output':output,'dirty':set()}
        return header,unit,member,unit['documents'][member]

    def mesh(self, map_name, model, layer, index):
        header,unit,member,state = self._document(map_name,model,layer)
        if type(index) is not int or not 0 <= index < len(state['working']):
            raise FormatError('Unknown collision mesh')
        return header,unit,member,state,state['working'][index]

    @staticmethod
    def _row_id(row_id):
        parts = str(row_id).split(':')
        if len(parts) != 2 or parts[0] not in ('v','f') or not parts[1].isdigit():
            raise FormatError('Invalid collision record identity')
        return ('vertices' if parts[0] == 'v' else 'faces'),int(parts[1])

    @staticmethod
    def _vertex_name(mesh, index):
        position = ', '.join(f'{value:.6g}' for value in mesh['vertices'][index][:3])
        return f'Vertex {index} ({position})'

    def _listed(self, table, state, index, kind, row):
        mesh = state['working'][index]
        if not 0 <= row < len(mesh[kind]):
            raise FormatError('Unknown collision record')
        vanilla = state['vanilla'][index] if index < len(state['vanilla']) else None
        created = vanilla is None or row >= len(vanilla[kind])
        if kind == 'vertices':
            values = dict(zip(('posX','posY','posZ'),mesh['vertices'][row][:3]))
            values.update({f'metadata{i}':value for i,value in enumerate(mesh['flags'][row])})
            modified = created or mesh['vertices'][row] != vanilla['vertices'][row] or mesh['flags'][row] != vanilla['flags'][row]
            return {'table':table,'id':f'v:{row}','name':f'Vertex {row}','values':values,'display':{},
                    'created':created,'modified':modified}
        values = dict(zip(('vertexA','vertexB','vertexC','metadata'),mesh['faces'][row]))
        display = {key:self._vertex_name(mesh,values[key]) for key in ('vertexA','vertexB','vertexC')}
        return {'table':table,'id':f'f:{row}','name':f'Face {row}','values':values,'display':display,
                'created':created,'modified':created or mesh['faces'][row] != vanilla['faces'][row]}

    def view(self, map_name, model, layer, index, kind):
        if kind not in ('vertices','faces'):
            raise FormatError('Choose collision vertices or faces')
        _,_,_,state,mesh = self.mesh(map_name,model,layer,index)
        table = self.table(map_name,model,layer,index)
        return {'table':table,'rows':[self._listed(table,state,index,kind,i) for i in range(len(mesh[kind]))],
                'meshes':[{'id':i,'name':f'Mesh {i+1}','vertices':len(item['vertices']),'faces':len(item['faces'])}
                          for i,item in enumerate(state['working'])]}

    def snapshot(self, table):
        return deepcopy(self.mesh(*self.parse_table(table))[-1])

    def read_row(self, table, row_id):
        args = self.parse_table(table)
        _,_,_,state,mesh = self.mesh(*args)
        index = args[-1]
        kind,row = self._row_id(row_id)
        listed = self._listed(table,state,index,kind,row)
        vanilla = state['vanilla'][index] if index < len(state['vanilla']) else None
        old_values = {}
        if vanilla is not None and row < len(vanilla[kind]):
            if kind == 'vertices':
                old_values.update(zip(('posX','posY','posZ'),vanilla[kind][row][:3]))
                old_values.update({f'metadata{i}':v for i,v in enumerate(vanilla['flags'][row])})
            else:
                old_values.update(zip(('vertexA','vertexB','vertexC','metadata'),vanilla[kind][row]))
        fields,links = [],[]
        bits = {'indices8':8,'indices16':16,'indices32':32}[state['document'].meshes[index]['index_field']]
        for key,value in listed['values'].items():
            field = {'key':key,'value':value,'editable':True,'section':'Properties','type':'number',
                     'step':1,'dtype':'u32','description':''}
            if key.startswith('pos'):
                field.update(label=f'Position {key[-1]}',minimum=-3.4028234663852886e38,maximum=3.4028234663852886e38,
                             step='any',dtype='f32',description=POSITION_HELP)
            elif key.startswith('vertex'):
                label = self._vertex_name(mesh,value)
                choices = {str(value):label}
                if key in old_values and old_values[key] < len(mesh['vertices']):
                    choices[str(old_values[key])] = self._vertex_name(mesh,old_values[key])
                field.update(label=f'Vertex {key[-1]}',type='enum',enum=choices)
                links.append({'field':key,'kind':'collisionVertex','table':table,'id':f'v:{value}',
                              'name':label,'resolved':True})
            else:
                label = 'Face metadata' if kind == 'faces' else f'Vertex metadata {int(key[8:])+1}'
                field.update(label=label,minimum=0,maximum=(1 << bits)-1 if kind == 'faces' else 255,description=METADATA_HELP)
            if key in old_values:
                field['vanilla'] = old_values[key]
            fields.append(field)
        points = [mesh['vertices'][row]] if kind == 'vertices' else [mesh['vertices'][i] for i in mesh['faces'][row][:3]]
        transformed = state['document'].transformed_vertices(index,points)
        center = [sum(point[axis] for point in transformed)/len(transformed) for axis in range(3)]
        return {**listed,'fields':fields,'recordLinks':links,'previewPosition':center}

    def edit_row(self, table, row_id, field, value):
        kind,row = self._row_id(row_id)
        if kind == 'vertices' and field in ('posX','posY','posZ'):
            self.edit(table,kind,row,('posX','posY','posZ').index(field),value)
        elif kind == 'vertices' and str(field).startswith('metadata') and str(field)[8:].isdigit():
            self.edit(table,'flags',row,int(field[8:]),value)
        elif kind == 'faces' and field in ('vertexA','vertexB','vertexC','metadata'):
            self.edit(table,kind,row,('vertexA','vertexB','vertexC','metadata').index(field),value)
        else:
            raise FormatError('Unknown collision property')
        return self.read_row(table,row_id)

    def geometry(self, map_name, model):
        from . import map_collision
        result,notes = [],[]
        for layer in ('high','low'):
            try:
                self._header(map_name,model,layer)
                wanted = 'collisionHigh' if layer == 'high' else 'collisionLow'
                source = map_collision.source(self.game_root,self.project,map_name,model,wanted)
                if source is not None and source[1] is None:
                    header = self._header(map_name,model,layer)[0]
                    unit = self.units.get(header)
                    matches = [state for state in unit['documents'].values() if state['output'] is not None
                               and state['output'].name == source[0].name] if unit is not None else []
                    if matches:
                        state = matches[0]
                        previews = map_collision.preview_document(state['document'],state['working'])
                    else:
                        raw = _read(source[0],map_collision.hkx.MAX_FILE)
                        if raw is None:
                            raise FormatError('The collision source disappeared')
                        previews = map_collision.preview_meshes(raw)
                    result.extend(dict(mesh,layer=wanted) for mesh in previews)
                    continue
                _,unit,member = self._locate(map_name,model,layer)
                if member in unit['documents'] or member in unit['recipes']:
                    _,_,_,state = self._document(map_name,model,layer)
                    document,meshes = state['document'],state['working']
                else:
                    # A map preview must not create editable copies of every
                    # collision model. Untouched geometry is decoded only for
                    # this response; selected/portable records own the cache.
                    source = unit['archive'].member(member)
                    previews = map_collision.preview_meshes(source)
                    result.extend(dict(mesh,layer=wanted) for mesh in previews)
                    continue
                result.extend(dict(mesh,layer=wanted) for mesh in map_collision.preview_document(document,meshes))
            except (FormatError,OSError,ValueError,OverflowError,struct.error,KeyError,TypeError,IndexError,RecursionError) as error:
                notes.append(f'{layer} collision: {error}')
        return {'meshes':result,'notes':notes}

    @staticmethod
    def _dirty(unit):
        return any(state['dirty'] for state in unit['documents'].values())

    @property
    def dirty_count(self):
        return sum(len(state['dirty']) for unit in self.units.values() for state in unit['documents'].values())

    @staticmethod
    def _recount(state, index):
        state['dirty'] = {key for key in state['dirty'] if key[0] != index}
        before,after = state['baseline'][index],state['working'][index]
        for kind in before:
            for row in range(max(len(before[kind]),len(after[kind]))):
                if row >= min(len(before[kind]),len(after[kind])):
                    state['dirty'].add((index,kind,row))
                else:
                    for component,(a,b) in enumerate(zip(before[kind][row],after[kind][row])):
                        if a != b:
                            state['dirty'].add((index,kind,row,component))

    def edit(self, table, kind, row, component, value):
        self.writable()
        map_name,model,layer,index = self.parse_table(table)
        _,_,_,state,mesh = self.mesh(map_name,model,layer,index)
        if (kind not in ('vertices','faces','flags') or type(row) is not int or not 0 <= row < len(mesh[kind])
                or type(component) is not int or not 0 <= component < len(mesh[kind][row])):
            raise FormatError('Unknown collision field')
        if kind == 'vertices':
            if component == 3:
                raise FormatError('The fourth vertex component is preserved collision metadata')
            if type(value) not in (int,float) or not math.isfinite(value):
                raise FormatError('Collision coordinates must be finite numbers')
            value = collision_mopp._float32(value)
        else:
            maximum = 255
            if kind == 'faces':
                bits = {'indices8':8,'indices16':16,'indices32':32}[state['document'].meshes[index]['index_field']]
                maximum = min(len(mesh['vertices'])-1,(1 << bits)-1) if component < 3 else (1 << bits)-1
            if type(value) is not int or not 0 <= value <= maximum:
                raise FormatError('Collision index or metadata is outside its valid range')
        mesh[kind][row][component] = value
        key = (index,kind,row,component)
        baseline = state['baseline'][index][kind]
        if row < len(baseline) and baseline[row][component] == value:
            state['dirty'].discard(key)
        else:
            state['dirty'].add(key)
        return value

    def replace_mesh(self, table, value):
        self.writable()
        map_name,model,layer,index = self.parse_table(table)
        _,_,_,state,_ = self.mesh(map_name,model,layer,index)
        collision_edits._validate_mesh(value)
        value = deepcopy(value)
        for vertex in value['vertices']:
            vertex[:3] = [collision_mopp._float32(coordinate) for coordinate in vertex[:3]]
        before = state['baseline'][index]
        if len(value['flags'][0]) != len(before['flags'][0]):
            raise FormatError('Collision vertex metadata has an invalid stride')
        bits = {'indices8':8,'indices16':16,'indices32':32}[state['document'].meshes[index]['index_field']]
        if any(v >= 1 << bits for face in value['faces'] for v in face):
            raise FormatError('Collision indices exceed this mesh storage width')
        collision_merge._update(before,value)
        state['working'][index] = value
        self._recount(state,index)
        return deepcopy(value)

    def sources(self):
        for unit in self.units.values():
            yield from unit['sources']
            if unit['record_path'] is not None:
                yield unit['record_path'],unit['record_hash'],record_edits.LIMIT

    def pending_changes(self):
        changes = []
        for header,unit in self.units.items():
            for member,state in unit['documents'].items():
                counts = {}
                for key in state['dirty']:
                    counts[key[0]] = counts.get(key[0],0)+1
                for index,count in sorted(counts.items()):
                    changes.append({'label':f'{header.stem}/{member}, collision mesh {index+1}',
                                    'before':'Saved geometry','after':f'{count} unsaved changes'})
        return changes

    def validate_save(self):
        if not any(self._dirty(unit) for unit in self.units.values()):
            return
        records = record_edits.project_specs(self.project)
        for header,unit in self.units.items():
            if not self._dirty(unit):
                continue
            if records.get(header) != unit['spec']:
                raise FormatError('The collision records changed externally; unsaved edits were kept')
            for path,expected,limit in unit['sources']:
                if _sha(_read(path,limit)) != expected:
                    raise FormatError(f'{path.name} changed externally; unsaved collision edits were kept')

    def prepare_save(self, records):
        self.validate_save()
        outputs,expected,records_changed = {},{},False
        for header,unit in self.units.items():
            if not self._dirty(unit):
                continue
            members = {}
            recipe = deepcopy(unit['spec']) if unit['spec'] is not None else {'kind':'collision','members':[]}
            for name,state in unit['documents'].items():
                if not state['dirty']:
                    continue
                if unit['raw'] or state['output'] is not None:
                    updates = {index:collision_merge._update(collision_merge._mesh(state['document'],index),after)
                               for index,after in enumerate(state['working'])
                               if collision_merge._mesh(state['document'],index) != after}
                    payload = state['document'].export(updates)
                    if state['output'] is not None:
                        output = state['output']
                        outputs[output] = payload
                        expected[output] = next(stamp for path,stamp,_ in unit['sources'] if path == output)
                    else:
                        members[name] = payload
                else:
                    spec = collision_edits.create_state(state['vanilla_document'],state['document'],state['working'])
                    recipe['members'] = [row for row in recipe['members'] if row['name'] != name]
                    if spec is not None:
                        entry = unit['archive'].members[name]
                        recipe['members'].append({'name':name,'id':entry['id'],'path':entry['name'],'edits':spec})
            group = collision_archive.pair(header)
            if unit['raw'] and members:
                payloads = unit['archive'].replace(members)
                for relative,payload in zip(group,payloads):
                    path = checked(self.project/relative)
                    outputs[path] = payload
                    expected[path] = next(stamp for source,stamp,_ in unit['sources'] if source == path)
            elif any(state['dirty'] and state['output'] is None for state in unit['documents'].values()):
                if recipe['members']:
                    records[header] = recipe
                else:
                    records.pop(header,None)
                records_changed = True
        return outputs,expected,records_changed

    def discard(self):
        self.units.clear()
