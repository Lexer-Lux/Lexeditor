"""Loose collision authoring and release use the shared archive record merger."""
import base64
import json
import struct
from pathlib import Path

import pytest

from core.mod_builds import ModBuildError
from core import plugin_files
from plugins.ds1 import collision_archive,mod_loader,record_edits,runtime_mods,standalone_runtime
from plugins.ds1.collision_write import CollisionDocument
from plugins.ds1.formats import deflate
from plugins.ds1.map_store import MapStore
from test_ds1_collision_store import setup,MAP,table
from test_ds1_collision_write import collision_source
from test_ds1_folder_mods import vanilla
from test_ds1_portable_collisions import HEADER,BODY,write_pair,changed_pair,coordinates
from ds1_fixture import make_archive

LOOSE=HEADER.parent/'h0000.hkx'


def authored(source,x):
    document=CollisionDocument(source)
    vertices=[row[:3] for row in document.meshes[0]['vertices']]
    vertices[0][0]=x
    return document.export({0:{'vertices':vertices}})


def placed(folder,raw):
    (folder/LOOSE).parent.mkdir(parents=True,exist_ok=True)
    (folder/LOOSE).write_bytes(raw)


def test_loose_authoring_save_reload_and_live_preview(collision_source,tmp_path):
    game,project,store,pair=setup(tmp_path,collision_source)
    initial=authored(collision_source,2)
    placed(project,initial)
    view=store.collisions.view(MAP,'h0000','high',0,'vertices')
    assert view['rows'][0]['values']['posX']==2
    assert view['rows'][0]['modified']
    store.collisions.edit_row(table(store),'v:0','posX',3)
    preview=store.model_geometry(MAP,{'type':5,'name':'h0000'})
    assert struct.unpack_from('<f',base64.b64decode(preview['meshes'][0]['positions']))[0]==3
    assert (project/LOOSE).read_bytes()==initial
    store.save()
    assert CollisionDocument((project/LOOSE).read_bytes()).meshes[0]['vertices'][0][0]==3
    assert not (project/record_edits.FILENAME).exists()
    assert MapStore(game,project,False).collisions.read_row(table(store),'v:0')['values']['posX']==3
    assert (game/HEADER).read_bytes()==pair[0] and (game/BODY).read_bytes()==pair[1]


def test_external_loose_change_preserves_dirty_state(collision_source,tmp_path):
    _game,project,store,_pair=setup(tmp_path,collision_source)
    placed(project,collision_source)
    store.collisions.edit_row(table(store),'v:0','posX',3)
    foreign=authored(collision_source,5)
    (project/LOOSE).write_bytes(foreign)
    with pytest.raises(ValueError,match='changed externally'):
        store.save()
    assert store.collisions.read_row(table(store),'v:0')['values']['posX']==3
    assert (project/LOOSE).read_bytes()==foreign


@pytest.mark.parametrize('filename',['h0000a10.hkx','h0000a10.hkx.dcx'])
def test_full_member_names_and_compression_are_editable(collision_source,tmp_path,filename):
    game,project,store,_pair=setup(tmp_path,collision_source)
    relative=LOOSE.with_name(filename)
    raw=deflate(make_archive(),collision_source) if filename.endswith('.dcx') else collision_source
    (project/relative).parent.mkdir(parents=True,exist_ok=True)
    (project/relative).write_bytes(raw)
    store.collisions.edit_row(table(store),'v:0','posX',3)
    store.save()
    saved=(project/relative).read_bytes()
    assert saved.startswith(b'DCX\0')==filename.endswith('.dcx')
    assert CollisionDocument(saved).meshes[0]['vertices'][0][0]==3
    result=mod_loader.compose_installed(game,[mod_loader.Mod('Full name',project,{relative:saved})])
    assert coordinates(tuple(result.files.get(path,original) for path,original in zip((HEADER,BODY),_pair)))==[3,0,0]


def test_duplicate_loose_members_fail_without_editing_another_source(collision_source,tmp_path):
    _game,project,store,_pair=setup(tmp_path,collision_source)
    placed(project,collision_source)
    (project/LOOSE.with_name('h0000a10.hkx')).write_bytes(authored(collision_source,5))
    (project/LOOSE.with_name('l0000.hkx')).write_bytes(collision_source)
    with pytest.raises(ValueError,match='multiple loose collision files'):
        store.collisions.edit_row(table(store),'v:0','posX',3)
    assert store.dirty_count==0
    assert CollisionDocument((project/LOOSE).read_bytes()).meshes[0]['vertices'][0][0]==0
    preview=store.model_geometry(MAP,{'type':5,'name':'h0000'})
    assert [mesh['layer'] for mesh in preview['meshes']]==['collisionLow','collisionLow']
    assert any('multiple loose collision files' in note for note in preview['notes'])


def test_failed_loose_save_rolls_back_and_can_retry(collision_source,tmp_path,monkeypatch):
    _game,project,store,_pair=setup(tmp_path,collision_source)
    placed(project,collision_source)
    store.collisions.edit_row(table(store),'v:0','posX',3)
    original_write=plugin_files.atomic_write
    attempted=[]
    def fail_once(path,data):
        original_write(path,data)
        attempted.append(path)
        if len(attempted)==1:
            raise OSError('injected loose save failure')
    with monkeypatch.context() as scope:
        scope.setattr(plugin_files,'atomic_write',fail_once)
        with pytest.raises(OSError,match='injected loose save failure'):
            store.save()
    assert (project/LOOSE).read_bytes()==collision_source
    assert store.collisions.read_row(table(store),'v:0')['values']['posX']==3
    store.save()
    assert CollisionDocument((project/LOOSE).read_bytes()).meshes[0]['vertices'][0][0]==3


def test_loose_records_combine_with_other_mods_without_preview_compilation(collision_source,tmp_path,monkeypatch):
    game,project,_store,pair=setup(tmp_path,collision_source)
    raw=authored(collision_source,2)
    mod=mod_loader.Mod('Loose',project,{LOOSE:raw})
    with monkeypatch.context() as scope:
        scope.setattr(CollisionDocument,'export',lambda *a,**k:pytest.fail('Normalizing source must not compile physics'))
        normalized=mod_loader.normalize_collisions(game,[mod])[0]
        assert not normalized.files and HEADER in normalized.edits
        assert not mod_loader.compose_installed(game,[mod],conflicts_only=True).files
    other=mod_loader.Mod('Other',tmp_path/'other',dict(zip((HEADER,BODY),changed_pair(pair,y=4))))
    compiled=[]
    original_export=CollisionDocument.export
    def counted(document,updates):
        compiled.append(bool(updates))
        return original_export(document,updates)
    with monkeypatch.context() as scope:
        scope.setattr(CollisionDocument,'export',counted)
        result=mod_loader.compose_installed(game,[mod,other],cache_root=tmp_path/'cache')
    assert compiled==[True]
    output=tuple(result.files.get(path,original) for path,original in zip((HEADER,BODY),pair))
    assert coordinates(output)==[2,4,0]
    assert not result.conflicts and LOOSE not in result.files


def test_broken_loose_mod_is_the_only_failure_owner(collision_source,tmp_path):
    game,project,_store,pair=setup(tmp_path,collision_source)
    bad=mod_loader.Mod('Broken',tmp_path/'broken',{LOOSE:b'broken collision'})
    healthy=mod_loader.Mod('Healthy',project,{LOOSE:authored(collision_source,2)})
    with pytest.raises(ModBuildError) as caught:
        mod_loader.compose_installed(game,[healthy,bad])
    assert tuple(caught.value.folders)==(bad.folder,)
    assert coordinates(tuple(mod_loader.compose_installed(game,[healthy]).files.get(path,original)
                             for path,original in zip((HEADER,BODY),pair)))==[2,0,0]


def test_unknown_loose_destination_is_a_mod_failure(collision_source,tmp_path):
    game,project,_store,_pair=setup(tmp_path,collision_source)
    unknown=Path('map/m99_00_00_00/h0000.hkx')
    bad=mod_loader.Mod('Unknown map',tmp_path/'unknown',{unknown:collision_source})
    healthy=mod_loader.Mod('Healthy',project,{LOOSE:authored(collision_source,2)})
    with pytest.raises(ModBuildError,match='no installed collision archive') as caught:
        mod_loader.compose_installed(game,[healthy,bad])
    assert tuple(caught.value.folders)==(bad.folder,)


def test_loose_and_archive_declarations_cannot_silently_override_each_other(collision_source,tmp_path):
    game,project,_store,pair=setup(tmp_path,collision_source)
    mod=mod_loader.Mod('Duplicate',project,{LOOSE:collision_source,HEADER:pair[0],BODY:pair[1]})
    with pytest.raises(ModBuildError,match='complete raw archive'):
        mod_loader.normalize_collisions(game,[mod])


def test_loose_release_rebases_and_runs_without_loose_asset_or_builder(collision_source,vanilla,tmp_path):
    authored_game,folder,_store,pair=setup(tmp_path,collision_source)
    placed(folder,authored(collision_source,2))
    (folder/'mod.json').write_text(json.dumps({'id':'loose','name':'Loose'}))
    game=tmp_path/'player-game'
    foreign=changed_pair(pair,y=5)
    write_pair(game,foreign)
    library=game/'mods'
    release=runtime_mods.write_release(folder,library,vanilla,game_root=authored_game)
    assert not (release/LOOSE).exists()
    specs=record_edits.decode(record_edits.read(release/record_edits.FILENAME))
    assert HEADER in specs
    (release/'script').mkdir()
    (release/'script/tweak.py').write_text('raise AssertionError("must not execute")')
    report=standalone_runtime._run(game,[library],lambda:None)
    assert report['loaded']==['loose'] and not report['disabled']
    assert coordinates(((game/HEADER).read_bytes(),(game/BODY).read_bytes()))==[2,5,0]
    assert not (game/LOOSE).exists()
