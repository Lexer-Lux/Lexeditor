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
    200: ([12.0, 30.0, 50.0, 80.0, 99.0], [0.0, 20.0, 50.0, 80.0, 100.0],
          [1.0, 1.0, 1.0, 1.0, 0.0], [0.5, 100.0, 2.0, 12.0]),
}


def make_stats_archive():
    """The base fixture plus a CalcCorrectGraph table shaped like vanilla's."""
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
