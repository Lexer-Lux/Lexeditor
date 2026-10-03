"""Mobs batches protect both source copies, caches, backups and loader mappings."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

COMBAT = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<Root><!--keep--><CombatInfos><!--indices--><Item><Name>GANG_FIXTURE</Name><Accuracy value="1"/><Enabled>true</Enabled><Style>A</Style><Style>B</Style><Ref ref="A"/><Ref ref="B"/><Opaque value="1" extra="keep"/></Item></CombatInfos></Root>'
HEALTH = b'<?xml version="1.0" encoding="UTF-8"?>\n<Root><!--keep--><HealthConfig><Item key="FIXTURE"><Energy value="10"/><Opaque value="1"><Child/></Opaque></Item></HealthConfig><Opaque value="3"/></Root>'
FIRST = {'file':'combat','path':[1,1,1],'kind':'attr','value':'0.125'}
SECOND = {'file':'health','path':[1,0,0],'kind':'attr','value':'12.3456789'}


@pytest.fixture
def mobs(fixture, monkeypatch):
    root, _ = fixture
    sources = [root/'vanilla-combat.meta', root/'vanilla-health.meta']
    for path, raw in zip(sources, [COMBAT, HEALTH]):
        path.write_bytes(raw)
    monkeypatch.setattr(s, 'VANILLA_COMBAT_FILE', sources[0])
    monkeypatch.setattr(s, 'VANILLA_PEDHEALTH_FILE', sources[1])
    monkeypatch.setattr(s, 'MOB_FILES', {
        'combat':(s.COMBAT_FILE, s.COMBAT_GAME_PATH, sources[0]),
        'health':(s.PEDHEALTH_FILE, s.PEDHEALTH_GAME_PATH, sources[1]),
    })
    install=s.ds_dir('mine')/'install.xml'
    install.write_text('<Install><!--keep mapping--><Resources><Resource><FileReplacement><GamePath>unrelated</GamePath><FilePath>keep</FilePath></FileReplacement></Resource></Resources></Install>')
    paths=[s.data_file_path(name,'mine') for name in [s.COMBAT_FILE,s.PEDHEALTH_FILE]]
    return root, paths, sources, install


def existing_files(mobs, mask):
    _, paths, sources, _ = mobs
    entries=[]
    for i,(path,source,name) in enumerate(zip(paths,sources,[s.COMBAT_FILE,s.PEDHEALTH_FILE])):
        if mask & (1<<i):
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(source.read_bytes())
            entry=s.load_file(name)
            entries.append((entry,entry['root'],ET.tostring(entry['root']),entry['mtime']))
    return entries


def unchanged_cache(entries):
    for entry, root, raw, mtime in entries:
        assert entry['root'] is root
        assert ET.tostring(root)==raw
        assert entry['mtime']==mtime


BAD=[None, {}, False, '', [None], [{}], [dict(SECOND, extra=1)], [dict(SECOND,file=[])],
     [dict(SECOND,file='unknown')], [dict(SECOND,path=[])], [dict(SECOND,path={})],
     [dict(SECOND,path=[-1])], [dict(SECOND,path=[True])], [dict(SECOND,path=[1.5])],
     [dict(SECOND,path=['1'])], [dict(SECOND,path=[99])], [dict(SECOND,path=[2])],
     [dict(SECOND,path=[1,0,1])], [dict(SECOND,kind='ref')], [FIRST],
     [dict(FIRST,path=[1,1,7])], [dict(FIRST,path=[1,1,2],kind='text',value='maybe')],
     [dict(FIRST,path=[1,1,5],kind='ref',value='invented')]]
BAD += [[dict(SECOND,value=v)] for v in [None,True,[],{},'', 'NaN','Inf','1_0','1e999',float('nan'),float('inf')]]
BAD += [[dict(FIRST,path=[1,1,0],kind='text',value='GANG_FIXTURE')]]


@pytest.mark.parametrize('mask',[0,1,2,3])
@pytest.mark.parametrize('bad',BAD)
def test_invalid_later_edit_preserves_every_file_and_cached_root(mobs,mask,bad):
    entries=existing_files(mobs,mask)
    root,_,_,_=mobs
    before=snapshot(root)
    with pytest.raises(ValueError):
        s.apply_mob_edits([FIRST,*bad] if isinstance(bad,list) else bad)
    assert snapshot(root)==before
    unchanged_cache(entries)


FAILURES=[(mask,position) for mask in [0,1,2,3] for position in range(1,4+mask.bit_count())]
@pytest.mark.parametrize('mask,position',FAILURES)
@pytest.mark.parametrize('staging',[False,True])
def test_each_output_failure_restores_all_outputs_cache_and_timestamps(mobs,monkeypatch,mask,position,staging):
    entries=existing_files(mobs,mask)
    root,paths,_,install=mobs
    before=snapshot(root)
    timestamps={p:p.stat().st_mtime_ns for p in [*paths,install] if p.exists()}
    obj=s.tempfile if staging else s.os
    method='NamedTemporaryFile' if staging else 'replace'
    original=getattr(obj,method)
    calls=0
    def fail_once(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==position:raise OSError('injected mobs failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(obj,method,fail_once)
    with pytest.raises(OSError,match='injected mobs failure'):
        s.apply_mob_edits([FIRST,SECOND])
    assert snapshot(root)==before
    assert {p:p.stat().st_mtime_ns for p in timestamps}==timestamps
    unchanged_cache(entries)
    assert not list(root.rglob('*.tmp'))
    assert not list(root.rglob('.lexeditor-save-recovery-*'))


@pytest.mark.parametrize('mask',[0,1,2,3])
def test_real_http_rejection_then_two_file_exact_reload_and_mapping(mobs,mask):
    entries=existing_files(mobs,mask)
    root,paths,sources,install=mobs
    http=s.create_server(0)
    worker=threading.Thread(target=http.serve_forever,daemon=True)
    worker.start()
    def post(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/mobs/save',data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:
            urlopen(post([FIRST,dict(SECOND,path=[-1])]),timeout=5)
        assert error.value.code==400
        assert snapshot(root)==before
        unchanged_cache(entries)
        edits=[dict(FIRST,value='9007199254740993'),SECOND,
               dict(FIRST,path=[1,1,2],kind='text',value='false'),
               dict(FIRST,path=[1,1,3],kind='text',value='B'),
               dict(FIRST,path=[1,1,4],kind='text',value='A'),
               dict(FIRST,path=[1,1,5],kind='ref',value='B')]
        assert json.load(urlopen(post(edits),timeout=5))['saved']==len(edits)
        s._files.clear()
        records=s.get_mobs()
        fields=records['combat']['records'][0]['fields']
        assert next(f for f in fields if f['field']=='Accuracy')['value']=='9007199254740993'
        assert next(f for f in fields if f['field']=='Enabled')['value']=='false'
        assert [f['value'] for f in fields if f['field']=='Style']==['B','A']
        assert [f['value'] for f in fields if f['field']=='Ref']==['B','B']
        assert records['health']['records'][0]['fields'][0]['value']==SECOND['value']
        mappings=[(n.findtext('GamePath'),n.findtext('FilePath')) for n in ET.parse(install).findall('.//FileReplacement')]
        assert mappings==[('unrelated','keep'),(s.COMBAT_GAME_PATH,s.COMBAT_FILE),(s.PEDHEALTH_GAME_PATH,s.PEDHEALTH_FILE)]
        assert b'<!--keep mapping-->' in install.read_bytes()
        assert paths[0].read_bytes().startswith(b'\xef\xbb\xbf<?xml')
        for i,(path,source,raw) in enumerate(zip(paths,sources,[COMBAT,HEALTH])):
            assert source.read_bytes()==raw
            assert b'<!--keep-->' in path.read_bytes()
            backup=path.with_suffix(path.suffix+'.bak')
            if mask & (1<<i):assert backup.read_bytes()==raw
            else:assert not backup.exists()
    finally:
        http.shutdown();http.server_close();worker.join()


@pytest.mark.parametrize('loader',['<broken','<Install/>'])
def test_empty_readonly_and_invalid_loader_do_not_copy_vanilla(mobs,loader):
    root,paths,_,install=mobs
    before=snapshot(root)
    assert s.apply_mob_edits([])==0
    s.DATASETS['mine']['readonly']=True
    with pytest.raises(ValueError,match='read-only'):s.apply_mob_edits([FIRST,SECOND])
    assert snapshot(root)==before
    s.DATASETS['mine']['readonly']=False
    install.write_text(loader)
    before=snapshot(root)
    with pytest.raises(ValueError):s.apply_mob_edits([FIRST,SECOND])
    assert snapshot(root)==before
    assert not any(path.exists() for path in paths)


@pytest.mark.parametrize('kind',['loader','existing-source','new-source'])
def test_external_change_after_preparation_is_preserved_without_batch_publication(mobs,monkeypatch,kind):
    entries=existing_files(mobs,1 if kind=='existing-source' else 0)
    root,paths,_,install=mobs
    before=snapshot(root)
    target=install if kind=='loader' else paths[0]
    external=b'<External>keep</External>'
    commit=s._commit_file_outputs
    def changed(outputs,label,**kwargs):
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(external)
        return commit(outputs,label,**kwargs)
    monkeypatch.setattr(s,'_commit_file_outputs',changed)
    with pytest.raises(ValueError,match='changed since preparation'):
        s.apply_mob_edits([FIRST,SECOND])
    before[str(target.relative_to(root))]=external
    assert snapshot(root)==before
    unchanged_cache(entries)


def test_existing_backups_and_registered_mappings_remain_unchanged(mobs):
    existing_files(mobs,3)
    _,paths,_,install=mobs
    backups=[]
    for path in paths:
        backup=path.with_suffix(path.suffix+'.bak')
        backup.write_bytes(b'older original backup')
        backups.append(backup)
    s.ensure_file_replacement(s.COMBAT_GAME_PATH,s.COMBAT_FILE)
    s.ensure_file_replacement(s.PEDHEALTH_GAME_PATH,s.PEDHEALTH_FILE)
    loader=install.read_bytes()
    mtime=install.stat().st_mtime_ns
    assert s.apply_mob_edits([FIRST,SECOND])==2
    assert install.read_bytes()==loader
    assert install.stat().st_mtime_ns==mtime
    assert all(backup.read_bytes()==b'older original backup' for backup in backups)


def test_missing_later_vanilla_source_does_not_create_earlier_copy(mobs):
    root,paths,sources,_=mobs
    sources[1].unlink()
    before=snapshot(root)
    with pytest.raises(ValueError,match='extract is missing'):
        s.apply_mob_edits([FIRST,SECOND])
    assert snapshot(root)==before
    assert not any(path.exists() for path in paths)


@pytest.mark.parametrize('mask',[0,1,2,3])
def test_validate_only_checks_complete_batch_and_loader_without_creating_outputs(mobs,mask):
    entries=existing_files(mobs,mask)
    root,_,_,install=mobs
    before=snapshot(root)
    assert s.apply_mob_edits([FIRST,SECOND],validate_only=True)==2
    with pytest.raises(ValueError):
        s.apply_mob_edits([FIRST,dict(SECOND,path=[-1])],validate_only=True)
    assert snapshot(root)==before
    unchanged_cache(entries)
    install.write_text('<Install/>')
    before=snapshot(root)
    with pytest.raises(ValueError,match='Resources'):
        s.apply_mob_edits([FIRST,SECOND],validate_only=True)
    assert snapshot(root)==before
    unchanged_cache(entries)
