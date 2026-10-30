"""Unsaved map collision records; geometry is compiled only while saving."""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re

from . import collision_archive, collision_edits, collision_merge, collision_mopp, deployment, record_edits
from .collision_write import CollisionDocument
from .formats import FormatError
from .tweak_mods import checked

MAX_OPEN_BYTES = 256 * 1024 * 1024


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
        if size > MAX_OPEN_BYTES:
            raise FormatError('This collision archive exceeds the editor memory limit')
        while sum(unit['size'] for unit in self.units.values())+size > MAX_OPEN_BYTES:
            unused = next((key for key, unit in self.units.items() if not self._dirty(unit)),None)
            if unused is None:
                raise FormatError('Save or discard collision edits before opening more collision archives')
            del self.units[unused]
        record_hash = _sha(record_bytes)
        unit = {'archive':archive,'originals':originals,'sources':sources,'spec':deepcopy(spec),
                'raw':raw,'recipes':recipes,'documents':{},'size':size,'record_path':record_path,'record_hash':record_hash}
        self.units[header] = unit
        return unit

    def _document(self, map_name, model, layer):
        header, prefix = self._header(map_name,model,layer)
        unit = self._unit(header)
        matches = [name for name in unit['archive'].members if name == prefix.lower()
                   or name.startswith(prefix.lower()+'a')]
        if len(matches) != 1:
            raise FormatError(f'No unique {layer} collision member for {model}')
        member = matches[0]
        if member not in unit['documents']:
            source = unit['archive'].member(member)
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
            unit['documents'][member] = {'document':document,'baseline':meshes,'working':deepcopy(meshes),
                'vanilla':[collision_merge._mesh(vanilla,i) for i in range(len(vanilla.meshes))],
                'vanilla_document':vanilla,'dirty':set()}
        return header,unit,member,unit['documents'][member]

    def mesh(self, map_name, model, layer, index):
        header,unit,member,state = self._document(map_name,model,layer)
        if type(index) is not int or not 0 <= index < len(state['working']):
            raise FormatError('Unknown collision mesh')
        return header,unit,member,state,state['working'][index]

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
                if unit['raw']:
                    updates = {index:collision_merge._update(collision_merge._mesh(state['document'],index),after)
                               for index,after in enumerate(state['working'])
                               if collision_merge._mesh(state['document'],index) != after}
                    members[name] = state['document'].export(updates)
                else:
                    spec = collision_edits.create_state(state['vanilla_document'],state['document'],state['working'])
                    recipe['members'] = [row for row in recipe['members'] if row['name'] != name]
                    if spec is not None:
                        entry = unit['archive'].members[name]
                        recipe['members'].append({'name':name,'id':entry['id'],'path':entry['name'],'edits':spec})
            group = collision_archive.pair(header)
            if unit['raw']:
                payloads = unit['archive'].replace(members)
                for relative,payload in zip(group,payloads):
                    path = checked(self.project/relative)
                    outputs[path] = payload
                    expected[path] = next(stamp for source,stamp,_ in unit['sources'] if source == path)
            else:
                if recipe['members']:
                    records[header] = recipe
                else:
                    records.pop(header,None)
                records_changed = True
        return outputs,expected,records_changed

    def discard(self):
        self.units.clear()
