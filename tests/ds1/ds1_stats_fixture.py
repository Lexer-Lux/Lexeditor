"""Generated scaling-curve, material and starting-class fixtures, not retail game data."""
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


#: Warrior-shaped class rows with their twin, plus two gift rows.
CHARA_ROWS = {
    2000: {'stats': (11, 8, 12, 13, 13, 9, 9, 10, 0, 11), 'soulLv': 4,
           'wepR': 212000, 'draw': 4},
    3000: {'stats': (11, 8, 12, 13, 13, 9, 9, 10, 0, 11), 'soulLv': 4, 'sex': 1, 'vow': 3,
           'wepR': 100, 'wepL': 101, 'helm': 100, 'spell1': 100, 'acc1': 100,
           'items': {9: (100, 1), 10: (101, 1)}, 'gestures': (0, 1, 2, 3, 4, 5, 8)},
    2405: {'items': {1: (100, 1)}, 'gift': True},
    2407: {'gift': True, 'giftAcc': 100},
}


def charainit_member():
    """A CharaInitParam table: a class pair and two gifts, vanilla-shaped."""
    ids = sorted(CHARA_ROWS)
    size = 240
    start = 48 + 12 * len(ids)
    table = bytearray(start + size * len(ids))
    struct.pack_into('<IHhhH', table, 0, len(table), start, 0, 2, len(ids))
    table[12:12 + len(b'CHARACTER_INIT_PARAM')] = b'CHARACTER_INIT_PARAM'
    table[45] = 2
    for index, row_id in enumerate(ids):
        offset = start + index * size
        struct.pack_into('<iII', table, 48 + index * 12, row_id, offset, 0)
        spec = CHARA_ROWS[row_id]
        empty = 0 if spec.get('gift') else -1
        equips = [empty] * 12
        if 'wepR' in spec:
            equips[0] = spec['wepR']
        if 'wepL' in spec:
            equips[2] = spec['wepL']
        if 'helm' in spec:
            equips[4] = spec['helm']
        acc = [empty] * 5
        if 'acc1' in spec:
            acc[0] = spec['acc1']
        if 'giftAcc' in spec:
            acc[0] = spec['giftAcc']
        spells = [empty] * 7
        if 'spell1' in spec:
            spells[0] = spec['spell1']
        items, nums = [empty] * 10, [0] * 10
        for slot, (item, count) in spec.get('items', {}).items():
            items[slot - 1], nums[slot - 1] = item, count
        stats = spec.get('stats', (0,) * 10)
        gestures = spec.get('gestures', (0,) * 7)
        table[offset:offset + size] = struct.pack(
            '<3f13i5i3i7i10i2i7H3hh10B10B5b7b4B10x',
            0.0, 0.0, 0.0, 0, *equips, *acc, *([-1] * 3), *spells, *items,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, spec.get('soulLv', 0), *stats, *nums,
            0, 0, 0, 0, 0, *gestures, 0, spec.get('draw', 0), spec.get('sex', 0),
            spec.get('vow', 0))
    return bytes(table)


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
    entries.append(('CharaInitParam.param', charainit_member()))
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
