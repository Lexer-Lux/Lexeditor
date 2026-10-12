"""Enemy hitbox data: NPC-to-model links, hit slots, character geometry."""
import base64
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds1_fixture import make_archive
from flver_fixture import build_flver, make_chrbnd
from msb_fixture import build_msb
from plugins.ds1.attacks import body_hitbox, hitbox_slots
from plugins.ds1.flver import FlverError
from plugins.ds1.formats import FormatError, ItemDocument
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR, MsbError
from plugins.ds1.store import MARKER, RELATIVE
from plugins.ds1 import viewport

MAP = 'm10_00_00_00.msb'


def game_with_map(tmp_path, parts=((('enemy', 2, 0, 0, 120000),),)):
    game = tmp_path / 'game'
    (game / MAP_DIR).mkdir(parents=True)
    names = []
    for index, part_list in enumerate(parts):
        name = f'm{index}.msb'
        (game / MAP_DIR / name).write_bytes(build_msb(parts=part_list))
        names.append(name)
    return game


def test_npc_models_links_enemy_to_chr(tmp_path):
    store = MapStore(game_with_map(tmp_path))
    assert store.npc_models() == {120000: ['c1200']}


def test_npc_models_merges_across_maps_and_skips_broken(tmp_path):
    game = game_with_map(tmp_path, parts=((('enemy', 2, 0, 0, 120000),),
                                          (('enemy', 2, 0, 1, 120000), ('enemy', 2, 1, 0, 120100))))
    (game / MAP_DIR / 'broken.msb').write_bytes(b'not a map')
    assert MapStore(game).npc_models() == {120000: ['c1200', 'm10piece'], 120100: ['c1200']}


def test_npc_models_invalidates_on_mutation(tmp_path):
    game = game_with_map(tmp_path)
    mod = tmp_path / 'mod'
    mod.mkdir()
    (mod / MARKER).touch()
    store = MapStore(game, mod, False)
    assert store.npc_models() == {120000: ['c1200']}
    store.remove_placement('m0.msb', '2:0')
    assert store._npc_models is None
    assert store.npc_models() == {}
    store.discard()
    assert store._npc_models is None


def test_hitbox_slots_classify_spheres_capsules_and_idle():
    document = ItemDocument(make_archive())
    document.edit('AtkParam_Npc', 100, 'hit0_Radius', 0.4)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly1', 1)
    document.edit('AtkParam_Npc', 100, 'hit0_DmyPoly2', 11)
    document.edit('AtkParam_Npc', 100, 'hit1_Radius', 0.7)
    document.edit('AtkParam_Npc', 100, 'hit1_DmyPoly1', 3)
    document.edit('AtkParam_Npc', 100, 'hit1_DmyPoly2', -1)
    document.edit('AtkParam_Npc', 100, 'hit3_Radius', 0.5)
    document.edit('AtkParam_Npc', 100, 'hit3_DmyPoly1', -1)
    slots = hitbox_slots(document, 100)
    assert [(slot['active'], slot['shape']) for slot in slots] == [
        (True, 'capsule'), (True, 'sphere'), (False, 'sphere'), (False, 'sphere')]
    assert slots[0]['radius'] == pytest.approx(0.4)
    assert (slots[0]['first'], slots[0]['second']) == (1, 11)
    with pytest.raises(FormatError):
        hitbox_slots(document, 999999)


def test_body_hitbox_reads_npc_dimensions():
    document = ItemDocument(make_archive())
    document.edit('NpcParam', 120000, 'hitRadius', 0.5)
    document.edit('NpcParam', 120000, 'hitHeight', 1.8)
    document.edit('NpcParam', 120000, 'hitYOffset', 0.1)
    assert body_hitbox(document, 120000) == pytest.approx({'radius': 0.5, 'height': 1.8, 'offset': 0.1})


def test_chr_dummies_and_geometry_from_binder(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
    info = viewport.chr_dummies(game, None, 'c1200')
    assert (info['meshes'], info['bones']) == (1, 1)
    assert info['dummies'] == [{'id': 100, 'pos': [1.0, 2.0, 3.0], 'bone': 0}]
    encoded = viewport.chr_geometry(game, None, 'c1200')
    assert len(encoded['meshes']) == 1
    positions = base64.b64decode(encoded['meshes'][0]['positions'])
    assert len(positions) == 4 * 3 * 4
    indices = struct.unpack('<6I', base64.b64decode(encoded['meshes'][0]['indices']))
    assert indices == (0, 1, 2, 0, 2, 3)


def test_chr_missing_and_bad_id(tmp_path):
    game = tmp_path / 'game'
    (game / 'chr').mkdir(parents=True)
    assert viewport.resolve_chr(game, None, 'c9999') == ('skip', 'no binder')
    assert viewport.resolve_chr(game, None, '../param') == ('skip', 'unknown character model')
    assert viewport.resolve_chr(game, None, '') == ('skip', 'unknown character model')
    with pytest.raises(FlverError):
        viewport.chr_geometry(game, None, 'c9999')
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(b'not a binder')
    with pytest.raises(FlverError):
        viewport.chr_dummies(game, None, 'c1200')


def test_chr_prefers_mod_override(tmp_path):
    game = tmp_path / 'game'
    mod = tmp_path / 'mod'
    (game / 'chr').mkdir(parents=True)
    (mod / 'chr').mkdir(parents=True)
    (mod / MARKER).touch()
    (game / 'chr' / 'c1200.chrbnd.dcx').write_bytes(make_chrbnd(build_flver()))
    (mod / 'chr' / 'c1200.chrbnd.dcx').write_bytes(b'not a binder')
    with pytest.raises(FlverError):
        viewport.chr_dummies(game, mod, 'c1200')
