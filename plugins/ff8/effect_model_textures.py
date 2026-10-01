"""Resolve skeletal summon materials against sibling TIM coordinates.

https://hobbitdur.github.io/FF8ModdingWiki/technical-reference/battle/summon-creature-models/
Only a unique image containing both the face's palette and pixel coordinates
is accepted. Overlapping or missing sources remain plain geometry.
"""
from types import SimpleNamespace
import struct

from . import assets


def sources(filename: str, dataset: str) -> dict[str, bytes]:
    result = {}
    total = 0
    for entry in assets._battle_archive_index():
        name = entry['file']
        if name[:6] != filename[:6] or name == filename:
            continue
        source = assets._battle_path(name, dataset)
        size = source.stat().st_size if source.is_file() else entry['sizeBytes']
        if size > 16 * 1024 * 1024:
            raise ValueError('Effect texture source exceeds size limit')
        data, _ = assets._model_bytes(name, dataset)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError('Effect texture source exceeds size limit')
        if assets._standalone_texture_info(data) is None:
            continue
        total += len(data)
        if total > 32 * 1024 * 1024:
            raise ValueError('Effect texture sources exceed preview limit')
        result[name] = data
    return result


def tim_region(data: bytes) -> dict:
    info = assets._tim_layout(data)
    if info['size'] != len(data) or info['depth'] not in (4, 8) or not info['paletteCount']:
        raise ValueError('Effect material requires a complete indexed TIM')
    palette_size, px, py, pw, ph = struct.unpack_from('<I4H', data, 8)
    _, x, y, _, _ = struct.unpack_from('<I4H', data, 8 + palette_size)
    if px + pw > 1024 or py + ph > 512 or x + info['width'] // (16 // info['depth']) > 1024 or y + info['height'] > 512:
        raise ValueError('Effect TIM rectangle is outside video memory')
    return {**info, 'x': x, 'y': y, 'paletteX': px, 'paletteY': py,
            'paletteWidth': pw, 'paletteHeight': ph}


def match_material(region: dict, page: int, clut: int, uv: list[tuple]) -> tuple | None:
    mode = (page >> 7) & 3
    if mode > 1 or region['depth'] != (4 if mode == 0 else 8):
        return None
    colors = 1 << region['depth']
    cx, cy = (clut & 63) * 16, clut >> 6
    dx, dy = cx - region['paletteX'], cy - region['paletteY']
    if not (0 <= dy < region['paletteHeight'] and 0 <= dx <= region['paletteWidth'] - colors):
        return None
    palette_start = dy * region['paletteWidth'] + dx
    if palette_start % colors:
        return None
    scale = 16 // region['depth']
    left = ((page & 15) * 64 - region['x']) * scale
    top = ((page >> 4) & 1) * 256 - region['y']
    points = [(left + u, top + v) for u, v in uv]
    if not all(0 <= u < region['width'] and 0 <= v < region['height'] for u, v in points):
        return None
    return palette_start // colors, [(u / region['width'], v / region['height']) for u, v in points]


def resolve(exporter, images: dict[str, bytes]) -> None:
    regions = [(name, tim_region(data)) for name, data in images.items()]
    geometry = exporter.ifrit_manager.enemy.geometry_data
    colored = [face for face in exporter._collect_triangulated_faces() if face[2] < 0]
    faces, textures, materials = [], [], {}
    base = 0
    missing = 0
    for obj in geometry.object_data:
        for primitive in obj.triangles + obj.quads:
            if primitive.is_hidden():
                continue
            corners = [primitive.vta, primitive.vtb, primitive.vtc]
            is_quad = len(primitive.vertex_indexes) == 4
            if is_quad:
                corners.append(primitive.vtd)
            uv = [(corner.get_u_raw(), corner.get_v_raw()) for corner in corners]
            matches = [(name, match_material(region, primitive.tex_id_2, primitive.tex_id_1, uv))
                       for name, region in regions]
            matches = [(name, match) for name, match in matches if match is not None]
            texture = -0xD7C3B4 - 2
            normalized = [(0, 0)] * len(corners)
            if len(matches) == 1:
                name, (palette, normalized) = matches[0]
                key = name, palette
                if key not in materials:
                    if len(textures) >= 128:
                        raise ValueError('Effect model exceeds material limit')
                    materials[key] = len(textures)
                    textures.append(SimpleNamespace(index=len(textures),
                        texture_image=assets.tim_png_bytes(images[name], palette=palette)))
                texture = materials[key]
            else:
                missing += 1
            indices = [base + index for index in primitive.vertex_indexes]
            if not is_quad:
                indices = [indices[2], indices[0], indices[1]]
            for triangle in (((0, 1, 3), (0, 2, 3)) if is_quad else ((0, 1, 2),)):
                faces.append((tuple(indices[i] for i in triangle), tuple(normalized[i] for i in triangle), texture))
        base += sum(group.nb_vertices for group in obj.vertices_data)
    exporter._resolved_faces = faces + colored
    exporter.ifrit_manager.texture_data = textures
    exporter.unmapped_effect_faces = missing
