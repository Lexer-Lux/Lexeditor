"""Textured drawer geometry: UVs, diffuse names and decoded PNGs on synthetic files."""
import base64
import io
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from flver_fixture import build_flver, make_chrbnd
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import viewport


def game_with_part(tmp_path, stem, tpf=None):
    game = tmp_path / 'game'
    (game / 'parts').mkdir(parents=True)
    extra = [(f'{stem}.tpf', tpf)] if tpf is not None else []
    (game / 'parts' / f'{stem}.partsbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), stem, extra))
    return game


def test_textured_part_serves_uv_map_and_png(tmp_path):
    red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
    game = game_with_part(tmp_path, 'WP_A_0100', make_tpf([('tex0', red)]))
    geometry = viewport.part_geometry(game, None, 'WP_A_0100')
    assert len(geometry['meshes']) == 1
    mesh = geometry['meshes'][0]
    flat = base64.b64decode(mesh['uv'])
    uvs = struct.unpack('<%df' % (len(flat) // 4), flat)
    assert uvs == (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
    assert mesh['map'] == 'tex0'
    image = Image.open(io.BytesIO(base64.b64decode(geometry['textures']['tex0'])))
    image.load()
    assert image.size == (4, 4)
    assert image.convert('RGB').getpixel((0, 0)) == (255, 0, 0)


def test_chr_geometry_serves_textures(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    blue = make_dds_rgba(2, 2, [(0, 0, 255, 255)] * 4)
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), 'c1200', [('c1200.tpf', make_tpf([('tex0', blue)]))]))
    geometry = viewport.chr_geometry(game, None, 'c1200')
    assert geometry['meshes'][0]['map'] == 'tex0'
    assert set(geometry['textures']) == {'tex0'}


def test_part_without_tpf_renders_gray_with_note(tmp_path):
    game = game_with_part(tmp_path, 'WP_A_0100')
    geometry = viewport.part_geometry(game, None, 'WP_A_0100')
    mesh = geometry['meshes'][0]
    assert mesh['map'] == 'tex0' and mesh['uv']
    assert geometry['textures'] == {}
    assert any('tex0' in note for note in geometry['notes'])


def test_map_geometry_serves_textured_shape(tmp_path):
    game = tmp_path / 'game'
    folder = game / 'map' / 'm99_00_00_00'
    folder.mkdir(parents=True)
    (folder / 'm99piece.flver.dcx').write_bytes(build_flver())
    geometry = viewport.model_geometry(game, None, 'm99_00_00_00.msb',
                                       {'type': 0, 'name': 'm99piece'})
    mesh = geometry['meshes'][0]
    assert mesh['map'] == 'tex0' and mesh['uv']
    assert geometry['textures'] == {}
    assert any('tex0' in note for note in geometry['notes'])
