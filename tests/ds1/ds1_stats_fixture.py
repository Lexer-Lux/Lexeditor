"""Generated scaling-curve fixtures, not retail game data."""
import struct
import zlib

from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument

#: Three vanilla-shaped graphs: default weapon scaling, Max HP, level-up cost.
CURVE_ROWS = {
    0: ([1.0, 10.0, 20.0, 40.0, 99.0], [0.0, 5.0, 40.0, 85.0, 100.0],
        [1.0, 1.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 0.0]),
    100: ([1.0, 10.0, 20.0, 30.0, 99.0], [0.0, 10.0, 45.0, 75.0, 100.0],
          [1.0, 1.0, 1.0, 1.0, 0.0], [0.0, 0.0, 0.0, 0.0]),
    200: ([0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, 0.0],
          [0.0, 0.0, 0.0, 0.0, 0.0], [0.1, 1.0, 0.02, 92.0]),
}


#: Three vanilla-shaped material sets: one single item, one pair, one empty.
MATERIAL_ROWS = {
    1: ([100, -1, -1, -1, -1], [1, -1, -1, -1, -1]),
    2: ([100, 101, -1, -1, -1], [2, 3, -1, -1, -1]),
    3: ([-1, -1, -1, -1, -1], [-1, -1, -1, -1, -1]),
}


def material_member():
    """An EquipMtrlSetParam table: five item slots, counts and hide flags."""
    ids = sorted(MATERIAL_ROWS)
    size = 32
    start = 48 + 12 * len(ids)
    table = bytearray(start + size * len(ids))
    struct.pack_into('<IHhhH', table, 0, len(table), start, 0, 1, len(ids))
    table[12:12 + len(b'EQUIP_MTRL_SET_PARAM_ST')] = b'EQUIP_MTRL_SET_PARAM_ST'
    table[45] = 2
    for index, row_id in enumerate(ids):
        offset = start + index * size
        struct.pack_into('<iII', table, 48 + index * 12, row_id, offset, 0)
        mats, nums = MATERIAL_ROWS[row_id]
        table[offset:offset + size] = struct.pack('<5i5b7x', *(mats + nums))
    return bytes(table)


def make_stats_archive():
    """The base fixture plus curve and material tables shaped like vanilla's."""
    source = make_archive()
    document = ItemDocument(source)
    entries = [
        (name, bytes(document.plain[member.offset:member.offset + member.size]))
        for name, member in document.members.items()
    ]
    ids = sorted(CURVE_ROWS)
    size = 80
    start = 48 + 12 * len(ids)
    table = bytearray(start + size * len(ids))
    struct.pack_into('<IHhhH', table, 0, len(table), start, 0, 1, len(ids))
    table[12:12 + len(b'CACL_CORRECT_GRAPH_ST')] = b'CACL_CORRECT_GRAPH_ST'
    table[45] = 2
    for index, row_id in enumerate(ids):
        offset = start + index * size
        struct.pack_into('<iII', table, 48 + index * 12, row_id, offset, 0)
        stages, growth, factors, soul = CURVE_ROWS[row_id]
        table[offset:offset + size] = struct.pack('<19f4x', *(stages + growth + factors + soul))
    entries.append(('CalcCorrectGraph.param', bytes(table)))
    entries.append(('EquipMtrlSetParam.param', material_member()))
    names = [name.encode('ascii') + b'\0' for name, _ in entries]
    directory_end = 32 + 24 * len(entries)
    names_end = directory_end + sum(map(len, names))
    plain = bytearray(names_end)
    plain[:16] = document.plain[:16]
    struct.pack_into('<II', plain, 16, len(entries), names_end)
    cursor = directory_end
    for index, ((_, payload), name) in enumerate(zip(entries, names)):
        struct.pack_into('<6I', plain, 32 + 24 * index,
                         0x40, len(payload), len(plain), index, cursor, len(payload))
        plain[cursor:cursor + len(name)] = name
        cursor += len(name)
        plain.extend(payload)
    compressed = zlib.compress(bytes(plain), 9)
    result = bytearray(source[:76])
    struct.pack_into('>II', result, 28, len(plain), len(compressed))
    return bytes(result) + compressed
