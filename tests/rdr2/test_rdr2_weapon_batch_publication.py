"""Weapon batches validate ownership and publish XML/backup/loader together."""
import copy
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

XML=b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<Root><!--keep--><Item type="CWeaponInfo"><Name>WEAPON_TEST</Name><Damage value="37"/><Enabled value="false"/><Variants><Item><Name>MODE</Name><AmmoInfo>AMMO_TEST</AmmoInfo><Damage value="10"/><DamageFallOffInfo>CURVE_TEST</DamageFallOffInfo></Item></Variants><Opaque value="2" extra="keep"/></Item><Item type="CAmmoInfo"><Name>AMMO_TEST</Name><Capacity value="6"/></Item><Item type="CDamageFallOffInfo"><Name>CURVE_TEST</Name><Distance value="50"/></Item><Item type="CWeaponInfo"><Name>OTHER</Name><Damage value="1"/></Item><Item type="CAmmoProjectileInfo"><Name>PROJECTILE</Name><ProjectileFlags>Alpha Beta {BITSET,UNKNOWN_BIT_INDEX:7}</ProjectileFlags></Item></Root>'
FIRST={'path':[1],'kind':'attr','value':'41.5'}
LINK={'path':[3,0,2],'kind':'attr','value':'12.3456789','targetType':'CWeaponInfo','targetName':'WEAPON_TEST'}
CURVE={'path':[1],'kind':'attr','value':'123.456789','targetType':'CDamageFallOffInfo','targetName':'CURVE_TEST'}


@pytest.fixture
def weapon(fixture):
    root,_=fixture
    path=s.ds_dir('mine')/s.WEAPONS_FILE
    path.write_bytes(XML)
    vanilla=root/'vanilla';vanilla.mkdir()
    (vanilla/s.WEAPONS_FILE).write_bytes(XML)
    s.DATASETS['vanilla']={'dir':vanilla,'readonly':True}
    install=s.ds_dir('mine')/'install.xml'
    install.write_text('<Install><!--keep mapping--><Resources><Resource><FileReplacement><GamePath>unrelated</GamePath><FilePath>keep</FilePath></FileReplacement></Resource></Resources></Install>')
    entry=s.load_file(s.WEAPONS_FILE)
    return root,path,install,entry


def apply(edits):return s.apply_weapon_edits('weapons','WEAPON_TEST',edits)


BAD=[None,{},False,'',[None],[{}],[dict(FIRST,extra=1)],[dict(FIRST,path=[])],
     [dict(FIRST,path={})],[dict(FIRST,path=[-1])],[dict(FIRST,path=[True])],
     [dict(FIRST,path=[1.5])],[dict(FIRST,path=['1'])],[dict(FIRST,path=[99])],
     [dict(FIRST,kind='text')],[dict(FIRST,path=[0],kind='text',value='WEAPON_TEST')],
     [dict(FIRST,path=[4])],[FIRST],
     [dict(FIRST,targetType=None,targetName=None)],
     [dict(FIRST,targetType='CWeaponInfo')],
     [dict(FIRST,targetType='CWeaponInfo',targetName='OTHER')],
     [dict(FIRST,targetType=[],targetName='WEAPON_TEST')]]
BAD += [[dict(FIRST,value=v)] for v in [None,True,[],{},'', 'NaN','Inf','1_0','1e999']]


@pytest.mark.parametrize('bad',BAD)
@pytest.mark.parametrize('backup',[False,True])
def test_invalid_later_rows_preserve_xml_mapping_backup_and_cache(weapon,bad,backup):
    root,path,_,entry=weapon
    if backup:path.with_suffix(path.suffix+'.bak').write_bytes(b'old backup')
    before=snapshot(root);old_root=entry['root'];old_xml=ET.tostring(old_root)
    with pytest.raises(ValueError):apply([FIRST,*bad] if isinstance(bad,list) else bad)
    assert snapshot(root)==before
    assert entry['root'] is old_root and ET.tostring(old_root)==old_xml


@pytest.mark.parametrize('staging',[False,True])
@pytest.mark.parametrize('backup,position',[(False,1),(False,2),(False,3),(True,1),(True,2)])
def test_each_failure_restores_xml_loader_backup_and_cache(weapon,monkeypatch,backup,staging,position):
    root,path,install,entry=weapon
    if backup:path.with_suffix(path.suffix+'.bak').write_bytes(b'old backup')
    before=snapshot(root);old_root=entry['root'];old_xml=ET.tostring(old_root)
    times={p:p.stat().st_mtime_ns for p in [path,install]}
    obj=s.tempfile if staging else s.os;method='NamedTemporaryFile' if staging else 'replace'
    original=getattr(obj,method);calls=0
    def fail_once(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==position:raise OSError('injected weapon publication failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(obj,method,fail_once)
    with pytest.raises(OSError,match='injected'):apply([FIRST])
    assert snapshot(root)==before
    assert entry['root'] is old_root and ET.tostring(old_root)==old_xml
    assert {p:p.stat().st_mtime_ns for p in times}==times
    assert not list(root.rglob('*.tmp'))
    assert not list(root.rglob('.lexeditor-save-recovery-*'))


@pytest.mark.parametrize('source',['owner','name','name-attributes','name-children','attributes','children','text','nonfinite'])
def test_ambiguous_or_unsupported_sources_cannot_be_saved(weapon,source):
    root,path,_,_=weapon
    doc=s.parse_with_comments(path);owner=doc.findall('Item')[0];node=owner.find('Damage')
    if source=='owner':doc.append(copy.deepcopy(owner))
    elif source=='name':owner.append(copy.deepcopy(owner.find('Name')))
    elif source=='name-attributes':owner.find('Name').set('opaque','keep')
    elif source=='name-children':ET.SubElement(owner.find('Name'),'Opaque')
    elif source=='attributes':node.set('opaque','keep')
    elif source=='children':ET.SubElement(node,'Opaque')
    elif source=='text':node.text='keep'
    else:node.set('value','NaN')
    path.write_bytes(ET.tostring(doc))
    s._files.clear();entry=s.load_file(s.WEAPONS_FILE);old_root=entry['root'];before=snapshot(root)
    with pytest.raises(ValueError):apply([{'path':[2],'kind':'attr','value':True},FIRST])
    assert snapshot(root)==before and entry['root'] is old_root


def test_real_http_rejects_then_primary_and_linked_fields_reload_exactly(weapon):
    root,path,install,entry=weapon
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    def post(section,name,edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/weapons/save',data=json.dumps({'section':section,'name':name,'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:urlopen(post('weapons','WEAPON_TEST',[FIRST,FIRST]),timeout=5)
        assert error.value.code==400 and snapshot(root)==before
        assert json.load(urlopen(post('weapons','WEAPON_TEST',[dict(FIRST,value='9007199254740993'),{'path':[2],'kind':'attr','value':True}]),timeout=5))['saved']==2
        edits=[{'path':[1],'kind':'attr','value':'7'},LINK,CURVE]
        assert json.load(urlopen(post('ammo','AMMO_TEST',edits),timeout=5))['saved']==3
        s._files.clear();doc=s.load_file(s.WEAPONS_FILE)['root']
        records={n.findtext('Name'):n for n in doc.findall('Item')}
        assert records['WEAPON_TEST'].find('Damage').get('value')=='9007199254740993'
        assert records['WEAPON_TEST'].find('Enabled').get('value')=='true'
        assert records['WEAPON_TEST'].find('./Variants/Item/Damage').get('value')==LINK['value']
        assert records['AMMO_TEST'].find('Capacity').get('value')=='7'
        assert records['CURVE_TEST'].find('Distance').get('value')==CURVE['value']
        assert records['OTHER'].find('Damage').get('value')=='1'
        assert records['PROJECTILE'].findtext('ProjectileFlags')=='Alpha Beta {BITSET,UNKNOWN_BIT_INDEX:7}'
        assert path.read_bytes().startswith(b'\xef\xbb\xbf<?xml') and b'<!--keep-->' in path.read_bytes()
        assert path.with_suffix(path.suffix+'.bak').read_bytes()==XML
        assert b'<!--keep mapping-->' in install.read_bytes()
        assert ET.parse(install).findall('.//GamePath')[-1].text==s.WEAPONS_GAME_PATH
    finally:http.shutdown();http.server_close();worker.join()


@pytest.mark.parametrize('loader',['<Install/>','<broken'])
def test_empty_readonly_and_invalid_loader_preserve_every_output(weapon,loader):
    root,_,install,_=weapon;before=snapshot(root)
    assert apply([])==0
    s.DATASETS['mine']['readonly']=True
    with pytest.raises(ValueError,match='read-only'):apply([FIRST])
    assert snapshot(root)==before
    s.DATASETS['mine']['readonly']=False;install.write_text(loader);before=snapshot(root)
    with pytest.raises(ValueError):apply([FIRST])
    assert snapshot(root)==before


@pytest.mark.parametrize('kind',['loader','source','backup'])
def test_external_change_after_preparation_is_not_overwritten(weapon,monkeypatch,kind):
    root,path,install,entry=weapon
    before=snapshot(root);old_root=entry['root']
    target=install if kind=='loader' else path if kind=='source' else path.with_suffix(path.suffix+'.bak')
    external=b'<External>keep</External>';commit=s._commit_file_outputs
    def changed(outputs,label,**kwargs):
        target.write_bytes(external)
        return commit(outputs,label,**kwargs)
    monkeypatch.setattr(s,'_commit_file_outputs',changed)
    with pytest.raises(ValueError,match='changed since preparation'):apply([FIRST])
    before[str(target.relative_to(root))]=external
    assert snapshot(root)==before and entry['root'] is old_root


def test_stale_source_with_preserved_timestamp_is_rejected_before_staging(weapon):
    root,path,_,entry=weapon;old_root=entry['root'];stat=path.stat()
    path.write_bytes(XML.replace(b'value="37"',b'value="38"'))
    s.os.utime(path,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    before=snapshot(root)
    with pytest.raises(ValueError,match='changed since preparation'):apply([FIRST])
    assert snapshot(root)==before and entry['root'] is old_root


def test_ambiguous_linked_curve_owner_rejects_the_complete_ammo_batch(weapon):
    root,path,_,_=weapon
    doc=s.parse_with_comments(path);doc.append(copy.deepcopy(doc.findall('Item')[2]))
    path.write_bytes(ET.tostring(doc));s._files.clear();entry=s.load_file(s.WEAPONS_FILE)
    before=snapshot(root);old_root=entry['root']
    with pytest.raises(ValueError,match='ambiguous'):
        s.apply_weapon_edits('ammo','AMMO_TEST',[LINK,CURVE])
    assert snapshot(root)==before and entry['root'] is old_root


@pytest.mark.parametrize('kind',['variant','curve'])
def test_unresolved_linked_record_types_are_readonly_and_cannot_be_saved(weapon,kind):
    root,path,_,_=weapon;doc=s.parse_with_comments(path)
    target=doc.findall('Item')[0].find('./Variants/Item') if kind=='variant' else doc.findall('Item')[2]
    target.set('type','UNK_MEMBER_0x12345678')
    path.write_bytes(ET.tostring(doc));s._files.clear();before=snapshot(root)
    rows=s._weapon_records(s.load_file(s.WEAPONS_FILE)['root'])['ammo'][0]['fields']
    matches=[row for row in rows if row['path']==(LINK['path'] if kind=='variant' else CURVE['path']) and row.get('linked')]
    assert matches and all(not row['writable'] for row in matches)
    edit=LINK if kind=='variant' else dict(CURVE,targetType='UNK_MEMBER_0x12345678')
    with pytest.raises(ValueError):s.apply_weapon_edits('ammo','AMMO_TEST',[{'path':[1],'kind':'attr','value':'7'},edit])
    assert snapshot(root)==before


@pytest.mark.parametrize('argument,value',[('section',[]),('section',None),('name',{}),('name',True),('source_file',{}),('source_file',False)])
def test_malformed_primary_arguments_preserve_files(weapon,argument,value):
    root,_,_,_=weapon;before=snapshot(root)
    args={'section':'weapons','name':'WEAPON_TEST','edits':[FIRST],'source_file':s.WEAPONS_FILE}
    args[argument]=value
    with pytest.raises(ValueError):s.apply_weapon_edits(**args)
    assert snapshot(root)==before


def test_signed_numeric_source_and_values_use_the_numeric_validator(weapon):
    root,path,_,_=weapon;doc=s.parse_with_comments(path);doc.find('./Item/Damage').set('value','+37')
    path.write_bytes(ET.tostring(doc));s._files.clear();before=snapshot(root)
    with pytest.raises(ValueError):apply([dict(FIRST,value='not a number')])
    assert snapshot(root)==before
    assert apply([dict(FIRST,value='+41.5')])==1
    assert s.parse_with_comments(path).find('./Item/Damage').get('value')=='+41.5'
