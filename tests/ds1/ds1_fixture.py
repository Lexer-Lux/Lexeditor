"""Synthetic DS1-shaped archives; no proprietary game bytes."""
import struct
import zlib
from plugins.ds1.formats import TABLES, schema
from plugins.ds3.formats import write_field


def make_archive():
    entries = []
    for table, (size, version) in TABLES.items():
        definition = schema(table)
        data = bytearray(84 + 3 * size)
        struct.pack_into('<IHhhH', data, 0, len(data), 84, 0, version, 3)
        encoded = definition['type'].encode('ascii')
        data[12:12+len(encoded)] = encoded
        data[45] = 2
        for index in range(3):
            struct.pack_into('<iII', data, 48 + index * 12, 100 + index, 84 + index * size, 0)
            row = bytes(size)
            category = 'goodsType' if table == 'EquipParamGoods' else 'weaponCategory' if table == 'EquipParamWeapon' else None
            if category:
                field = next(f['spec'] for f in definition['fields'] if f['spec'].key == category)
                value = index if table == 'EquipParamGoods' else [0, 13, 14][index]
                row = write_field(row, field, value, '<')
            data[84 + index * size:84 + (index + 1) * size] = row
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
