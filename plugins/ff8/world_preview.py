"""Read-only world preview assets; bounded cache, no generated files on disk."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
import struct

from PIL import Image

from . import assets, world_geometry, world_map, world_textures


def _key(path):
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns


@lru_cache(maxsize=2)
def _mesh(key):
    return world_geometry.preview_vertices(Path(key[0]).read_bytes())


def mesh_bytes(dataset='current'):
    return _mesh(_key(world_geometry.source_path(dataset)))


def _tim_image(payload):
    layout = assets._tim_layout(payload)
    header = 8 + (struct.unpack_from('<I', payload, 8)[0] if layout['paletteCount'] else 0)
    x, y = struct.unpack_from('<HH', payload, header + 4)
    image = Image.open(BytesIO(assets.tim_png_bytes(payload))).convert('RGBA')
    if layout['paletteCount'] == 16 and image.size == (256, 256):
        for palette in range(16):
            left, top = palette % 4 * 64, palette // 4 * 64
            tile = Image.open(BytesIO(assets.tim_png_bytes(payload, palette=palette))).convert('RGBA')
            image.paste(tile.crop((left, top, left + 64, top + 64)), (left, top))
    return image, x, y


def _section_images(raw, section, count, indices):
    pointers = world_map._pointers(raw)
    data = raw[pointers[section]:pointers[section + 1]]
    offsets = list(struct.unpack_from(f'<{count}I', data)) + [len(data)]
    if any(a < count * 4 or a >= b or b > len(data) for a, b in zip(offsets, offsets[1:])):
        raise ValueError('World texture offsets are invalid')
    return [_tim_image(data[offsets[i]:offsets[i+1]]) for i in indices]


def _compose(images):
    left, top = min(x for _, x, _ in images), min(y for _, _, y in images)
    width = max(x + image.width for image, x, _ in images) - left
    height = max(y + image.height for image, _, y in images) - top
    if width > 256 or height > 256:
        raise ValueError('World texture composition exceeds its atlas page')
    output = Image.new('RGBA', (256, 256))
    for image, x, y in images:
        output.alpha_composite(image, (x-left, y-top))
    return output


@lru_cache(maxsize=2)
def _atlas(texture_key, world_key):
    raw = Path(texture_key[0]).read_bytes()
    atlas = Image.new('RGBA', (1280, 1280))
    for index in range(world_textures.TEXTURE_COUNT):
        payload = raw[index * world_textures.SLOT_SIZE:(index+1) * world_textures.SLOT_SIZE]
        image, _, _ = _tim_image(payload)
        atlas.paste(image, (index // 5 * 256, index % 5 * 256))
    world = Path(world_key[0]).read_bytes()
    # Deling: special textures start at index 9; Sea1..Sea5 span 7..14.
    atlas.paste(_compose(_section_images(world, 37, 36, range(16, 24))), (1024, 0))
    atlas.paste(_compose(_section_images(world, 38, 13, range(13))), (1024, 256))
    output = BytesIO()
    atlas.save(output, format='PNG')
    return output.getvalue()


def atlas_png(dataset='current'):
    return _atlas(_key(world_textures.source_path(dataset)), _key(world_map.source_path(dataset)))
