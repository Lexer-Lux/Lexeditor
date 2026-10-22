"""Lightmapped meshes name their baked light and ship its UVs.

Map materials pair a tiling diffuse with a baked lightmap over a
second, atlas-ranged UV set. The encoder ships the lightmap stem as
`light` and its UVs as `uv1`; the map viewport then renders those
meshes unlit (map times light) the way the game does.
"""
import base64
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugins.ds1.viewport import _encode, _lightmap_name


def test_lightmap_name_extraction():
    material = {'textures': [
        {'type': 'g_Diffuse', 'path': 'N:\\FRPG\\m10_wall.tga'},
        {'type': 'g_Lightmap', 'path': 'N:\\FRPG\\Model\\map\\m10\\tex\\m10_01_00_lit_B1m2000.tga'},
        {'type': 'g_DetailBumpmap', 'path': ''}]}
    assert _lightmap_name(material) == 'm10_01_00_lit_B1m2000'
    assert _lightmap_name({'textures': [{'type': 'g_Diffuse', 'path': 'x.tga'}]}) is None
    assert _lightmap_name({'textures': [{'type': 'g_Lightmap', 'path': ''}]}) is None
    assert _lightmap_name({'textures': []}) is None


class StubDoc:
    def __init__(self, textures):
        self.meshes = [{'material': {'textures': textures}}]
        self.notes = []

    def mesh_data(self, _index):
        return {'material': 'mat', 'mat_def': 'M[D][L].mtd', 'dynamic': False,
                'cull': True, 'bbox': None, 'positions': [(0.0, 0.0, 0.0)] * 2,
                'normals': [(0.0, 1.0, 0.0)] * 2, 'uvs': [(0.0, 0.0)] * 2,
                'uvs2': [(0.5, 0.5)] * 2, 'triangles': []}


def unpack(entry):
    raw = base64.b64decode(entry)
    return struct.unpack('<%df' % (len(raw) // 4), raw)


def test_encode_ships_light_name_and_uv1():
    doc = StubDoc([{'type': 'g_Diffuse', 'path': 'm10_wall.tga'},
                   {'type': 'g_Lightmap', 'path': 'm10_01_00_lit_B1m2000.tga'}])
    entry = _encode(doc, textured=True)['meshes'][0]
    assert entry['map'] == 'm10_wall'
    assert entry['light'] == 'm10_01_00_lit_B1m2000'
    assert unpack(entry['uv1']) == (0.5, 0.5, 0.5, 0.5)


def test_encode_without_lightmap_ships_no_light():
    doc = StubDoc([{'type': 'g_Diffuse', 'path': 'm10_wall.tga'}])
    entry = _encode(doc, textured=True)['meshes'][0]
    assert entry['light'] is None
