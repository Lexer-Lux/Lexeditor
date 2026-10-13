"""Honor control request/source validation precedes publication."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import honor_actions as honor, server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

FIRST={'id':'tier_+5','amount':'-9007199254740993'}
BAD=[None,{},True,'',[None],[{}],[dict(FIRST,extra=1)],[{'id':[]}],
     [{'id':'UNKNOWN','amount':1}],[FIRST],[{'id':'tier_+5'}],
     [{'id':'HONOR_EVENT_THEFT','amount':3}]]
BAD += [[{'id':'tier_+10','amount':value}] for value in [None,True,[],{},'',1.5,'1.5',float('nan'),float('inf')]]
BAD += [[{'id':'HONOR_EVENT_THEFT','enabled':value}] for value in [None,0,1,'true',[],{}]]


@pytest.fixture
def controls(fixture,monkeypatch):
    root,_=fixture
    path=root/'mine'/'honor_actions.csv'
    monkeypatch.setattr(s,'HONOR_ACTIONS_FILE',path)
    return root,path


@pytest.mark.parametrize('bad',BAD)
@pytest.mark.parametrize('existing',[False,True])
def test_invalid_later_edit_preserves_existing_or_absent_output(controls,bad,existing):
    root,path=controls
    if existing:honor.save_honor_actions(path,[{'id':'tier_+5','amount':7}])
    before=snapshot(root)
    with pytest.raises(ValueError):s.save_honor_actions([FIRST,*bad] if isinstance(bad,list) else bad)
    assert snapshot(root)==before


@pytest.mark.parametrize('source',[
    'kind,id,enabled,amount,opaque\nevent,HONOR_EVENT_THEFT,1,,keep\n',
    'kind,id,enabled,amount\nevent,HONOR_EVENT_THEFT,unknown,\n',
    'kind,id,enabled,amount\ntier,tier_+5,1,1.5\n',
    'kind,id,enabled,amount\nevent,tier_+5,1,5\n',
    'kind,id,enabled,amount\nevent,HONOR_EVENT_THEFT,1,3\n',
    'kind,id,enabled,amount\ntier,tier_+5,1,5\ntier,tier_+5,1,6\n',
])
def test_unsupported_stored_controls_are_not_normalized(controls,source):
    root,path=controls;path.write_text(source)
    before=snapshot(root)
    with pytest.raises(ValueError):honor.read_honor_actions(path)
    with pytest.raises(ValueError):s.save_honor_actions([FIRST])
    assert snapshot(root)==before


def test_http_rejects_then_exact_signed_amount_and_boolean_reload(controls):
    root,path=controls
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    def post(edits):return Request(f'http://127.0.0.1:{http.server_port}/api/honor-actions/save',data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:urlopen(post([FIRST,{'id':'tier_+10','amount':1.5}]))
        assert error.value.code==400;assert snapshot(root)==before
        assert json.load(urlopen(post([FIRST,{'id':'HONOR_EVENT_THEFT','enabled':False}])))['saved']==2
        data=honor.read_honor_actions(path)
        assert next(row for row in data['tiers'] if row['id']=='tier_+5')['amount']==-9007199254740993
        assert not next(row for row in data['events'] if row['id']=='HONOR_EVENT_THEFT')['enabled']
        assert len(data['events'])==21 and len(data['tiers'])==19
        api_data=json.load(urlopen(f'http://127.0.0.1:{http.server_port}/api/honor-actions'))
        assert next(row for row in api_data['tiers'] if row['id']=='tier_+5')['amount']=='-9007199254740993'
    finally:http.shutdown();http.server_close();worker.join()


@pytest.mark.parametrize('operation',['stage','replace'])
def test_failed_honor_publication_preserves_existing_output(controls,monkeypatch,operation):
    root,path=controls;honor.save_honor_actions(path,[{'id':'tier_+5','amount':7}])
    before=snapshot(root)
    def fail(*args,**kwargs):raise OSError('Injected honor save failure')
    monkeypatch.setattr(s.tempfile if operation=='stage' else s.os,'NamedTemporaryFile' if operation=='stage' else 'replace',fail)
    with pytest.raises(OSError,match='Injected honor'):s.save_honor_actions([FIRST])
    assert snapshot(root)==before


def test_empty_and_readonly_do_not_create_a_control_file(controls):
    root,path=controls;before=snapshot(root)
    s.DATASETS['mine']['readonly']=True
    assert s.save_honor_actions([])==0
    with pytest.raises(ValueError,match='read-only'):s.save_honor_actions([FIRST])
    assert snapshot(root)==before and not path.exists()
