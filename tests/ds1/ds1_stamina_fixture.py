"""Generated stamina-effect fixtures, not retail game data."""
import struct
import zlib

from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, inflate, members
from plugins.ds3.formats import write_field


def wrap(plain, header):
    compressed = zlib.compress(bytes(plain), 9)
    result = bytearray(header[:76])
    struct.pack_into(">II", result, 28, len(plain), len(compressed))
    return bytes(result) + compressed


def make_stamina_archive(*, effect_size=368, version=1):
    """Append an independently specified effect table to the existing fixture."""
    source = make_archive()
    document = ItemDocument(source)
    references = [
        ("EquipParamWeapon", 100, "residentSpEffectId", 6890),
        ("EquipParamWeapon", 101, "residentSpEffectId", 99001),
        ("EquipParamProtector", 100, "residentSpEffectId", 6200),
        ("EquipParamAccessory", 100, "refId", 6890),
        ("EquipParamAccessory", 100, "refCategory", 2),
        # This coincidentally matching projectile ID is NOT an effect reference.
        ("EquipParamAccessory", 101, "refId", 6890),
        ("EquipParamAccessory", 101, "refCategory", 1),
    ]
    for table, row_id, key, value in references:
        _, start, row = document._row(table, row_id)
        field = next(f["spec"] for f in document.schemas[table]["fields"]
                     if f["spec"].key == key)
        document.plain[start:start + len(row)] = write_field(row, field, value, "<")
    entries = [
        (name, bytes(document.plain[member.offset:member.offset + member.size]))
        for name, member in document.members.items()
    ]
    ids = [40, 41, 42, 43, 44, 2013, 3040, 6200, 6201, 6890, 6920, 99001]
    start = 48 + 12 * len(ids)
    effect = bytearray(start + effect_size * len(ids))
    struct.pack_into("<IHhhH", effect, 0, len(effect), start, 0, version, len(ids))
    effect[12:12 + len(b"SP_EFFECT_PARAM_ST")] = b"SP_EFFECT_PARAM_ST"
    effect[45] = 2
    for index, row_id in enumerate(ids):
        offset = start + index * effect_size
        struct.pack_into("<iII", effect, 48 + index * 12, row_id, offset, 0)
        # Nonzero opaque bytes detect accidental row reconstruction.
        row = bytearray([0xA5] * effect_size)
        value = 10 if row_id == 6890 else -2 if row_id in (6200, 6201) else 0
        struct.pack_into("<i", row, 0xB8, value)
        effect[offset:offset + effect_size] = row
    entries.append(("SpEffectParam.param", bytes(effect)))
    names = [name.encode("ascii") + b"\0" for name, _ in entries]
    directory_end = 32 + 24 * len(entries)
    names_end = directory_end + sum(map(len, names))
    plain = bytearray(names_end)
    plain[:16] = document.plain[:16]
    struct.pack_into("<II", plain, 16, len(entries), names_end)
    cursor = directory_end
    for index, ((_, payload), name) in enumerate(zip(entries, names)):
        struct.pack_into("<6I", plain, 32 + 24 * index,
                         0x40, len(payload), len(plain), index, cursor, len(payload))
        plain[cursor:cursor + len(name)] = name
        cursor += len(name)
        plain.extend(payload)
    return wrap(plain, source)


def mutate_effect_header(source, offset, fmt, value):
    plain = bytearray(inflate(source))
    start = members(plain)["SpEffectParam.param"].offset
    struct.pack_into(fmt, plain, start + offset, value)
    return wrap(plain, source)
