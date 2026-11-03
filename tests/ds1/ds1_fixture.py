"""Synthetic DS1-shaped archives; no proprietary game bytes."""
import struct
import zlib
from plugins.ds1.formats import TABLES, OPTIONAL_TABLES, schema
from plugins.ds3.formats import write_field


def make_archive(table_ids=None, field_values=None):
    """Synthetic GameParam; table_ids overrides row ids per table and can
    include optional tables the default skips. field_values maps a table
    to {row_id: {field: value}} for links the default zero bytes lack."""
    table_ids = table_ids or {}
    field_values = field_values or {}
    entries = []
    for table, (size, version) in TABLES.items():
        if table in OPTIONAL_TABLES and table not in table_ids:
            continue
        definition = schema(table)
        ids = table_ids.get(table, [120000, 120100, 251000, 223000, 321001, 502, 999999] if table == 'NpcParam' else [100, 101, 102, 103] if table == 'EquipParamWeapon' else [100, 101, 102])
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
                value = index if table == 'EquipParamGoods' else [0, 13, 14, 12][index]
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
            for key, value in field_values.get(table, {}).get(row_id, {}).items():
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


def make_text_archive(names=None, descs=None, extra=None):
    """A synthetic msg/ENGLISH/item.msgbnd.dcx: every name and description
    table twice (the base and later copies Remastered ships), holding `names`
    and `descs` by table. `extra` maps an FMG file name to {id: text}, also
    carried twice."""
    from plugins.ds1 import texts
    names = names or {'EquipParamGoods': {100: 'Fixture Stone', 101: 'Fixture Key'},
                      'EquipParamWeapon': {100: 'Fixture Sword'}}
    descs = descs or {'EquipParamGoods': {100: ('A stone of safety.', 'A stone that keeps souls safe.\nIt has never broken.')},
                      'EquipParamWeapon': {100: ('A blade for testing.', 'A blade made for testing.\nIt has never tasted blood.')}}
    blank = b'\0\0\x01\0' + bytes(4) + b'\x01\0\0\0' + bytes(texts.HEADER - 12)
    entries = []
    folder = 'N:/FRPG/data/Msg/Data_ENGLISH/'.replace('/', chr(92))
    for base in (10, 110):
        for offset, (table, file_name) in enumerate(texts.NAME_TABLES.items()):
            payload = texts.build_fmg(blank, [], dict(names.get(table, {})))
            entries.append((base + offset, folder + file_name, payload))
        for offset, (table, (short, full)) in enumerate(texts.DESC_TABLES.items()):
            pair = descs.get(table, {})
            entries.append((base + 10 + offset * 2, folder + short,
                            texts.build_fmg(blank, [], {item: text[0] for item, text in pair.items()})))
            entries.append((base + 11 + offset * 2, folder + full,
                            texts.build_fmg(blank, [], {item: text[1] for item, text in pair.items()})))
        # Extra tables (Place_name_ and the like) sit past the name and
        # description members, which end at base + 19.
        for extra_offset, (file_name, contents) in enumerate((extra or {}).items()):
            entries.append((base + 40 + extra_offset, folder + file_name,
                            texts.build_fmg(blank, [], dict(contents))))
    encoded = [name.encode('shift_jis') + b'\0' for _, name, _ in entries]
    directory_end = 32 + len(entries) * 24
    names_end = directory_end + sum(map(len, encoded))
    plain = bytearray(names_end)
    plain[:4] = b'BND3'
    plain[4:12] = b'TEST0000'
    plain[12] = 0x74
    struct.pack_into('<II', plain, 16, len(entries), names_end)
    name_offset = directory_end
    for index, ((member_id, _name, payload), name) in enumerate(zip(entries, encoded)):
        while len(plain) % 16:
            plain.append(0)
        struct.pack_into('<6I', plain, 32 + index * 24, 0x40, len(payload), len(plain), member_id, name_offset, len(payload))
        plain[name_offset:name_offset + len(name)] = name
        name_offset += len(name)
        plain.extend(payload)
    compressed = zlib.compress(plain, 9)
    header = bytearray.fromhex('44435800000100000000001800000024000000240000002c4443530000000000000000004443500044464c540000002009000000000000000000000000000000000101004443410000000008')
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def pack_text_members(entries):
    """entries is [(member_id, name, payload)]: a synthetic DCX+BND3 archive."""
    encoded = [name.encode('shift_jis') + b'\0' for _, name, _ in entries]
    directory_end = 32 + len(entries) * 24
    names_end = directory_end + sum(map(len, encoded))
    plain = bytearray(names_end)
    plain[:4] = b'BND3'
    plain[4:12] = b'TEST0000'
    plain[12] = 0x74
    struct.pack_into('<II', plain, 16, len(entries), names_end)
    name_offset = directory_end
    for index, ((member_id, _name, payload), name) in enumerate(zip(entries, encoded)):
        while len(plain) % 16:
            plain.append(0)
        struct.pack_into('<6I', plain, 32 + index * 24, 0x40, len(payload), len(plain), member_id, name_offset, len(payload))
        plain[name_offset:name_offset + len(name)] = name
        name_offset += len(name)
        plain.extend(payload)
    compressed = zlib.compress(plain, 9)
    header = bytearray.fromhex('44435800000100000000001800000024000000240000002c4443530000000000000000004443500044464c540000002009000000000000000000000000000000000101004443410000000008')
    struct.pack_into('>II', header, 28, len(plain), len(compressed))
    return bytes(header) + compressed


def make_menu_archive(labels=None, extra=None, omit_labels=False):
    """A synthetic msg/ENGLISH/menu.msgbnd.dcx: Menu_general_text_ twice
    (member IDs 76 and 124, as Remastered ships them), holding `labels` by
    entry ID. `extra` maps an FMG file name to {id: text}, also carried
    twice."""
    from plugins.ds1 import texts
    labels = labels if labels is not None else {102204: 'MagDEF', 102205: 'FireDEF', 102206: 'LitngDEF'}
    blank = b'\0\0\x01\0' + bytes(4) + b'\x01\0\0\0' + bytes(texts.HEADER - 12)
    entries = []
    folder = 'N:/FRPG/data/Msg/Data_ENGLISH/'.replace('/', chr(92))
    for member_id in (76, 124):
        if not omit_labels:
            entries.append((member_id, folder + texts.MENU_LABEL_FILE,
                            texts.build_fmg(blank, [], dict(labels))))
        for extra_offset, (file_name, contents) in enumerate((extra or {}).items()):
            entries.append((member_id + 64 + extra_offset, folder + file_name,
                            texts.build_fmg(blank, [], dict(contents))))
    return pack_text_members(entries)
