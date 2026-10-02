"""Damage-only edits and conservative parameter reference tracing."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, FormatError
from plugins.ds1.attacks import ATTACK_FIELDS
from plugins.ds1.store import ItemStore, RELATIVE, MARKER
from plugins.ds3.formats import write_field


def test_direct_projectile_child_and_shared_npc_references():
    doc = ItemDocument(make_archive())
    refs = doc.attack_references()
    rows = refs.list(120000)['rows']
    assert [(r['id'],r['route']) for r in rows] == [(100,'Direct + projectile'),(101,'Projectile')]
    impact = doc.read_row('AtkParam_Npc',101)['impact']
    assert [v['id'] for v in impact['variants']] == [120000,251000]  # Includes excluded friendly NPC.
    assert impact['paths'] == ['Behavior 101 → Bullet 100 → Bullet 101 → Attack 101']
    assert refs.list(120100)['rows'] == []
    assert refs.list(120100)['unresolved'] == ['Behavior 102 → Bullet 102 → Bullet 999999 (missing)']
    assert refs.list(120000,True)['rows'][-1]['route'] == 'Not linked'
    assert doc.read_row('AtkParam_Npc',102)['impact']['variants'] == []
    with pytest.raises(ValueError): refs.list(251000)


def replace(doc, table, row_id, key, value):
    _, start, data = doc._row(table,row_id)
    field = next(f['spec'] for f in doc.schemas[table]['fields'] if f['spec'].key == key)
    doc.plain[start:start+len(data)] = write_field(data,field,value,'<')


def test_cycles_missing_attacks_effects_and_unknown_types_are_explicit():
    doc = ItemDocument(make_archive())
    replace(doc,'Bullet',101,'HitBulletID',100)
    replace(doc,'Bullet',101,'atkId_Bullet',9999)
    result = doc.attack_references().list(120000)
    assert any('(cycle)' in issue for issue in result['unresolved'])
    assert any('Attack 9999 (missing)' in issue for issue in result['unresolved'])
    for kind, expected in [(2,'damage not traced'),(7,'unsupported reference type')]:
        doc = ItemDocument(make_archive())
        replace(doc,'BehaviorParam',100,'refType',kind)
        assert any(expected in issue for issue in doc.attack_references().list(120000)['unresolved'])


def test_five_fields_only_roundtrip_exact_byte_boundary_and_revert():
    raw = make_archive(); doc = ItemDocument(raw)
    fields = doc.read_row('AtkParam_Npc',100)['fields']
    assert {f['key'] for f in fields} == set(ATTACK_FIELDS)
    assert all(f['editable'] for f in fields)
    assert next(f for f in fields if f['key']=='atkAttribute')['enum'] == {'0':'Standard','1':'Slash','2':'Strike','3':'Thrust','4':'Push'}
    allowed = set()
    values = {'atkPhys':123,'atkMag':234,'atkFire':345,'atkThun':456,'atkAttribute':3}
    for key,value in values.items():
        doc.edit('AtkParam_Npc',100,key,value)
        start = doc._row('AtkParam_Npc',100)[1]
        field = next(f['spec'] for f in doc.schemas['AtkParam_Npc']['fields'] if f['spec'].key==key)
        allowed.update(range(start+field.offset,start+field.offset+(1 if key=='atkAttribute' else 2)))
    reopened = ItemDocument(doc.export())
    assert {i for i,(a,b) in enumerate(zip(doc.original_plain,reopened.plain)) if a!=b} <= allowed
    for key,value in values.items():
        assert reopened.value('AtkParam_Npc',100,key)==value
        doc.edit('AtkParam_Npc',100,key,0)
    assert doc.export()==raw and doc.dirty_count==0


@pytest.mark.parametrize('key,value',[('atkPhys',-1),('atkMag',10000),('atkFire',1.5),('atkThun',float('nan')),('atkAttribute',5),('atkAttribute',-1),('atkPhys','100')])
def test_damage_bounds_and_enum_validation(key,value):
    with pytest.raises(FormatError): ItemDocument(make_archive()).edit('AtkParam_Npc',100,key,value)


def test_other_attack_behavior_projectile_fields_protected():
    doc = ItemDocument(make_archive())
    for table,key in [('AtkParam_Npc','atkPhysCorrection'),('AtkParam_Npc','hit0_Radius'),('BehaviorParam','refId'),('Bullet','atkId_Bullet')]:
        with pytest.raises(FormatError): doc.edit(table,100,key,1)


def test_safe_project_save_reload_and_vanilla(tmp_path):
    game,mod = tmp_path/'game',tmp_path/'mod'
    (game/RELATIVE).parent.mkdir(parents=True); raw=make_archive(); (game/RELATIVE).write_bytes(raw)
    mod.mkdir(); (mod/MARKER).touch()
    store = ItemStore(game,mod,False)
    for key,value in [('atkPhys',9999),('atkMag',250),('atkFire',300),('atkThun',400),('atkAttribute',2)]:
        store.edit('AtkParam_Npc',101,key,value)
    store.save()
    fresh = ItemStore(game,mod,False).get()
    assert fresh.value('AtkParam_Npc',101,'atkPhys')==9999
    assert fresh.value('AtkParam_Npc',101,'atkAttribute')==2
    assert (game/RELATIVE).read_bytes()==raw
    with pytest.raises(PermissionError): ItemStore(game).edit('AtkParam_Npc',101,'atkPhys',100)
