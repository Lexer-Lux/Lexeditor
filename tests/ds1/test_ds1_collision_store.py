"""Map collision edits remain unsaved, undoable, stale-safe and retryable."""
from copy import deepcopy
import json

import pytest

from core import plugin_files
from plugins.ds1 import collision_archive, project_refresh, record_edits
from plugins.ds1.collision_write import CollisionDocument
from plugins.ds1.map_store import MapStore
from plugins.ds1.msb import MAP_DIR
from plugins.ds1.store import MARKER
from test_ds1_collision_write import collision_source, split_fixture
from test_ds1_portable_collisions import HEADER,BODY,write_pair
from msb_fixture import build_msb

MAP = 'm10_00_00_00.msb'


def setup(tmp_path,source,*,raw=False):
    game,project = tmp_path/'game',tmp_path/'project'
    pair = split_fixture(source)
    write_pair(game,pair)
    (game/MAP_DIR).mkdir(parents=True,exist_ok=True)
    (game/MAP_DIR/MAP).write_bytes(build_msb())
    project.mkdir()
    (project/MARKER).write_text(json.dumps({'name':'Collision test'}))
    if raw:
        write_pair(project,pair)
    return game,project,MapStore(game,project,False),pair


def table(store):
    return store.collisions.table(MAP,'h0000','high',0)


def mesh(store):
    return store.collisions.mesh(MAP,'h0000','high',0)[-1]


def test_collision_fields_do_not_compile_or_write_until_save(collision_source,tmp_path,monkeypatch):
    game,project,store,pair = setup(tmp_path,collision_source)
    before = deepcopy(mesh(store))

    def forbidden(*args,**kwargs):
        raise AssertionError('Editing geometry must not compile physics')

    monkeypatch.setattr(CollisionDocument,'export',forbidden)
    assert store.collisions.edit(table(store),'vertices',0,0,2) == 2
    assert store.dirty_count == 1 and store.pending_changes()
    store.collisions.edit(table(store),'vertices',0,0,0)
    assert store.dirty_count == 0
    after = deepcopy(before)
    after['vertices'].append([0,2,0,0])
    after['flags'].append([17])
    after['faces'].append([3,1,2,555])
    store.collisions.replace_mesh(table(store),after)
    assert store.dirty_count > 0
    store.collisions.replace_mesh(table(store),before)
    assert store.dirty_count == 0
    assert (game/HEADER).read_bytes() == pair[0] and (game/BODY).read_bytes() == pair[1]
    assert not (project/record_edits.FILENAME).exists()


def test_collision_save_uses_portable_records_and_reloads(collision_source,tmp_path):
    game,project,store,pair = setup(tmp_path,collision_source)
    store.collisions.edit(table(store),'vertices',0,1,5)
    saved = store.save()
    assert saved['recordsChanged'] and store.dirty_count == 0
    assert not (project/HEADER).exists() and not (project/BODY).exists()
    assert HEADER in record_edits.project_specs(project)
    reopened = MapStore(game,project,False)
    assert mesh(reopened)['vertices'][0] == [0,5,0,0]
    assert reopened.collisions.mesh(MAP,'h0000','high',0)[3]['vanilla'][0]['vertices'][0] == [0,0,0,0]
    assert (game/HEADER).read_bytes() == pair[0] and (game/BODY).read_bytes() == pair[1]
    reopened.collisions.edit(table(reopened),'vertices',0,1,7)
    reopened.discard()
    assert mesh(reopened)['vertices'][0][1] == 5 and reopened.dirty_count == 0


def test_opening_editing_and_saving_portable_geometry_never_recompiles_physics(collision_source,tmp_path,monkeypatch):
    game,project,store,_pair = setup(tmp_path,collision_source)
    store.collisions.edit(table(store),'vertices',0,0,2)
    # Keep a contribution in a member the next session never opens.
    other = store.collisions.table(MAP,'h0001','high',0)
    store.collisions.edit(other,'vertices',0,1,7)
    store.save()

    def forbidden(*args,**kwargs):
        raise AssertionError('Authoring portable geometry must not compile physics')

    monkeypatch.setattr(CollisionDocument,'export',forbidden)
    reopened = MapStore(game,project,False)
    assert mesh(reopened)['vertices'][0][0] == 2
    reopened.collisions.edit(table(reopened),'vertices',0,1,5)
    reopened.save()
    again = MapStore(game,project,False)
    assert mesh(again)['vertices'][0][:3] == [2,5,0]
    assert again.collisions.mesh(MAP,'h0001','high',0)[-1]['vertices'][0][1] == 7


@pytest.mark.parametrize('raw',[False,True])
def test_failed_collision_and_map_save_restores_every_file_and_can_retry(collision_source,tmp_path,monkeypatch,raw):
    game,project,store,pair = setup(tmp_path,collision_source,raw=raw)
    store.collisions.edit(table(store),'vertices',0,1,5)
    document = store.get(MAP)
    document.edit((2,0),'posX',10.)
    original = plugin_files.atomic_write
    calls = 0

    def failing(path,data):
        nonlocal calls
        calls += 1
        original(path,data)
        if calls == 2:
            raise OSError('injected post-write failure')

    monkeypatch.setattr(plugin_files,'atomic_write',failing)
    with pytest.raises(OSError,match='injected'):
        store.save()
    assert store.dirty_count > 0 and mesh(store)['vertices'][0][1] == 5
    assert not (project/MAP_DIR/MAP).exists()
    assert not (project/record_edits.FILENAME).exists()
    if raw:
        assert (project/HEADER).read_bytes() == pair[0] and (project/BODY).read_bytes() == pair[1]
    monkeypatch.setattr(plugin_files,'atomic_write',original)
    store.save()
    assert store.dirty_count == 0 and mesh(store)['vertices'][0][1] == 5
    assert (game/HEADER).read_bytes() == pair[0] and (game/BODY).read_bytes() == pair[1]


def test_foreign_collision_file_change_retains_unsaved_geometry(collision_source,tmp_path):
    _game,project,store,pair = setup(tmp_path,collision_source,raw=True)
    store.collisions.edit(table(store),'vertices',0,0,2)
    (project/BODY).write_bytes(b'foreign')
    with pytest.raises(ValueError,match='changed externally'):
        store.save()
    assert store.dirty_count == 1 and mesh(store)['vertices'][0][0] == 2
    assert (project/BODY).read_bytes() == b'foreign'
    assert (project/HEADER).read_bytes() == pair[0]


def test_readonly_collision_and_invalid_field_keep_good_mesh(collision_source,tmp_path):
    game,project,store,pair = setup(tmp_path,collision_source)
    before = deepcopy(mesh(store))
    with pytest.raises(ValueError):
        store.collisions.edit(table(store),'faces',0,0,999)
    with pytest.raises(ValueError):
        store.collisions.replace_mesh(table(store),{'vertices':[],'faces':[],'flags':[]})
    invalid = deepcopy(before)
    invalid['vertices'][0][0] = 1e40
    with pytest.raises(ValueError):
        store.collisions.replace_mesh(table(store),invalid)
    assert mesh(store) == before and store.dirty_count == 0
    readonly = MapStore(game,project,True)
    with pytest.raises(PermissionError):
        readonly.collisions.edit(table(readonly),'vertices',0,0,2)
    assert (game/BODY).read_bytes() == pair[1]


def test_external_collision_refresh_is_atomic_and_defers_for_unsaved_edits(collision_source,tmp_path):
    from test_ds1_project_refresh import stores
    old = stores(tmp_path)
    game,project = old[0].game_root,old[0].project
    pair = split_fixture(collision_source)
    write_pair(game,pair)
    write_pair(project,pair)
    assert mesh(old[2])['vertices'][0][0] == 0
    archive = collision_archive.CollisionArchive(*pair)
    changed = CollisionDocument(collision_source).export({0:{'vertices':[[3,0,0],[1,0,0],[0,0,1]]}})
    write_pair(project,archive.replace({'h0000a10':changed}))
    fresh = project_refresh.refresh(*old,paths=[BODY.as_posix(),HEADER.as_posix()])
    assert mesh(fresh[2])['vertices'][0][0] == 3
    assert mesh(old[2])['vertices'][0][0] == 0
    fresh[2].collisions.edit(table(fresh[2]),'vertices',0,0,4)
    write_pair(project,pair)
    assert project_refresh.refresh(*fresh) is None
    assert mesh(fresh[2])['vertices'][0][0] == 4
