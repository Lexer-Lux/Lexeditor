"""Damage and hitbox edits and conservative parameter reference tracing."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ds1_fixture import make_archive
from plugins.ds1.formats import ItemDocument, FormatError, SIZES
from plugins.ds1.attacks import ATTACK_FIELDS, PC_ATTACK_FIELDS
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
    assert impact['behaviors'] == [{'id': 101, 'name': doc.display_name('BehaviorParam', 101)}]
    assert impact['bulletReferences'] == [{'id': 101, 'name': doc.display_name('Bullet', 101)}]
    assert refs.list(120100)['rows'] == []
    assert refs.list(120100)['unresolved'] == ['Behavior 102 → Bullet 102 → Bullet 999999 (missing)']
    assert refs.list(120000,True)['rows'][-1]['route'] == 'Not linked'
    assert doc.read_row('AtkParam_Npc',102)['impact']['variants'] == []
    assert [(r['id'],r['route']) for r in refs.list(251000)['rows']] == [(100,'Direct + projectile'),(101,'Projectile')]
    with pytest.raises(ValueError): refs.list(502)


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


def test_damage_hitbox_and_impact_fields_roundtrip_exact_byte_boundary_and_revert():
    raw = make_archive(); doc = ItemDocument(raw)
    fields = doc.read_row('AtkParam_Npc',100)['fields']
    assert {f['key'] for f in fields} == set(ATTACK_FIELDS)
    assert all(f['editable'] for f in fields)
    assert len(ATTACK_FIELDS) == 35
    assert [f['key'] for f in fields[:9]] == ['atkPhys', 'atkPhysCorrection', 'atkMag', 'atkMagCorrection',
        'atkFire', 'atkFireCorrection', 'atkThun', 'atkThunCorrection', 'atkAttribute']
    assert next(f for f in fields if f['key']=='atkAttribute')['enum'] == {'0':'Standard','1':'Slash','2':'Strike','3':'Thrust','4':'Push'}
    stamina = next(f for f in fields if f['key']=='atkStam')
    assert stamina['label'] == 'Stamina (points)' and stamina['group'] == 'Base damage'
    assert 'blocking victim' in stamina['description']
    effects = [f for f in fields if f['group']=='Effects']
    assert [f['key'] for f in effects] == ['spEffectId0','spEffectId1','spEffectId2','spEffectId3','spEffectId4',
        'disableHitSpEffect']
    assert next(f for f in fields if f['key']=='spEffectId0')['label'] == 'Effect on hit 1'
    assert next(f for f in fields if f['key']=='disableHitSpEffect')['type'] == 'bool'
    source = next(f for f in fields if f['key']=='hitSourceType')
    assert source['type'] == 'enum' and len(source['enum']) == 34
    assert (source['enum']['0'],source['enum']['1'],source['enum']['33']) == ('Weapon','Body','Part 31')
    groups = {f['key']: f['group'] for f in fields}
    assert groups['hit0_Radius'] == 'Hitbox' and groups['knockbackDist'] == 'Impact'
    values = {'atkPhys':123,'atkMag':234,'atkFire':345,'atkThun':456,
              'atkPhysCorrection':150,'atkMagCorrection':250,'atkFireCorrection':350,'atkThunCorrection':450,
              'atkAttribute':3,'atkStam':50,
              'hit0_Radius':2.5,'hit1_Radius':0.5,'hit2_Radius':1.25,'hit3_Radius':3.75,
              'hit0_DmyPoly1':10,'hit1_DmyPoly1':11,'hit2_DmyPoly1':12,'hit3_DmyPoly1':13,
              'hit0_DmyPoly2':20,'hit1_DmyPoly2':21,'hit2_DmyPoly2':22,'hit3_DmyPoly2':23,
              'spEffectId0':-1,'spEffectId1':0,'spEffectId2':1,'spEffectId3':2,'spEffectId4':3,
              'disableHitSpEffect':1,
              'hti0_Priority':0,'hti1_Priority':1,'hti2_Priority':2,'hti3_Priority':3,
              'hitSourceType':1,'knockbackDist':4.5,'hitStopTime':0.25}
    assert set(values) == set(ATTACK_FIELDS)
    originals = {key: doc.value('AtkParam_Npc',100,key) for key in values}
    allowed = set()
    for key,value in values.items():
        doc.edit('AtkParam_Npc',100,key,value)
        start = doc._row('AtkParam_Npc',100)[1]
        field = next(f['spec'] for f in doc.schemas['AtkParam_Npc']['fields'] if f['spec'].key==key)
        allowed.update(range(start+field.offset,start+field.offset+SIZES[field.dtype]))
    reopened = ItemDocument(doc.export())
    assert {i for i,(a,b) in enumerate(zip(doc.original_plain,reopened.plain)) if a!=b} <= allowed
    for key,value in values.items():
        assert reopened.value('AtkParam_Npc',100,key)==value
        doc.edit('AtkParam_Npc',100,key,originals[key])
    assert doc.export()==raw and doc.dirty_count==0


@pytest.mark.parametrize('key,value',[('atkPhys',-1),('atkMag',10000),('atkFire',1.5),('atkThun',float('nan')),('atkAttribute',5),('atkAttribute',-1),('atkPhys','100'),
    ('atkPhysCorrection',-1),('atkMagCorrection',60001),
    ('hti0_Priority',256),('hti0_Priority',-1),('hitSourceType',34),('hitSourceType',-1),
    ('hit0_Radius','wide'),('hit0_DmyPoly1',40000),('hit0_DmyPoly1',-40000),('hit0_DmyPoly1',1.5),
    ('knockbackDist','far'),('hitStopTime',float('inf'))])
def test_field_bounds_and_enum_validation(key,value):
    with pytest.raises(FormatError): ItemDocument(make_archive()).edit('AtkParam_Npc',100,key,value)


def test_other_attack_behavior_projectile_fields_protected():
    doc = ItemDocument(make_archive())
    # Hit type stays protected: its collision-type values are not documented
    # well enough to expose (see attacks.py). Behavior and projectile call
    # targets (refId, atkId_Bullet) are editable; identity, judgement and
    # visual-effect fields stay protected.
    for table,key in [('AtkParam_Npc','hit0_hitType'),('BehaviorParam','variationId'),('BehaviorParam','behaviorJudgeId'),('Bullet','sfxId_Hit'),('Bullet','Material_AttackType')]:
        with pytest.raises(FormatError): doc.edit(table,100,key,1)


def test_safe_project_save_reload_and_vanilla(tmp_path):
    game,mod = tmp_path/'game',tmp_path/'mod'
    (game/RELATIVE).parent.mkdir(parents=True); raw=make_archive(); (game/RELATIVE).write_bytes(raw)
    mod.mkdir(); (mod/MARKER).touch()
    store = ItemStore(game,mod,False)
    for key,value in [('atkPhys',9999),('atkMag',250),('atkFire',300),('atkThun',400),('atkAttribute',2),('hit0_Radius',2.5),('hitSourceType',1)]:
        store.edit('AtkParam_Npc',101,key,value)
    store.save()
    fresh = ItemStore(game,mod,False).get()
    assert fresh.value('AtkParam_Npc',101,'atkPhys')==9999
    assert fresh.value('AtkParam_Npc',101,'atkAttribute')==2
    assert fresh.value('AtkParam_Npc',101,'hit0_Radius')==2.5
    assert fresh.value('AtkParam_Npc',101,'hitSourceType')==1
    assert (game/RELATIVE).read_bytes()==raw
    with pytest.raises(PermissionError): ItemStore(game).edit('AtkParam_Npc',101,'atkPhys',100)


def test_player_attacks_mirror_enemy_keys_except_stamina_with_motion_value_presentation():
    import json
    from plugins.ds1.formats import METADATA
    doc = ItemDocument(make_archive())
    rows = doc.list_rows('player-attacks')
    assert [(r['id'], r['table']) for r in rows] == [(100, 'AtkParam_Pc')] * 1 + [(101, 'AtkParam_Pc'), (102, 'AtkParam_Pc')]
    assert rows[0]['name'] == 'Attack 100'
    expected = json.loads((METADATA / 'row_names' / 'AtkParam_Pc.json').read_text('utf-8-sig'))
    names = {row['ID']: row['Entries'][0] for row in expected['Entries'] if row['Entries']}
    assert rows[1]['name'] == names[101]
    fields = doc.read_row('AtkParam_Pc', 100)['fields']
    assert {f['key'] for f in fields} == set(PC_ATTACK_FIELDS)
    assert set(PC_ATTACK_FIELDS) == set(ATTACK_FIELDS) - {'atkStam'}
    assert all(f['editable'] for f in fields)
    assert [f['key'] for f in fields[:9]] == ['atkPhys', 'atkPhysCorrection', 'atkMag', 'atkMagCorrection',
        'atkFire', 'atkFireCorrection', 'atkThun', 'atkThunCorrection', 'atkAttribute']
    by_key = {f['key']: f for f in fields}
    assert by_key['atkPhys']['label'] == 'Physical (%)'
    assert by_key['atkPhys']['group'] == 'Motion values'
    assert 'motion value' in by_key['atkPhys']['description'] and '100' in by_key['atkPhys']['description']
    assert by_key['atkPhysCorrection']['label'] == 'Physical correction (%)'
    assert by_key['atkPhysCorrection']['group'] == 'Motion values'
    npc = {f['key']: f for f in doc.read_row('AtkParam_Npc', 100)['fields']}
    assert npc['atkPhys']['label'] == 'Physical (points)'
    assert npc['atkPhys']['group'] == 'Base damage'
    assert 'points of health' in npc['atkPhys']['description']
    assert npc['atkPhysCorrection']['label'] == 'Physical correction (%)'
    assert npc['atkPhysCorrection']['group'] == 'Base damage'
    assert 'impact' not in doc.read_row('AtkParam_Pc', 100)


def test_player_attack_edits_roundtrip_and_revert():
    raw = make_archive(); doc = ItemDocument(raw)
    for key, value in [('atkPhys', 123), ('hit0_Radius', 2.5), ('hitSourceType', 1), ('knockbackDist', 4.5)]:
        doc.edit('AtkParam_Pc', 100, key, value)
    reopened = ItemDocument(doc.export())
    for key, value in [('atkPhys', 123), ('hit0_Radius', 2.5), ('hitSourceType', 1), ('knockbackDist', 4.5)]:
        assert reopened.value('AtkParam_Pc', 100, key) == value
    for key, value in [('atkPhys', 0), ('hit0_Radius', 0.0), ('hitSourceType', 0), ('knockbackDist', 0.0)]:
        doc.edit('AtkParam_Pc', 100, key, value)
    assert doc.export() == raw and doc.dirty_count == 0


def test_player_attack_unknown_fields_stay_protected():
    doc = ItemDocument(make_archive())
    for key in ['hit0_hitType']:
        with pytest.raises(FormatError): doc.edit('AtkParam_Pc', 100, key, 1)
