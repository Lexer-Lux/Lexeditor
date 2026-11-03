"""Split texture archives: BHF parsing plus map/chr wiring on synthetic files."""
import base64
import io
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pytest
from bhf_fixture import make_bhf, make_edge
from PIL import Image
from flver_fixture import build_flver, make_chrbnd
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import viewport
from plugins.ds1.bhf import BhfError, member_tpf, parse_bhf


def test_parse_lists_members_by_filename():
    bhd = make_bhf([(r'\m99\m99_00_wall.tpf.dcx', 16, 200),
                    (r'\c1200\c1200.tpf.dcx', 500, 300)])
    assert parse_bhf(bhd) == {'m99_00_wall': (16, 200), 'c1200': (500, 300)}


def test_parse_skips_partial_slot():
    bhd = make_bhf([(r'\m99\tex0.tpf.dcx', 16, 200)]) + struct.pack('<2I', 999, 64)
    assert parse_bhf(bhd) == {'tex0': (16, 200)}


def test_parse_rejects_bad_magic():
    with pytest.raises(BhfError):
        parse_bhf(b'BND3' + bytes(100))


def test_member_round_trip(tmp_path):
    red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
    blob = make_edge(make_tpf([('tex0', red)]))
    bdt = tmp_path / 'm99_0000.tpfbdt'
    bdt.write_bytes(bytes(16) + blob)
    bhd = make_bhf([(r'\m99\tex0.tpf.dcx', 16, len(blob))])
    assert member_tpf(bhd, bdt, 'tex0') == make_tpf([('tex0', red)])
    assert member_tpf(bhd, bdt, 'missing') is None


def game_with_split_map(tmp_path):
    game = tmp_path / 'game'
    folder = game / 'map' / 'm99_00_00_00'
    folder.mkdir(parents=True)
    (folder / 'm99piece.flver.dcx').write_bytes(build_flver())
    red = make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16)
    blob = make_edge(make_tpf([('tex0', red)]))
    area = game / 'map' / 'm99'
    area.mkdir(parents=True)
    (area / 'm99_0000.tpfbdt').write_bytes(bytes(16) + blob)
    (area / 'm99_0000.tpfbhd').write_bytes(
        make_bhf([(r'\m99\tex0.tpf.dcx', 16, len(blob))]))
    return game


def test_map_piece_resolves_split_texture(tmp_path):
    game = game_with_split_map(tmp_path)
    geometry = viewport.model_geometry(game, None, 'm99_00_00_00.msb',
                                       {'type': 0, 'name': 'm99piece'})
    mesh = geometry['meshes'][0]
    assert mesh['map'] == 'tex0' and mesh['uv']
    image = Image.open(io.BytesIO(base64.b64decode(geometry['textures']['tex0'])))
    image.load()
    assert image.size == (4, 4)
    assert image.convert('RGB').getpixel((0, 0)) == (255, 0, 0)


def test_chr_companion_resolves(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    blue = make_dds_rgba(2, 2, [(0, 0, 255, 255)] * 4)
    blob = make_edge(make_tpf([('tex0', blue)]))
    bhd = make_bhf([(r'\c1200\tex0.tpf.dcx', 16, len(blob))])
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), 'c1200', [('c1200.chrtpfbhd', bhd)]))
    (game / 'chr' / 'c1200.chrtpfbdt').write_bytes(bytes(16) + blob)
    geometry = viewport.chr_geometry(game, None, 'c1200')
    assert set(geometry['textures']) == {'tex0'}


def test_missing_companion_data_file_is_reported(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    bhd = make_bhf([(r'\c1200\tex0.tpf.dcx', 16, 200)])
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), 'c1200', [('c1200.chrtpfbhd', bhd)]))
    geometry = viewport.chr_geometry(game, None, 'c1200')
    assert geometry['textures'] == {}
    assert any('c1200.chrtpfbdt' in note for note in geometry['notes'])
