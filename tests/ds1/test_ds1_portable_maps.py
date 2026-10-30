"""Map releases preserve unrelated installed fields instead of reverting them."""
import json
from pathlib import Path
import pytest

from plugins.ds1 import record_edits,mod_loader,runtime_mods,standalone_runtime
from plugins.ds1.msb import MsbDocument
from test_ds1_map_merge import MAP,VANILLA,ENEMY,PLAYER,edited,value
from test_ds1_folder_mods import vanilla


def test_portable_map_edits_preserve_foreign_fields_and_compose_two_mods():
    a=record_edits.create(MAP,VANILLA,edited((ENEMY,'posX',10.0)))
    b=record_edits.create(MAP,VANILLA,edited((PLAYER,'posZ',20.0)))
    foreign=edited((ENEMY,'npcId',120100))
    materialized=[mod_loader.Mod(name,Path(name),{MAP:record_edits.materialize(MAP,foreign,spec)})
                  for name,spec in [('a',a),('b',b)]]
    result=mod_loader.compose({MAP:foreign},materialized)
    assert not result.conflicts
    assert value(result.files[MAP],ENEMY,'posX')==10.0
    assert value(result.files[MAP],PLAYER,'posZ')==20.0
    assert value(result.files[MAP],ENEMY,'npcId')==120100
    assert record_edits.materialize(MAP,result.files[MAP],a)==result.files[MAP]


def test_foreign_change_to_the_same_field_is_an_explicit_conflict():
    spec=record_edits.create(MAP,VANILLA,edited((ENEMY,'posX',10.0)))
    with pytest.raises(ValueError,match='Position X.*conflicts'):
        record_edits.materialize(MAP,edited((ENEMY,'posX',3.0)),spec)


def test_portable_map_cannot_write_noneditable_offsets_or_repeat_fields():
    from copy import deepcopy
    spec=record_edits.create(MAP,VANILLA,edited((ENEMY,'posX',10.0)))
    invalid=deepcopy(spec);invalid['fields'][0]['offset']=0
    with pytest.raises(ValueError,match='Invalid portable map field'):
        record_edits.materialize(MAP,VANILLA,invalid)
    invalid=deepcopy(spec);invalid['fields']*=2
    with pytest.raises(ValueError,match='Invalid portable map field'):
        record_edits.materialize(MAP,VANILLA,invalid)


def test_structural_changes_keep_exact_anchor_and_refuse_to_discard_foreign_edits():
    document=MsbDocument(VANILLA,MAP.name)
    document.add_placement(ENEMY)
    changed=document.export()
    spec=record_edits.create(MAP,VANILLA,changed)
    assert record_edits.materialize(MAP,VANILLA,spec)==changed
    assert record_edits.materialize(MAP,changed,spec)==changed
    with pytest.raises(ValueError,match='structural map changes conflict'):
        record_edits.materialize(MAP,edited((PLAYER,'posZ',55.0)),spec)


def test_exported_maps_run_through_standalone_with_foreign_baseline(vanilla,tmp_path):
    game=tmp_path/'game';library=game/'mods'
    (game/MAP).parent.mkdir(parents=True)
    foreign=edited((ENEMY,'npcId',120100))
    (game/MAP).write_bytes(foreign)
    # Authors build against their pristine baseline; install onto a different
    # baseline only after export, exactly as a downloaded release would.
    authored=tmp_path/'author-game'
    (authored/MAP).parent.mkdir(parents=True)
    (authored/MAP).write_bytes(VANILLA)
    for name,change in [('first',(ENEMY,'posX',10.0)),('second',(PLAYER,'posZ',20.0))]:
        folder=tmp_path/'sources'/name
        (folder/MAP).parent.mkdir(parents=True)
        (folder/MAP).write_bytes(edited(change))
        (folder/'mod.json').write_text(json.dumps({'id':name,'name':name}))
        release=runtime_mods.write_release(folder,library,vanilla,game_root=authored)
        assert not (release/MAP).exists()
        assert MAP in record_edits.decode(record_edits.read(release/record_edits.FILENAME))
    broken=library/'broken';broken.mkdir()
    (broken/'mod.json').write_text(json.dumps({'id':'broken','name':'Broken','enabled':True}))
    (broken/'runtime.lxd').write_bytes((library/'first/runtime.lxd').read_bytes())
    (broken/record_edits.FILENAME).write_bytes(record_edits.encode({MAP:record_edits.create(
        MAP,VANILLA,edited((ENEMY,'npcId',120400)))}))
    # Data-only sentinel modules contain no shared native support requiring an
    # executable. The normal writer updates this isolated game fixture only.
    result=standalone_runtime._run(game,[library],lambda:None)
    assert set(result['loaded'])=={'first','second'}
    assert [row['id'] for row in result['disabled']]==['broken']
    assert not json.loads((broken/'mod.json').read_text())['enabled']
    combined=(game/MAP).read_bytes()
    assert value(combined,ENEMY,'posX')==10.0
    assert value(combined,PLAYER,'posZ')==20.0
    assert value(combined,ENEMY,'npcId')==120100


def test_imported_map_and_item_edits_save_into_one_portable_record_file(tmp_path):
    from plugins.ds1.map_store import MapStore
    from plugins.ds1.store import ItemStore,MARKER,RELATIVE
    from plugins.ds1.formats import ItemDocument
    from ds1_fixture import make_archive
    game,project=tmp_path/'game',tmp_path/'project'
    (game/MAP).parent.mkdir(parents=True)
    (game/MAP).write_bytes(VANILLA)
    (game/RELATIVE).parent.mkdir(parents=True)
    params=make_archive();(game/RELATIVE).write_bytes(params)
    document=ItemDocument(params);document.edit('EquipParamGoods',100,'sellValue',12)
    project.mkdir();(project/MARKER).touch()
    (project/record_edits.FILENAME).write_bytes(record_edits.encode({
        MAP:record_edits.create(MAP,VANILLA,edited((ENEMY,'posX',10.0))),
        RELATIVE:record_edits.create(RELATIVE,params,document.export())}))
    items=ItemStore(game,project,False)
    assert items.get().value('EquipParamGoods',100,'sellValue')==12
    maps=MapStore(game,project,False,items)
    assert value(maps.get(MAP.name).export(),ENEMY,'posX')==10.0
    items.get().edit('EquipParamGoods',100,'sellValue',17)
    maps.get(MAP.name).edit(ENEMY,'posX',15.0)
    maps.validate_save()
    items.save()
    assert maps.save()['recordsChanged']
    items.load()
    assert items.get().value('EquipParamGoods',100,'sellValue')==17
    assert value(maps.get(MAP.name).export(),ENEMY,'posX')==15.0
    assert not (project/MAP).exists() and not (project/RELATIVE).exists()
    assert (game/MAP).read_bytes()==VANILLA and (game/RELATIVE).read_bytes()==params
