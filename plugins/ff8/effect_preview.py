"""Static mesh materials at the object's first simulated use in its summon."""
import base64
from io import BytesIO
import re

from PIL import Image

from . import assets, effect_mesh, effect_textures, effect_timeline, paths
from .fs_archive import FsArchive


def _files(family: int, dataset: str) -> dict:
    if dataset == 'current':
        roots = [paths.DIRECT_ROOT]
    elif dataset == 'vanilla':
        roots = []
    elif dataset.startswith('reference:'):
        root = assets._reference_root(dataset)
        roots = [root / 'direct', root]
    elif dataset.startswith('mod:'):
        root = assets._managed_root(dataset)
        roots = [root / 'direct', root]
    else:
        raise ValueError('Unknown summon dataset')
    result = {}
    total_bytes = 0
    for archive_name in ('magic', 'battle'):
        archive = FsArchive(paths.GAME_ROOT / 'Data/lang-en' / archive_name)
        for entry in archive.entries:
            filename = entry.basename
            match = re.fullmatch(fr'mag{family:03}_b\.(\d+)', filename)
            if match:
                key = int(match[1])
                if key >= 64:
                    raise ValueError('Summon file slot is outside preview bounds')
            elif filename in ('ma8def_p.0', 'ma8def_p.1', 'ma8def_p.2'):
                key = filename
            else:
                continue
            override = next((root / archive_name / filename for root in roots
                             if (root / archive_name / filename).is_file()), None)
            if override is not None:
                size = override.stat().st_size
                if size > 16 * 1024 * 1024 or total_bytes + size > 64 * 1024 * 1024:
                    raise ValueError('Summon override exceeds preview size limit')
                result[key] = override.read_bytes()
            else:
                if entry.unpacked_length > 16 * 1024 * 1024 or total_bytes + entry.unpacked_length > 64 * 1024 * 1024:
                    raise ValueError('Summon archive entry exceeds preview size limit')
                result[key] = archive.extract(entry)
            total_bytes += len(result[key])
    return result


def material_state(simulation, object_id: int, description: dict):
    uses = [(when, bone) for bone in simulation.bones for when, key, value in bone.props
            if key == 'mesh' and value == object_id]
    if not uses:
        return None
    tick, bone = min(uses, key=lambda entry: entry[0])
    page, clut = 0, 0
    for when, key, value in bone.props:
        if when > tick:
            break
        if key != 'tex_op':
            continue
        code, op, words = value
        if code == 0x52:
            index = words[0]
            if index == -1:
                page = clut = 0
            elif 0 <= index < min(len(description['textures']), len(description['cluts'])):
                texture, palette = description['textures'][index], description['cluts'][index]
                x, y = texture['rect'][:2]
                page = (page & 0x60) | (128 if texture['depth'] == 8 else 0) | (((y & 256) | ((x >> 2) & 1008)) >> 4)
                x, y = palette['rect'][:2]
                clut = ((x >> 4) & 63) | ((y & 511) << 6)
            else:
                raise ValueError('Summon material references an unavailable texture')
        elif code == 0x78:
            clut = 14356 + (words[0] & 15) + 4 * (words[0] & 496)
        elif code == 0x92:
            page, clut = words[0] & 65535, words[1] & 65535
        elif code == 0x23:
            blend = op >> 9
            page = (page & ~96) | ((blend if blend <= 3 else 1) << 5)
    return tick, page, clut


def _texture_sources(filename: str, dataset: str):
    match = effect_mesh.FILENAME.fullmatch(filename)
    if match is None:
        raise ValueError('Unsupported summon filename')
    family, slot = int(match[1]), int(filename.rpartition('.')[2])
    files = _files(family, dataset)
    description = effect_textures.descriptor((paths.GAME_ROOT / 'FF8_EN.exe').read_bytes(), family)
    return slot, files, description


def texture_options(filename: str, dataset: str) -> dict:
    slot, files, description = _texture_sources(filename, dataset)
    rows = []
    for texture in description['textures']:
        if texture['slot'] != slot or slot not in files:
            continue
        effect_textures.resource_bytes(files[slot], texture, texture=True)
        depth = texture['depth']
        colors = 1 << depth
        choices = []
        for palette in description['cluts']:
            if palette['slot'] is None or palette['slot'] not in files or palette['rect'][2] % colors:
                continue
            data = effect_textures.resource_bytes(files[palette['slot']], palette, texture=False)
            for bank in range(len(data) // (colors * 2)):
                choices.append({'value': f"{palette['id']}:{bank}",
                                'name': f"Palette {palette['id']}" + (f' · Part {bank + 1}' if len(data) > colors * 2 else '')})
                if len(choices) > 4096:
                    raise ValueError('Summon exceeds preview palette limit')
        default = f"{texture['id']}:0"
        rows.append({'id': texture['id'], 'width': texture['rect'][2] * (16 // depth),
                     'height': texture['rect'][3], 'depth': depth, 'palettes': choices,
                     'palette': default if any(choice['value'] == default for choice in choices) else (choices[0]['value'] if choices else None)})
    return {'rows': rows}


def texture_png(filename: str, dataset: str, texture_id: int, palette_key: str) -> bytes:
    slot, files, description = _texture_sources(filename, dataset)
    if not 0 <= texture_id < len(description['textures']):
        raise ValueError('Unknown summon texture')
    texture = description['textures'][texture_id]
    if texture['slot'] != slot or slot not in files:
        raise ValueError('Summon texture is not stored in this file')
    if not re.fullmatch(r'\d{1,4}:\d{1,4}', palette_key):
        raise ValueError('Invalid summon palette selection')
    palette_id, bank = map(int, palette_key.split(':'))
    if not 0 <= palette_id < len(description['cluts']):
        raise ValueError('Unknown summon palette')
    palette = description['cluts'][palette_id]
    depth, colors = texture['depth'], 1 << texture['depth']
    if palette['slot'] is None or palette['slot'] not in files or palette['rect'][2] % colors:
        raise ValueError('Summon palette is unavailable for this image depth')
    palette_data = effect_textures.resource_bytes(files[palette['slot']], palette, texture=False)
    if bank >= len(palette_data) // (colors * 2):
        raise ValueError('Summon palette part is outside the resource')
    palette_data = palette_data[bank * colors * 2:(bank + 1) * colors * 2]
    pixels = effect_textures.resource_bytes(files[slot], texture, texture=True)
    size = texture['rect'][2] * (16 // depth), texture['rect'][3]
    rgba = effect_textures.indexed_rgba(pixels, palette_data, *size, depth)
    output = BytesIO()
    Image.frombytes('RGBA', size, rgba).save(output, format='PNG')
    return output.getvalue()


def scene(filename: str, dataset: str, object_id: int | None = None) -> dict:
    match = effect_mesh.FILENAME.fullmatch(filename)
    if match is None:
        raise ValueError('Unsupported summon filename')
    family = int(match[1])
    files = _files(family, dataset)
    slot = int(filename.rpartition('.')[2])
    result = effect_mesh.scene(filename, files[slot], object_id)
    description = effect_textures.descriptor((paths.GAME_ROOT / 'FF8_EN.exe').read_bytes(), family)
    simulation = effect_timeline.simulate(files[0])
    state = material_state(simulation, result['objectId'], description)
    if state is None:
        return result
    tick, page, clut = state
    memory = effect_textures.TextureMemory(description, files).replay(simulation.vram_events, tick)
    if memory.missing:
        raise ValueError('Summon texture upload source is unavailable')
    images, materials = [], {}
    for triangle in result['triangles']:
        source = triangle.pop('sourceTexture', None)
        if source is None:
            continue
        key = (source['tpage'] | page, (source['clut'] + clut) & 65535)
        if key not in materials:
            if len(images) >= 64:
                raise ValueError('Summon mesh exceeds texture-page preview limit')
            output = BytesIO()
            Image.frombytes('RGBA', (256, 256), memory.page_rgba(*key)).save(output, format='PNG')
            materials[key] = len(images)
            images.append('data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii'))
        triangle['texture'] = materials[key]
    result.update(textures=list(range(len(images))), textureImages=images, previewTick=tick)
    return result
