"""Downloaded animation records preserve unrelated installed animation data."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import pytest

from plugins.ds1 import tae_merge,record_edits,formats,texts,runtime_mods,standalone_runtime,composition_cache
from plugins.ds1.tae import TaeDocument,TaeError
from test_ds1_tae_record_merge import variants,added
from test_ds1_folder_mods import vanilla
from tae_fixture import build_anibnd

BINDER=Path('chr/c1200.anibnd.dcx')


def binder(tae,other=b'original skeleton',extra=False):
    source=build_anibnd({'a87.tae':tae,'skeleton.hkx':other})
    plain=formats.inflate(source)
    entries=[replace(entry,member_id=87 if entry.name.endswith('.tae') else 100000)
             for entry in texts.bnd3_entries(plain)]
    if extra:
        entries.append(replace(entries[0],member_id=88,name='a88.tae'))
    return formats.deflate(source,texts.build_bnd3(plain,entries))


def member(payload,name='a87.tae'):
    return next(entry.data for entry in texts.bnd3_entries(formats.inflate(payload))
                if entry.name.replace('\\','/').rsplit('/',1)[-1]==name)


def test_sparse_animation_rebase_preserves_foreign_records_additions_and_opaque_events():
    base,a,b=variants()
    foreign,_=tae_merge.compose(base,[('foreign',b),('extra',added(base,key=3500))])
    spec=tae_merge.create_edits(base,a)
    combined=tae_merge.apply_edits(foreign,spec)
    expected=tae_merge._records(foreign)[1] | {3300:tae_merge._records(a)[1][3300]}
    assert tae_merge._records(combined)[1]==expected
    assert tae_merge.apply_edits(combined,spec)==combined


def test_conflicting_installed_animation_and_added_id_are_not_silently_replaced():
    base,a,_b=variants()
    foreign=TaeDocument(base);foreign.edit(0,0,'judge',456)
    with pytest.raises(TaeError,match='3300.*conflicts'):
        tae_merge.apply_edits(foreign.export(),tae_merge.create_edits(base,a))
    with pytest.raises(TaeError,match='3400.*conflicts'):
        tae_merge.apply_edits(added(base,18),tae_merge.create_edits(base,added(base,17)))


def test_portable_rows_cannot_duplicate_or_select_missing_animations():
    base,a,_b=variants();spec=tae_merge.create_edits(base,a)
    invalid=deepcopy(spec);invalid['rows']*=2
    with pytest.raises(TaeError,match='Invalid portable animation record'):
        tae_merge.apply_edits(base,invalid)
    invalid=deepcopy(spec);invalid['rows'][0]['id']=999999
    with pytest.raises(TaeError,match='Invalid portable animation record'):
        tae_merge.apply_edits(base,invalid)


def test_character_binder_rebase_preserves_foreign_members_and_native_id_order():
    base,a,b=variants()
    original=binder(base)
    changed=binder(a,extra=True)
    foreign=binder(b,b'foreign skeleton')
    spec=record_edits.create(BINDER,original,changed)
    assert spec['members'][0]['after']['kind']=='tae'
    changes=record_edits.describe({BINDER:spec})
    assert any(row['id']==3300 and row['label']=='Animation 3300' and not row['added'] for row in changes)
    result=record_edits.materialize(BINDER,foreign,spec)
    assert member(result,'skeleton.hkx')==b'foreign skeleton'
    assert [entry.member_id for entry in texts.bnd3_entries(formats.inflate(result))]==[87,88,100000]
    assert tae_merge._records(member(result))[1]==tae_merge._records(a)[1] | {3301:tae_merge._records(b)[1][3301]}


def test_descriptor_changes_keep_a_whole_member_anchor_instead_of_losing_foreign_edits():
    import struct
    base,_a,b=variants()
    document=TaeDocument(base)
    data=bytearray(base)
    descriptor=struct.unpack_from('<I',data,document.anims[0]['offset']+24)[0]
    struct.pack_into('<I',data,descriptor+20,456)
    changed=bytes(data)
    spec=record_edits.create(BINDER,binder(base),binder(changed))
    assert spec['members'][0]['after']['kind']=='bytes'
    assert member(record_edits.materialize(BINDER,binder(base),spec))==changed
    with pytest.raises(ValueError,match='anchor conflicts'):
        record_edits.materialize(BINDER,binder(b),spec)


def test_export_to_standalone_preserves_foreign_animation_and_isolates_bad_sibling(vanilla,tmp_path,monkeypatch):
    monkeypatch.setattr(composition_cache,'user_root',lambda:tmp_path/'cache')
    base,a,b=variants()
    author,game=tmp_path/'author',tmp_path/'game'
    for root,payload in ((author,binder(base)),(game,binder(b,b'foreign skeleton'))):
        (root/BINDER).parent.mkdir(parents=True)
        (root/BINDER).write_bytes(payload)
    library=game/'mods'
    for name,payload in [('first',a),('broken',b)]:
        folder=tmp_path/'sources'/name
        (folder/BINDER).parent.mkdir(parents=True)
        (folder/BINDER).write_bytes(binder(payload))
        (folder/'mod.json').write_text(json.dumps({'id':name,'name':name}))
        release=runtime_mods.write_release(folder,library,vanilla,game_root=author)
        assert not (release/BINDER).exists()
    # The second mod conflicts with an existing independent change to3301.
    foreign=TaeDocument(member((game/BINDER).read_bytes()))
    foreign.edit(1,0,'effect',99)
    (game/BINDER).write_bytes(binder(foreign.export(),b'foreign skeleton'))
    report=standalone_runtime._run(game,[library],lambda:None)
    assert report['loaded']==['first'] and [row['id'] for row in report['disabled']]==['broken']
    combined=(game/BINDER).read_bytes()
    records=tae_merge._records(member(combined))[1]
    assert records[3300]==tae_merge._records(a)[1][3300]
    assert records[3301]==tae_merge._records(foreign.export())[1][3301]
    assert member(combined,'skeleton.hkx')==b'foreign skeleton'


def test_imported_animation_map_and_item_edits_share_one_saved_record_file(tmp_path):
    from plugins.ds1.store import ItemStore,MARKER,RELATIVE
    from plugins.ds1.map_store import MapStore
    from plugins.ds1.tae_store import TaeStore
    from test_ds1_map_merge import MAP,VANILLA as MAP_BASE,ENEMY,edited,value
    from ds1_fixture import make_archive
    base,a,_b=variants();params=make_archive()
    game,project=tmp_path/'game',tmp_path/'project'
    baseline={RELATIVE:params,MAP:MAP_BASE,BINDER:binder(base)}
    for relative,raw in baseline.items():
        (game/relative).parent.mkdir(parents=True,exist_ok=True)
        (game/relative).write_bytes(raw)
    project.mkdir();(project/MARKER).touch()
    (project/record_edits.FILENAME).write_bytes(record_edits.encode({
        MAP:record_edits.create(MAP,MAP_BASE,edited((ENEMY,'posX',10.0))),
        BINDER:record_edits.create(BINDER,binder(base),binder(a))}))
    items=ItemStore(game,project,False);items.get()
    maps=MapStore(game,project,False,items)
    animations=TaeStore(game,project,False,items)
    maps.get(MAP.name).edit(ENEMY,'posX',15.0)
    selected=next(iter(animations.get(BINDER.name)['taes'].values()))
    assert selected.read_event(0,0)['fields'][-1]['value']==123
    selected.edit(0,0,'judge',144)
    items.get().edit('EquipParamGoods',100,'sellValue',17)
    maps.validate_save();animations.validate_save()
    items.save();assert maps.save()['recordsChanged'];assert animations.save()['recordsChanged'];items.load()
    assert items.get().value('EquipParamGoods',100,'sellValue')==17
    assert value(maps.get(MAP.name).export(),ENEMY,'posX')==15.0
    selected=next(iter(animations.get(BINDER.name)['taes'].values()))
    assert selected.read_event(0,0)['fields'][-1]['value']==144
    assert {relative:(game/relative).read_bytes() for relative in baseline}==baseline
    assert not any((project/relative).exists() for relative in baseline)
