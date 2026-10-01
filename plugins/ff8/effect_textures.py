"""Read cinematic texture/CLUT sources; script upload order remains significant.

Source: FF8UltimateEditor/FF8GameData/magcine/cinevram.py and the GF cinematic
format reference. Descriptor addresses were verified against the supported EXE.
No executable, palette or texture bytes are bundled with the editor.
"""
import struct
from array import array

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


def indexed_rgba(pixels: bytes, palette: bytes, width: int, height: int, depth: int) -> bytes:
    """Decode one exact indexed resource with an explicitly selected palette."""
    if depth not in (4, 8) or not 0 < width <= 4096 or not 0 < height <= 512:
        raise ValueError('Unsupported summon image dimensions or depth')
    if width * height * depth != len(pixels) * 8 or len(palette) != (1 << depth) * 2:
        raise ValueError('Summon image or palette has incomplete pixels')
    colors = []
    for packed, in struct.iter_unpack('<H', palette):
        channels = [((packed >> shift) & 31) for shift in (0, 5, 10)]
        colors.append(bytes([(value << 3) | (value >> 2) for value in channels] + [255 if packed else 0]))
    rgba = bytearray()
    for packed in pixels:
        if depth == 4:
            rgba.extend(colors[packed & 15])
            rgba.extend(colors[packed >> 4])
        else:
            rgba.extend(colors[packed])
    return bytes(rgba)


class TextureMemory:
    """One bounded PSX VRAM snapshot, replayed in script order up to a tick."""

    def __init__(self, description: dict, files: dict[int | str, bytes]):
        self.description, self.files = description, files
        self.words = array('H', [0]) * (1024 * 512)
        self.present = bytearray(1024 * 512)
        self.missing = []

    def write(self, rect, data: bytes):
        x, y, width, height = rect
        if not (0 <= x < 1024 and 0 <= y < 512 and 0 < width <= 1024 - x and 0 < height <= 512 - y):
            raise ValueError('Texture upload rectangle is outside VRAM')
        if len(data) != width * height * 2:
            raise ValueError('Texture upload has incomplete pixels')
        for row in range(height):
            values = struct.unpack_from(f'<{width}H', data, row * width * 2)
            start = (y + row) * 1024 + x
            self.words[start:start + width] = array('H', values)
            self.present[start:start + width] = b'\x01' * width

    def upload(self, index: int, *, texture: bool):
        rows = self.description['textures' if texture else 'cluts']
        if not 0 <= index < len(rows):
            raise ValueError('Texture upload resource ID is outside its table')
        row = rows[index]
        slot = row['slot']
        if slot is None or slot not in self.files:
            self.missing.append(('texture' if texture else 'clut', index, slot))
            return
        self.write(row['rect'], resource_bytes(self.files[slot], row, texture=texture))

    def replay(self, events: list, tick: int):
        if not 0 <= tick <= 3000 or len(events) > 100000:
            raise ValueError('Texture replay exceeds preview limits')
        self.words = array('H', [0]) * (1024 * 512)
        self.present = bytearray(1024 * 512)
        self.missing = []
        # Begin with known packed resources, matching the preview simulator's
        # baseline. The script may replace these rectangles with streamed pages.
        for texture, rows in ((True, self.description['textures']), (False, self.description['cluts'])):
            for row in rows:
                if row['slot'] is not None and row['slot'] in self.files:
                    self.upload(row['id'], texture=texture)
        for when, kind, args in events:
            if when > tick:
                break
            if kind in ('tex', 'clut'):
                self.upload(args[0], texture=kind == 'tex')
            elif kind in ('raw', 'rawrect'):
                if kind == 'raw':
                    index, slot, offset = args
                    if not 0 <= index < len(self.description['textures']):
                        raise ValueError('Raw texture rectangle ID is outside its table')
                    rect = self.description['textures'][index]['rect']
                else:
                    rect, slot = args
                    offset = 0
                if slot not in self.files:
                    self.missing.append((kind, slot))
                    continue
                if offset < 0:
                    raise ValueError('Raw texture upload has a negative offset')
                length = rect[2] * rect[3] * 2
                self.write(rect, self.files[slot][offset:offset + length])
            else:
                raise ValueError(f'Unsupported texture upload event {kind}')
        return self

    def page_rgba(self, tpage: int, clut: int) -> bytes:
        if not 0 <= tpage <= 65535 or not 0 <= clut <= 65535:
            raise ValueError('Texture page and palette must be 16-bit values')
        mode = (tpage >> 7) & 3
        if mode == 3:
            raise ValueError('Unsupported texture page depth')
        base_x, base_y = (tpage & 15) * 64, ((tpage >> 4) & 1) * 256
        palette_x, palette_y = (clut & 63) * 16, (clut >> 6) & 511
        rgba = bytearray(256 * 256 * 4)
        def word(x, y):
            return self.words[y * 1024 + x] if 0 <= x < 1024 and 0 <= y < 512 else 0
        for y in range(256):
            for x in range(256):
                packed = word(base_x + (x >> (2 - mode)), base_y + y)
                if mode == 0:
                    color = word(palette_x + ((packed >> ((x & 3) * 4)) & 15), palette_y)
                elif mode == 1:
                    color = word(palette_x + ((packed >> ((x & 1) * 8)) & 255), palette_y)
                else:
                    color = packed
                offset = (y * 256 + x) * 4
                for channel, shift in enumerate((0, 5, 10)):
                    value = (color >> shift) & 31
                    rgba[offset + channel] = (value << 3) | (value >> 2)
                rgba[offset + 3] = 0 if color == 0 else 255
        return bytes(rgba)
