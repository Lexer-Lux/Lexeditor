"""Read cinematic texture/CLUT sources; script upload order remains significant.

Source: FF8UltimateEditor/FF8GameData/magcine/cinevram.py and the GF cinematic
format reference. Descriptor addresses were verified against the supported EXE.
No executable, palette or texture bytes are bundled with the editor.
"""
import struct

from . import executable_text

DESCRIPTORS = {5: 0x187726C, 200: 0x1874894, 201: 0x1873A60,
               202: 0x1872EF8, 203: 0x1872384, 204: 0x1871878, 205: 0x1870640}


def descriptor(exe: bytes, family: int) -> dict:
    executable_text._validate_executable(exe)
    if family not in DESCRIPTORS:
        raise ValueError('Unsupported cinematic family')
    return read_descriptor(exe, DESCRIPTORS[family] - 0x400000)


def read_descriptor(data: bytes, start: int) -> dict:
    if start < 0 or start + 32 > len(data):
        raise ValueError('Cinematic descriptor header is truncated')
    offsets = struct.unpack_from('<8I', data, start)
    tex, clut, tex_slots, clut_slots, objects = offsets[:5]
    if not 32 == tex <= clut <= tex_slots <= clut_slots <= objects <= len(data) - start:
        raise ValueError('Cinematic descriptor tables are out of order')
    result = {}
    for name, begin, end, slots, slot_end in (
            ('textures', tex, clut, tex_slots, clut_slots),
            ('cluts', clut, tex_slots, clut_slots, objects)):
        if (end - begin) % 8:
            raise ValueError('Cinematic rectangle table is misaligned')
        count = (end - begin) // 8
        if count > 4096 or slots + count > slot_end:
            raise ValueError('Cinematic file-slot table is truncated')
        rows = []
        for index in range(count):
            rect = struct.unpack_from('<4h', data, start + begin + index * 8)
            x, y, width, height = rect
            slot_byte = data[start + slots + index]
            slot = slot_byte & 127 if name == 'textures' else slot_byte
            if slot_byte == 255 or (name == 'textures' and slot == 127):
                slot = None  # No packed-file source; scripts can upload raw pages here.
            elif slot >= 64:
                raise ValueError('Cinematic file slot is outside the supported range')
            if not (slot is None and width == height == 0 and 0 <= x <= 1024 and 0 <= y <= 512):
                if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1024 or y + height > 512:
                    raise ValueError('Cinematic texture rectangle is outside VRAM')
            rows.append({'id': index, 'rect': rect, 'slot': slot,
                         'depth': (8 if slot_byte & 128 else 4) if name == 'textures' else None})
        result[name] = rows
    return result


def resource_bytes(data: bytes, row: dict, *, texture: bool) -> bytes:
    """Return one complete upload; never pad truncated data with invented pixels."""
    if not 48 <= len(data) <= 16 * 1024 * 1024:
        raise ValueError('Cinematic resource file size is outside the supported bounds')
    table, = struct.unpack_from('<I', data, 20 if texture else 8)
    index = row['id']
    if not isinstance(index, int) or not 0 <= index < 4096 or table < 48 or table + 4 * (index + 1) > len(data):
        raise ValueError('Cinematic resource table is outside the file')
    entry, = struct.unpack_from('<I', data, table + 4 * index)
    if not entry:
        raise ValueError('Cinematic resource is absent from this file')
    start = table + (entry & 0xFFFFFF)
    width, height = row['rect'][2:]
    if not 0 < width <= 1024 or not 0 < height <= 512:
        raise ValueError('Cinematic resource dimensions are invalid')
    end = start + width * height * 2
    if start < table + 4 * (index + 1) or end > len(data):
        raise ValueError('Cinematic resource pixels are truncated')
    return data[start:end]
