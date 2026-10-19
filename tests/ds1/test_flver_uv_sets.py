"""Two UV sets stay separate: lightmapped meshes keep diffuse UVs.

Real DS1 map pieces carry a second UV pair per vertex (the lightmap
channel). The parser used to merge both sets into one list, so the
viewport encoder saw twice as many UVs as positions and shipped no
UVs at all - and the map viewport renders meshes without UVs gray.
That is why lightmapped terrain (the Kiln's ground, the Burg's
grass) showed untextured. The first set ships as uv, the second as
uv1 for the lightmap step.
"""
import base64
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flver_fixture import build_flver
from plugins.ds1.flver import FlverDocument
from plugins.ds1.viewport import _encode


def unpack(entry):
    raw = base64.b64decode(entry)
    return struct.unpack('<%df' % (len(raw) // 4), raw)


def test_second_uv_set_stays_separate():
    mesh = FlverDocument(build_flver(second_uv=True)).mesh_data(0)
    assert len(mesh['positions']) == 4
    assert mesh['uvs'] == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    assert mesh['uvs2'] == [(10.0, 20.0), (11.0, 20.0), (11.0, 21.0), (10.0, 21.0)]


def test_encode_ships_both_uv_sets():
    entry = _encode(FlverDocument(build_flver(second_uv=True)), textured=True)['meshes'][0]
    assert unpack(entry['uv']) == (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    assert unpack(entry['uv1']) == (10.0, 20.0, 11.0, 20.0, 11.0, 21.0, 10.0, 21.0)


def test_single_uv_mesh_has_empty_second_set():
    doc = FlverDocument(build_flver())
    assert doc.mesh_data(0)['uvs2'] == []
    entry = _encode(doc, textured=True)['meshes'][0]
    assert base64.b64decode(entry['uv1']) == b''
    assert len(unpack(entry['uv'])) == 8


def test_lightmapped_single_uv_mesh_reuses_diffuse_uvs():
    # Depths pieces (m2130B0A10 et al) carry one UV pair per vertex
    # and an [L]-suffixed lightmapped material: 0 of 688 meshes in
    # m10_00_00_00 ship a second set. The game samples the lightmap
    # with the diffuse interpolants, so the encoder repeats uv as
    # uv1 instead of leaving the light path dead (fullbright map).
    entry = _encode(FlverDocument(build_flver(light_tex='lit0')),
                    textured=True)['meshes'][0]
    assert entry['light'] == 'lit0'
    assert base64.b64decode(entry['uv1']) != b''
    assert unpack(entry['uv1']) == unpack(entry['uv'])
