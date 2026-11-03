"""Map opens reuse inflated binders and area texture tables.

Duke's Archives shows hundreds of models sharing one area's texture
archives: re-reading, re-inflating and re-parsing those containers
for every model made the map open slowly. Repeated lookups against
the same containers must hit a cache, keyed by file stamp so a
rebuilt mod still reloads.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bhf_fixture import make_bhf, make_edge
from flver_fixture import build_flver, make_chrbnd
from tpf_fixture import make_dds_rgba, make_tpf
from plugins.ds1 import viewport


def game_with_shared_area(tmp_path):
    game = tmp_path / 'game'
    (game / 'obj').mkdir(parents=True)
    (game / 'obj' / 'o1000.objbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), 'o1000'))
    blob = make_edge(make_tpf([('tex0', make_dds_rgba(4, 4, [(255, 0, 0, 255)] * 16))]))
    folder = game / 'map' / 'm13'
    folder.mkdir(parents=True)
    (folder / 'm13_0000.tpfbdt').write_bytes(bytes(16) + blob)
    (folder / 'm13_0000.tpfbhd').write_bytes(
        make_bhf([(r'\m13\tex0.tpf.dcx', 16, len(blob))]))
    return game


def resolve_five_times(game):
    binder = str(game / 'obj' / 'o1000.objbnd.dcx')
    for _ in range(5):
        found, _notes = viewport._resolve_textures(
            'member', binder, 'o1000.flver', ['tex0'], str(game), None,
            viewport.MAP_TEXTURE_CAP, 'm13')
        assert set(found) == {'tex0'}


def test_area_texture_tables_parse_once(tmp_path, monkeypatch):
    game = game_with_shared_area(tmp_path)
    real = viewport.parse_bhf
    calls = []
    monkeypatch.setattr(viewport, 'parse_bhf',
                        lambda blob: calls.append(1) or real(blob))
    resolve_five_times(game)
    assert len(calls) == 1, calls


def game_with_many_tilesets(tmp_path, count=40):
    game = tmp_path / 'game'
    for index in range(10, 10 + count):
        folder = game / 'map' / ('m%02d' % index)
        folder.mkdir(parents=True)
        (folder / 'm_x.tpfbdt').write_bytes(bytes(16))
        (folder / 'm_x.tpfbhd').write_bytes(
            make_bhf([(r'\m%02d\zz%d.tpf.dcx' % (index, index), 16, 8)]))
    return game


def resolve_missing_twice(game):
    for _ in range(2):
        found, _notes = viewport._resolve_textures(
            'piece', str(game / 'map' / 'm10' / 'm10piece.flver.dcx'),
            '', ['tex0'], str(game), None, viewport.MAP_TEXTURE_CAP, 'm10')
        assert found == {}


def test_tileset_sweep_parses_each_header_once(tmp_path, monkeypatch):
    game = game_with_many_tilesets(tmp_path)
    real = viewport.parse_bhf
    calls = []
    monkeypatch.setattr(viewport, 'parse_bhf',
                        lambda blob: calls.append(1) or real(blob))
    resolve_missing_twice(game)
    assert len(calls) == 40, calls


def test_shared_tpf_members_inflate_once(tmp_path, monkeypatch):
    game = game_with_shared_area(tmp_path)
    real = viewport.inflate_member
    calls = []
    monkeypatch.setattr(viewport, 'inflate_member',
                        lambda bdt, off, size: calls.append(1) or real(bdt, off, size))
    resolve_five_times(game)
    assert len(calls) == 1, calls


def test_shared_binder_inflates_once(tmp_path, monkeypatch):
    game = game_with_shared_area(tmp_path)
    real = viewport.inflate
    calls = []
    monkeypatch.setattr(viewport, 'inflate',
                        lambda blob: calls.append(1) or real(blob))
    resolve_five_times(game)
    assert len(calls) == 1, calls
