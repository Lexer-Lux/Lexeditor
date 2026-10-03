"""Dispatch and incident edits validate and commit together without cache leakage."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

FIRST={'group':'','field':'ParoleDuration','value':'9010.25'}
SECOND={'group':s.WANTED_INCIDENT_GROUP,'field':'TimeEvadingForEscape','value':'80.5'}
THIRD={'group':'LawSpawnDelayMin','field':'WantedLevel1','value':'1.75'}
BAD=[None,{},False,'',[None],[{}],[dict(SECOND,opaque=1)],
     [dict(SECOND,group=[])],[dict(SECOND,field=[])],[dict(SECOND,field='../Opaque')],
     [dict(SECOND,group='UNKNOWN')],[dict(SECOND,field='Unknown')],[FIRST,FIRST]]
BAD += [[dict(SECOND,value=v)] for v in [None,True,[],{},'',float('nan'),float('inf'),10**400]]


@pytest.fixture
def dispatch(fixture):
    root,_=fixture
    files={s.DISPATCH_FILE:'<Root><!--keep--><ParoleDuration value="9000"/><LawSpawnDelayMin><WantedLevel1 value="1"/></LawSpawnDelayMin><Opaque value="keep"/></Root>',
           s.INCIDENTS_FILE:'<Root><Tunables><Item><Name>Other</Name><Evasion><TimeEvadingForEscape value="999"/></Evasion></Item><Item><Name>CBountyIncident</Name><Evasion><TimeEvadingForEscape value="75"/><Opaque value="keep"/></Evasion></Item></Tunables></Root>'}
    for name,text in files.items():
        path=s.data_file_path(name,'mine');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        s.load_file(name)
    return root


@pytest.mark.parametrize('bad',BAD)
@pytest.mark.parametrize('backups',[False,True])
def test_invalid_later_dispatch_preserves_files_and_cached_roots(dispatch,bad,backups):
    if backups:
        for name in [s.DISPATCH_FILE,s.INCIDENTS_FILE]:s.data_file_path(name,'mine').with_suffix('.meta.bak').write_bytes(b'original')
    before=snapshot(dispatch)
    roots={name:s.load_file(name)['root'] for name in [s.DISPATCH_FILE,s.INCIDENTS_FILE]}
    with pytest.raises(ValueError):s.apply_dispatch_edits([FIRST,*bad] if isinstance(bad,list) else bad)
    assert snapshot(dispatch)==before
    assert all(s.load_file(name)['root'] is root for name,root in roots.items())


def test_http_save_reload_both_sources_and_unknown_data(dispatch):
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    def post(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/dispatch/save',data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(dispatch)
        with pytest.raises(HTTPError) as error:urlopen(post([FIRST,dict(SECOND,value=True)]))
        assert error.value.code==400;assert snapshot(dispatch)==before
        assert json.load(urlopen(post([FIRST,SECOND,THIRD])))['saved']==3
        s._files.clear()
        values={(r['group'],r['field']):r['value'] for r in s.get_dispatch()['rows']}
        assert values['','ParoleDuration']=='9010.25'
        assert values[s.WANTED_INCIDENT_GROUP,'TimeEvadingForEscape']=='80.5'
        assert values['LawSpawnDelayMin','WantedLevel1']=='1.75'
        assert b'<!--keep-->' in s.data_file_path(s.DISPATCH_FILE,'mine').read_bytes()
        for name in [s.DISPATCH_FILE,s.INCIDENTS_FILE]:
            assert s.load_file(name)['root'].find('.//Opaque').get('value')=='keep'
        assert s.load_file(s.INCIDENTS_FILE)['root'].find('.//Item/Evasion/TimeEvadingForEscape').get('value')=='999'
    finally:http.shutdown();http.server_close();worker.join()


@pytest.mark.parametrize('backups,fail_at',[(False,1),(False,2),(False,3),(False,4),(True,1),(True,2)])
def test_replacement_failure_restores_both_files_and_caches(dispatch,monkeypatch,backups,fail_at):
    if backups:
        for name in [s.DISPATCH_FILE,s.INCIDENTS_FILE]:s.data_file_path(name,'mine').with_suffix('.meta.bak').write_bytes(b'original')
    before=snapshot(dispatch);replace=s.os.replace;count=0
    roots={name:s.load_file(name)['root'] for name in [s.DISPATCH_FILE,s.INCIDENTS_FILE]}
    def fail(src,dst):
        nonlocal count
        count+=1
        if count==fail_at:raise OSError('injected disk failure')
        return replace(src,dst)
    monkeypatch.setattr(s.os,'replace',fail)
    with pytest.raises(OSError):s.apply_dispatch_edits([FIRST,SECOND])
    assert snapshot(dispatch)==before
    assert all(s.load_file(name)['root'] is root for name,root in roots.items())


@pytest.mark.parametrize('fragment', ['<ParoleDuration value="1"/>','<LawSpawnDelayMin><WantedLevel1 value="2"/></LawSpawnDelayMin>'])
def test_ambiguous_source_identity_rejects_before_other_edits(dispatch,fragment):
    import xml.etree.ElementTree as ET
    doc=s.load_file(s.DISPATCH_FILE)['root'];doc.append(ET.fromstring(fragment));s.save_file(s.DISPATCH_FILE)
    before=snapshot(dispatch)
    target=FIRST if 'ParoleDuration' in fragment else THIRD
    rows=[row for row in s.get_dispatch()['rows'] if (row['group'],row['field'])==(target['group'],target['field'])]
    assert rows and all(row['readonly'] for row in rows)
    with pytest.raises(ValueError,match='ambiguous'):s.apply_dispatch_edits([SECOND,FIRST if 'ParoleDuration' in fragment else THIRD])
    assert snapshot(dispatch)==before


def test_unmodeled_target_and_nonfinite_source_are_protected(dispatch):
    doc=s.load_file(s.DISPATCH_FILE)['root']
    doc.find('ParoleDuration').set('value','NaN');s.save_file(s.DISPATCH_FILE)
    before=snapshot(dispatch)
    assert next(row for row in s.get_dispatch()['rows'] if row['field']=='ParoleDuration')['readonly']
    for edit in [FIRST,dict(FIRST,field='Opaque')]:
        with pytest.raises(ValueError):s.apply_dispatch_edits([SECOND,edit])
        assert snapshot(dispatch)==before


def test_readonly_and_empty_batch(dispatch,monkeypatch):
    before=snapshot(dispatch);s.DATASETS['mine']['readonly']=True
    assert s.apply_dispatch_edits([])==0
    with pytest.raises(ValueError,match='read-only'):s.apply_dispatch_edits([FIRST])
    assert snapshot(dispatch)==before
