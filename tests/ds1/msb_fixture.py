"""Synthetic DS1-shaped map files; no proprietary game bytes."""
import struct


def build_msb(parts=(("enemy", 2, 0, 0, 120000), ("player", 4, 0, 1, None), ("piece", 0, 0, 1, None),
                     ("chest", 1, 0, 1, None))):
    """A minimal map: 2 models, no events/points, and the given parts.
    Each part is (kind, type, id, model, npc)."""
    model_names = ["c1200", "m10piece"]
    blobs = []
    for index, name in enumerate(model_names):
        entry = struct.pack("<8i", 0x20, index if index != 1 else 0, index, 0, 1, 0, 0, 0)
        blobs.append((entry, name, "sib%d" % index))
    for kind, ptype, pid, model, npc in parts:
        base = struct.pack("<5i", 0x64, ptype, pid, model, 0)
        base += struct.pack("<3f", 1.0, 2.0, 3.0) + struct.pack("<3f", 0.0, 90.0, 0.0)
        base += struct.pack("<3f", 1.0, 1.0, 1.0) + bytes(32)
        base += struct.pack("<iii", 0, 0, 0)
        entity = bytes(0x18)
        # Blobs match the real sizes per part type, so fixtures duplicate
        # like real maps; collision and navigation parts keep a stub.
        if npc is not None:
            typedata = struct.pack("<5i", 0, 0, 1000, npc, 111) + bytes(0x40 - 20)
        elif ptype in (1, 9):
            typedata = bytes(0x18)
        elif ptype == 4:
            typedata = bytes(0x10)
        else:
            typedata = bytes(8)
        blobs.append((base, "%s%d" % (kind, pid), "s%s%d" % (kind, pid), entity, typedata))
    dirs = [(0, "MODEL_PARAM_ST", len(model_names)), (0, "EVENT_PARAM_ST", 0),
            (0, "POINT_PARAM_ST", 0), (0, "PARTS_PARAM_ST", len(parts))]
    dir_size = sum(16 + 4 * n for _, _, n in dirs)
    out = bytearray(dir_size)
    cursor = dir_size
    spans = []
    for entry, *rest in blobs:
        start = cursor
        chunks = [entry]
        for text in rest[:2] if isinstance(rest[0], str) else []:
            chunks.append(text.encode("shift_jis") + b"\0")
        chunks.extend(rest[2:] if isinstance(rest[0], str) else rest)
        blob = b"".join(chunks)
        out.extend(blob)
        spans.append((start, blob))
        cursor += len(blob)
    # Backpatch: param names live at the end, entries point at their strings.
    name_base = len(out)
    for _, name, _ in dirs:
        out.extend(name.encode("ascii") + b"\0")
    site = 0
    entry_sets = [spans[:len(model_names)], [], [], spans[len(model_names):]]
    for index, (base, name, count) in enumerate(dirs):
        entries = entry_sets[index]
        struct.pack_into("<iIi", out, site, 0, name_base, len(entries) + 1)
        for slot, (start, _blob) in enumerate(entries):
            struct.pack_into("<i", out, site + 12 + 4 * slot, start)
        site += 16 + 4 * len(entries)
        struct.pack_into("<i", out, site - 4, 0 if index == 3 else site)
        name_base += len(name) + 1
    for (start, blob), (entry, *rest) in zip(spans, blobs):
        if len(blob) >= 0x64 + 11:
            name_len = len(rest[0]) + 1
            struct.pack_into("<i", out, start, 0x64)
            struct.pack_into("<i", out, start + 0x10, 0x64 + name_len)
            struct.pack_into("<i", out, start + 0x58, 0x64 + name_len + len(rest[1]) + 1)
            struct.pack_into("<i", out, start + 0x5c, 0x64 + name_len + len(rest[1]) + 1 + 0x18)
        else:
            struct.pack_into("<i", out, start, 0x20)
            struct.pack_into("<i", out, start + 12, 0x20 + len(rest[0]) + 1)
    return bytes(out)
