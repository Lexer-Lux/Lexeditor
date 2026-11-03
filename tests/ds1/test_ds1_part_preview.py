"""Weapon and armor rows resolve to their parts-binder models.

A preview drawer shows the mesh a row wears; these tests pin the binder
stem rules, the no-model reasons, and the binder reading behind them.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from plugins.ds1.formats import ItemDocument, write_field
from plugins.ds1 import viewport
from plugins.ds1.flver import FlverError


def put(document, table, row_id, key, value):
    _row, start, data = document._row(table, row_id)
    spec = next(f['spec'] for f in document.schemas[table]['fields'] if f['spec'].key == key)
    document.plain[start:start + len(data)] = write_field(data, spec, value, '<')


def test_weapon_rows_resolve_to_their_wp_stem():
    document = ItemDocument(make_archive())
    put(document, 'EquipParamWeapon', 100, 'equipModelId', 100)
    info = document.part_model('EquipParamWeapon', 100)
    assert info['available'] and info['model_id'] == 100
    stems, reason = viewport.part_candidates('EquipParamWeapon', info['category'], info['gender'], 100)
    assert reason is None
    assert stems == [('WP_A_0100', None)]


def test_armor_piece_and_fit_name_the_binder():
    document = ItemDocument(make_archive())
    cases = {(1, 1): [('AM_M_0100', None)], (2, 2): [('BD_F_0100', None)],
             (5, 0): [('HD_A_0100', None)], (6, 4): [('LG_A_0100', None)],
             (2, 5): [('BD_E_0100', None)],
             (2, 3): [('BD_M_0100', 'M'), ('BD_F_0100', 'F')]}
    for (category, gender), expected in cases.items():
        put(document, 'EquipParamProtector', 100, 'equipModelId', 100)
        put(document, 'EquipParamProtector', 100, 'equipModelCategory', category)
        put(document, 'EquipParamProtector', 100, 'equipModelGender', gender)
        info = document.part_model('EquipParamProtector', 100)
        assert info['available'], (category, gender)
        stems, reason = viewport.part_candidates('EquipParamProtector', category, gender, 100)
        assert reason is None
        assert stems == expected


def test_faces_hair_and_bare_rows_have_no_model():
    document = ItemDocument(make_archive())
    for category in (3, 4):
        put(document, 'EquipParamProtector', 100, 'equipModelCategory', category)
        info = document.part_model('EquipParamProtector', 100)
        assert not info['available'] and 'face generator' in info['reason']
    stems, _reason = viewport.part_candidates('EquipParamProtector', 0, 0, 100)
    assert stems is None
    stems, _reason = viewport.part_candidates('EquipParamProtector', 9, 0, 100)
    assert stems is None
    for table, row_id in (('EquipParamGoods', 100), ('EquipParamAccessory', 100)):
        info = document.part_model(table, row_id)
        assert not info['available'] and 'no model file' in info['reason']
    info = document.part_model('Magic', 100)
    assert not info['available']


def test_part_binder_traversal_is_rejected(tmp_path):
    for stem in ('../evil', '..\\evil', 'a/b', '', None, 'WP_A_0100.flver'):
        assert viewport.resolve_part(tmp_path, None, stem)[0] == 'skip'
    assert viewport.resolve_part(tmp_path, None, 'WP_A_0100') == ('skip', 'no binder')


def test_part_geometry_reads_the_binder_member(tmp_path):
    game = tmp_path / 'game'
    (game / 'parts').mkdir(parents=True)
    (game / 'parts' / 'WP_A_0100.partsbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), stem='WP_A_0100'))
    seen = viewport.part_view(game, None, 'WP_A_0100')
    assert seen['available'] and seen['meshes'] == 1 and seen['file'] == 'WP_A_0100.partsbnd.dcx'
    geometry = viewport.part_geometry(game, None, 'WP_A_0100')
    assert len(geometry['meshes']) == 1 and geometry['meshes'][0]['tris'] == 2
    with pytest.raises(FlverError):
        viewport.part_geometry(game, None, 'WP_A_0101')


def test_overlay_parts_file_wins_over_the_game_file(tmp_path):
    game, mod = tmp_path / 'game', tmp_path / 'mod'
    (game / 'parts').mkdir(parents=True)
    (mod / 'parts').mkdir(parents=True)
    blob = make_chrbnd(build_flver(), stem='BD_M_0100')
    (game / 'parts' / 'BD_M_0100.partsbnd.dcx').write_bytes(blob)
    (mod / 'parts' / 'BD_M_0100.partsbnd.dcx').write_bytes(blob)
    kind, location, member = viewport.resolve_part(game, mod, 'BD_M_0100')
    assert kind == 'member' and Path(location).parent.parent == mod
    assert member == 'BD_M_0100.flver'
    assert viewport.part_view(game, mod, 'BD_M_0100')['available']


def test_part_member_falls_back_to_the_first_mesh(tmp_path):
    game = tmp_path / 'game'
    (game / 'parts').mkdir(parents=True)
    (game / 'parts' / 'WP_A_0100.partsbnd.dcx').write_bytes(
        make_chrbnd(build_flver(), stem='other'))
    kind, _location, member = viewport.resolve_part(game, None, 'WP_A_0100')
    assert kind == 'member' and member == 'other.flver'
    assert viewport.part_geometry(game, None, 'WP_A_0100')['meshes'][0]['tris'] == 2
