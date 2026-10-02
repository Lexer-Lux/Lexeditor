"""Synthetic DS1-shaped archives; no proprietary game bytes."""
import struct
import zlib
from plugins.ds1.formats import TABLES, OPTIONAL_TABLES, schema
from plugins.ds3.formats import write_field


def make_archive():
    entries = []
    for table, (size, version) in TABLES.items():
        if table in OPTIONAL_TABLES:
            continue
        definition = schema(table)
        ids = [120000, 120100, 251000, 223000, 321001, 502, 999999] if table == 'NpcParam' else [100, 101, 102]
        rows_start = 48 + len(ids) * 12
        data = bytearray(rows_start + len(ids) * size)
        struct.pack_into('<IHhhH', data, 0, len(data), rows_start, 0, version, len(ids))
        encoded = definition['type'].encode('ascii')
        data[12:12+len(encoded)] = encoded
        data[45] = 2
        for index, row_id in enumerate(ids):
            struct.pack_into('<iII', data, 48 + index * 12, row_id, rows_start + index * size, 0)
            row = bytes(size)
            category = 'goodsType' if table == 'EquipParamGoods' else 'weaponCategory' if table == 'EquipParamWeapon' else None
            if category:
                field = next(f['spec'] for f in definition['fields'] if f['spec'].key == category)
                value = index if table == 'EquipParamGoods' else [0, 13, 14][index]
                row = write_field(row, field, value, '<')
            if table == 'NpcParam' and row_id in (251000, 321001):
                field = next(f['spec'] for f in definition['fields'] if f['spec'].key == 'npcType')
                row = write_field(row, field, 2, '<')
            values = {}
            if table == 'NpcParam':
                values = {'behaviorVariationId': 12000 if row_id in (120000,251000) else 12010 if row_id == 120100 else row_id}
            elif table == 'BehaviorParam':
                values = {'variationId': [12000,12000,12010][index], 'refType': [0,1,1][index], 'refId': [100,100,102][index]}
            elif table == 'Bullet':
                values = {'atkId_Bullet': [100,101,-1][index], 'HitBulletID': [101,-1,999999][index]}
            for key, value in values.items():
                field = next(f['spec'] for f in definition['fields'] if f['spec'].key == key)
                row = write_field(row, field, value, '<')
            data[rows_start + index * size:rows_start + (index + 1) * size] = row
        entries.append((table + '.param', bytes(data)))
    entries.append(('Untouched.bin', b'unknown payload\x00\xff\xa5'))
    names = [name.encode('ascii') + b'\0' for name, _ in entries]
    directory_end = 32 + len(entries) * 24
    names_end = directory_end + sum(map(len, names))
    plain = bytearray(names_end)
    plain[:4] = b'BND3'
    plain[4:12] = b'TEST0000'
    plain[12] = 0x74
    struct.pack_into('<II', plain, 16, len(entries), names_end)
    name_offset = directory_end
    for index, ((name, payload), encoded) in enumerate(zip(entries, names)):
        data_offset = len(plain)
        struct.pack_into('<6I', plain, 32 + index * 24, 0x40, len(payload), data_offset, index, name_offset, len(payload))
        plain[name_offset:name_offset+len(encoded)] = encoded
        name_offset += len(encoded)
        plain.extend(payload)
    compressed = zlib.compress(plain, 9)
    header = bytearray.fromhex('44435800000100000000001800000024000000240000002c4443530000000000000000004443500044464c540000002009000000000000000000000000000000000101004443410000000008')
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed
