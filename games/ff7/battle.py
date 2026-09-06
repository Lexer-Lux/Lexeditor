"""English FF7 scene data, preserving block membership and all unedited bytes.

Layout reference: ff7-mods/ff7-flat-wiki, FF7/Battle/Battle_Scenes.html.
The 4 * 96-byte formation array is contiguous (third record starts at 0x1D8).
Unedited AI, IDs and scene-to-block mappings are preserved.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import struct
import zlib

from .format_codec import bounds, decode_text, encode_text, read_int
from . import ai


def number(key, label, offset, size=1, signed=False, maximum=None, group="Data"):
    return {"key": key, "label": label, "offset": offset, "size": size,
            "signed": signed, "dataType": "int", "step": 1,
            "minimum": -(1 << (size * 8 - 1)) if signed else 0,
            "maximum": maximum if maximum is not None else (1 << (size * 8 - int(signed))) - 1,
            "group": group}


def text(key, label, offset=0, size=32, group="Text"):
    return {"key": key, "label": label, "offset": offset, "size": size,
            "dataType": "text", "group": group}


def read_values(raw, fields):
    return {f["key"]: decode_text(raw[f["offset"]:f["offset"] + f["size"]])
            if f["dataType"] == "text" else read_int(raw, f["offset"], f["size"], f["signed"])
            for f in fields}


def write_values(raw, fields, values):
    if not isinstance(values, dict) or set(values) != {f["key"] for f in fields}:
        raise ValueError("Record has an invalid field set")
    result = bytearray(raw)
    for f in fields:
        value, offset, size = values[f["key"]], f["offset"], f["size"]
        bounds(result, offset, size)
        if f["dataType"] == "text":
            # Keep original padding/control bytes on an unchanged string.
            if value == decode_text(raw[offset:offset + size]):
                continue
            encoded = encode_text(value)
            if len(encoded) > size:
                raise ValueError(f"{f['label']} exceeds {size - 1} encoded bytes")
            result[offset:offset + size] = encoded.ljust(size, b'\xff')
        else:
            if type(value) is not int or not f["minimum"] <= value <= f["maximum"]:
                raise ValueError(f"{f['label']} must be an integer from {f['minimum']} to {f['maximum']}")
            result[offset:offset + size] = value.to_bytes(size, 'little', signed=f["signed"])
    return result


def validate_rows(rows, expected):
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Save must contain exactly the original records")
    allowed, seen = {r['id'] for r in expected}, set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] not in allowed or row['id'] in seen:
            raise ValueError("Invalid, missing or duplicate record ID")
        seen.add(row['id'])


ENEMY_FIELDS = [text("name", "Enemy name")]
ENEMY_FIELDS += [number(key, label, 0x20 + i, group="Stats") for i, (key, label) in enumerate((
    ('level','Level'), ('speed','Speed'), ('luck','Luck'), ('evade','Evade'),
    ('strength','Strength'), ('defense','Defense'), ('magic','Magic'), ('magicDefense','Magic defense')))]
ENEMY_FIELDS += [number(key, label, offset, size, group="Stats / rewards") for key, label, offset, size in (
    ('mp','MP',0x9C,2), ('ap','AP reward',0x9E,2), ('morph','Morph item ID (65535: none)',0xA0,2),
    ('backMultiplier','Back damage multiplier (eighths)',0xA2,1), ('hp','HP',0xA4,4),
    ('experience','Experience reward',0xA8,4), ('gil','Gil reward',0xAC,4), ('statusImmunity','Status immunity mask',0xB0,4))]
for key, label, offset, size, count, group in (
    ('element','Element / status ID',0x28,1,8,'Resistances'), ('rate','Element rate code',0x30,1,8,'Resistances'),
    ('animation','Action animation',0x38,1,16,'Actions'), ('attack','Attack ID',0x48,2,16,'Actions'),
    ('camera','Attack camera',0x68,2,16,'Actions'), ('dropRate','Drop/steal rate byte',0x88,1,4,'Loot'),
    ('item','Drop/steal item ID',0x8C,2,4,'Loot'), ('manipulate','Manipulate / berserk attack',0x94,2,3,'Actions')):
    ENEMY_FIELDS += [number(f'{key}{i}', f'{label} {i + 1}', offset + i * size, size, group=group) for i in range(count)]

FORMATION_FIELDS = [number(k,l,o,s,group='Battle setup') for k,l,o,s in (
    ('location','Battle location',0,2), ('nextBattle','Next battle (65535: none)',2,2),
    ('escapeCounter','Escape counter',4,2), ('flags','Battle flags',16,2),
    ('layout','Battle layout',18,1), ('cameraIndex','Pre-battle camera',19,1))]
FORMATION_FIELDS += [number(f'arena{i}', f'Arena candidate {i + 1}', 8 + i * 2, 2, group='Battle setup') for i in range(4)]
# Assemble setup + cameras + placements as one virtual 164-byte record.
for camera in range(3):
    FORMATION_FIELDS += [number(f'camera{camera}_{axis}', f'Camera {camera + 1} {axis}', 20 + camera * 12 + j * 2, 2, True, group='Cameras')
                         for j,axis in enumerate(('x','y','z','directionX','directionY','directionZ'))]
for slot in range(6):
    FORMATION_FIELDS += [number(f'slot{slot}_{k}', f'{label}', 68 + slot * 16 + o, s, signed,
                               group=f'Enemy slot {slot + 1}')
        for k,label,o,s,signed in (('enemy','Enemy ID (65535: empty)',0,2,False), ('x','X',2,2,True),
            ('y','Y',4,2,True), ('z','Z',6,2,True), ('row','Row',8,2,False),
            ('cover','Cover flags',10,2,False), ('flags','Initial condition flags',12,4,False))]

ATTACK_FIELDS = [text('name','Attack name',28)]
ATTACK_FIELDS += [number(k,l,o,s) for k,l,o,s in (
    ('accuracy','Accuracy',0,1), ('impact','Impact effect',1,1), ('targetAnimation','Target hurt action',2,1),
    ('cost','MP cost',4,2), ('impactSound','Impact sound',6,2),
    ('singleCamera','Single-target camera',8,2), ('multiCamera','Multi-target camera',10,2),
    ('target','Target flags',12,1), ('effect','Attack effect',13,1), ('formula','Damage formula',14,1),
    ('power','Power',15,1), ('condition','Condition',16,1), ('statusChance','Status chance / mode',17,1),
    ('additionalEffect','Additional effect',18,1), ('modifier','Effect modifier',19,1),
    ('statuses','Statuses',20,4), ('elements','Elements',24,2), ('specialFlags','Special flags',26,2))]
SCENE_CATEGORIES = {
    'enemies': {'label':'Enemies', 'fields':ENEMY_FIELDS},
    'enemyAI': {'label':'Enemy AI', 'fields':ai.metadata()},
    'formationAI': {'label':'Formation AI', 'fields':ai.metadata()},
    'encounters': {'label':'Encounters', 'fields':FORMATION_FIELDS},
    'enemyAttacks': {'label':'Enemy attacks', 'fields':ATTACK_FIELDS},
}


class SceneArchive:
    def __init__(self, data: bytes):
        if not data or len(data) % 0x2000 or len(data) > 0x2000 * 64:
            raise ValueError('scene.bin must contain complete 8192-byte blocks')
        self.original, self.scenes, self.blocks, self.compressed = data, [], [], []
        for start in range(0, len(data), 0x2000):
            block = data[start:start + 0x2000]
            pointers = list(struct.unpack_from('<16I', block))
            count = next((i for i,v in enumerate(pointers) if v == 0xFFFFFFFF), 16)
            if any(v != 0xFFFFFFFF for v in pointers[count:]):
                raise ValueError('scene.bin has a pointer after its end marker')
            offsets = [v * 4 for v in pointers[:count]]
            if offsets != sorted(set(offsets)) or any(not 64 <= o < 8192 for o in offsets):
                raise ValueError('scene.bin has invalid or overlapping pointers')
            ids = []
            for i, offset in enumerate(offsets):
                chunk = block[offset:offsets[i + 1] if i + 1 < count else 8192]
                decoder = zlib.decompressobj(31)
                raw = decoder.decompress(chunk, 0x1E81)
                if not decoder.eof or len(raw) != 0x1E80:
                    raise ValueError('Expected a complete 7808-byte English scene')
                if any(v != 255 for v in decoder.unused_data):
                    raise ValueError('Unexpected bytes after scene gzip member')
                ids.append(len(self.scenes)); self.scenes.append(bytearray(raw))
                self.compressed.append(chunk[:len(chunk) - len(decoder.unused_data)])
            self.blocks.append(ids)
        if len(self.scenes) != 256:
            raise ValueError('Expected exactly 256 scenes; other scene layouts are not writable')
        self.original_scenes = [bytes(s) for s in self.scenes]

    def _record(self, category, scene, slot):
        raw = self.scenes[scene]
        if category == 'enemies':
            return raw[0x298 + slot * 184:0x298 + (slot + 1) * 184]
        if category == 'encounters':
            return raw[8 + slot * 20:28 + slot * 20] + raw[0x58 + slot * 48:0x88 + slot * 48] + raw[0x118 + slot * 96:0x178 + slot * 96]
        return raw[0x4C0 + slot * 28:0x4DC + slot * 28] + raw[0x880 + slot * 32:0x8A0 + slot * 32]

    def records(self, category):
        if category in ('enemyAI', 'formationAI'):
            start, size, count = (0xE80,4096,3) if category == 'enemyAI' else (0xC80,512,4)
            return [row for scene, raw in enumerate(self.scenes)
                    for row in ai.Pool(raw[start:start+size],count).records(f'Scene {scene} / owner',scene*count)]
        count = {'enemies':3, 'encounters':4, 'enemyAttacks':32}[category]
        rows = []
        for scene, raw in enumerate(self.scenes):
            for slot in range(count):
                if category == 'enemies' and read_int(raw, slot * 2) == 65535:
                    continue
                if category == 'enemyAttacks' and read_int(raw, 0x840 + slot * 2) == 65535:
                    continue
                values = read_values(self._record(category, scene, slot), SCENE_CATEGORIES[category]['fields'])
                suffix = f'Enemy ID {read_int(raw, slot * 2)}' if category == 'enemies' else (
                    f'Attack ID {read_int(raw, 0x840 + slot * 2)}' if category == 'enemyAttacks' else 'Formation composition; not field/world placement')
                rows.append({'id':scene * count + slot, 'name':values.get('name', f'Battle {scene * 4 + slot}'),
                             'description':f'Scene {scene}, slot {slot}: {suffix}. AI is edited separately.', 'values':values})
        return rows

    def apply(self, category, rows):
        if category in ('enemyAI', 'formationAI'):
            validate_rows(rows, self.records(category))
            start, size, count = (0xE80,4096,3) if category == 'enemyAI' else (0xC80,512,4)
            grouped = {}
            for row in rows:
                scene, owner = divmod(row['id'], count)
                grouped.setdefault(scene, {})[owner] = row.get('values')
            pending = {}
            for scene, values in grouped.items():
                pending[scene] = ai.Pool(self.scenes[scene][start:start+size],count).apply(values)
            for scene, raw in pending.items(): self.scenes[scene][start:start+size] = raw
            return
        validate_rows(rows, self.records(category))
        replacement = deepcopy(self.scenes)
        count = {'enemies':3, 'encounters':4, 'enemyAttacks':32}[category]
        for row in rows:
            scene, slot = divmod(row['id'], count)
            data = write_values(self._record(category, scene, slot), SCENE_CATEGORIES[category]['fields'], row.get('values'))
            raw = replacement[scene]
            if category == 'enemies':
                raw[0x298 + slot * 184:0x298 + (slot + 1) * 184] = data
            elif category == 'enemyAttacks':
                raw[0x4C0 + slot * 28:0x4DC + slot * 28] = data[:28]
                raw[0x880 + slot * 32:0x8A0 + slot * 32] = data[28:]
            else:
                allowed = set(struct.unpack_from('<3H', raw)) | {65535}
                for index in range(6):
                    value = row['values'][f'slot{index}_enemy']
                    if value not in allowed:
                        raise ValueError(f'Battle {row["id"]}: enemy {value} is not defined in this scene')
                raw[8 + slot * 20:28 + slot * 20] = data[:20]
                raw[0x58 + slot * 48:0x88 + slot * 48] = data[20:68]
                raw[0x118 + slot * 96:0x178 + slot * 96] = data[68:]
        self.scenes = replacement

    def to_bytes(self):
        output = bytearray(self.original)
        for block_index, ids in enumerate(self.blocks):
            if all(self.scenes[i] == self.original_scenes[i] for i in ids):
                continue
            block, offset = bytearray(b'\xff' * 8192), 64
            for slot, i in enumerate(ids):
                chunk = self.compressed[i] if self.scenes[i] == self.original_scenes[i] else gzip.compress(bytes(self.scenes[i]), mtime=0)
                if offset + len(chunk) > 8192:
                    raise ValueError(f'Scene block {block_index} exceeds its original capacity. No files written; cross-block relocation requires a coordinated KERNEL lookup update.')
                struct.pack_into('<I', block, slot * 4, offset // 4)
                block[offset:offset + len(chunk)] = chunk
                offset += (len(chunk) + 3) & ~3
            output[block_index * 8192:(block_index + 1) * 8192] = block
        return bytes(output)
