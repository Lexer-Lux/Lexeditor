"""Synthetic Unity mainData/resources.assets carrying FF9 .mes TextAssets.

The smallest serialized-file subset message_text reads: one ResourceManager
object in mainData pointing each description table at a TextAsset in
resources.assets. No game bytes; entry text is synthetic.
"""
import struct

TABLE_PATHS = {
    "items": "embeddedasset/text/us/item/itm_help.mes",
    "actions": "embeddedasset/text/us/ability/aa_help.mes",
    "abilities": "embeddedasset/text/us/ability/sa_help.mes",
    "commands": "embeddedasset/text/us/command/com_help.mes",
}


def _archive(records, externals):
    """records: [(info, type_id, payload)]; externals: [container name]."""
    head = bytearray(struct.pack(">IIIII", 20, 0, 0x0F, 0, 0))
    head += b"2021.3\x00\x00"
    head += struct.pack("<I", 0) + b"\x00" + struct.pack("<I", 0)
    head += struct.pack("<I", len(records))
    while len(head) % 4:
        head += b"\x00"
    table_at = len(head)
    head += b"\x00" * (28 * len(records) - (3 if records else 0))
    head += struct.pack("<I", 0)
    head += struct.pack("<I", len(externals))
    for name in externals:
        head += b"\x00" + b"\x00" * 20 + name.encode("utf-8") + b"\x00"
    # Version 15's last record carries its flags as one byte: the script
    # table starts three bytes before the contiguous record block ends.
    file_offset = len(head)
    struct.pack_into(">I", head, 12, file_offset)
    out = bytearray(head)
    table = bytearray()
    offset = 0
    for index, (info, type_id, payload) in enumerate(records):
        record = struct.pack("<qIIIII", info, offset, len(payload), type_id, 0, 0)
        table += record[:-3] if index == len(records) - 1 else record
        offset += len(payload)
    out[table_at:table_at + len(table)] = table
    for _, _, payload in records:
        out += payload
    struct.pack_into(">I", out, 4, len(out))
    return bytes(out)


def make_message_archives(entries_by_key):
    """(mainData, resources.assets) bytes for the given .mes entries.

    entries_by_key maps each message_text TABLES key to its entry list.
    Missing keys get one placeholder entry, so every table resolves.
    """
    keys = list(TABLE_PATHS)
    refs = bytearray(struct.pack("<I", len(keys)))
    assets = []
    for path_id, key in enumerate(keys, start=1):
        entries = entries_by_key.get(key, ["Placeholder"])
        refs += struct.pack("<I", len(TABLE_PATHS[key])) + TABLE_PATHS[key].encode("utf-8")
        while len(refs) % 4:
            refs += b"\x00"
        refs += struct.pack("<iq", 1, path_id)
        text = ("[ENDN]".join(entries) + "[ENDN]").encode("utf-8")
        assets.append((path_id, 49, struct.pack("<II", 0, len(text)) + text))
    main = _archive([(0, 147, bytes(refs))], ["resources.assets"])
    resources = _archive(assets, [])
    return main, resources
