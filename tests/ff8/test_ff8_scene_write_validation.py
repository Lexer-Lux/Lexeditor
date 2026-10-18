"""Authored scene records prove rejection before writes and lossless reload."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import encounters, formats
from plugins.ff8.server import create_server


def slot_edit(record=0):
    return dict(id=record,slot=0,enemyId=0,level=100,x=-32768,y=32767,z=0,
                enabled=True,visible=True,loaded=False,targetable=True)


def header_edit(record=0):
    return dict(id=record,stageId=255,flags=0xA5,cameraMain=0xA5,cameraSecondary=0xA5)


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'vanilla'/'scene.out';source.parent.mkdir()
    source.write_bytes(bytes([0xA5])*encounters.RECORD_SIZE*2)
    destination=tmp_path/'mod'/'scene.out'
    monkeypatch.setattr(formats,'source_path',lambda name:source)
    monkeypatch.setattr(formats,'output_path',lambda name:destination)
    monkeypatch.setattr(formats,'MONSTERS',[{'com_id':0,'name':'Authored enemy'}])
    return tmp_path,source,destination


def snapshot(root):
    return {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('field',['id','slot','enemyId','level','x','y','z',
                                  'stageId','flags','cameraMain','cameraSecondary'])
@pytest.mark.parametrize('value',[True,False,.5,float('inf'),float('nan'),'1.5'])
def test_noninteger_encounter_values_preserve_files_after_prior_valid_edit(files,field,value):
    root,_,_=files;before=snapshot(root)
    bad=header_edit(1) if field in header_edit() and field!='id' else slot_edit(1)
    bad[field]=value
    with pytest.raises(ValueError,match='integer'):
        formats.save_encounters([slot_edit(),bad])
    assert snapshot(root)==before
    assert not (root/'mod').exists()


@pytest.mark.parametrize('field',['enabled','visible','loaded','targetable'])
@pytest.mark.parametrize('value',[0,1,'false',None])
def test_encounter_flags_require_booleans(files,field,value):
    root,_,_=files;before=snapshot(root);bad=slot_edit(1);bad[field]=value
    with pytest.raises(ValueError,match='boolean'):
        formats.save_encounters([slot_edit(),bad])
    assert snapshot(root)==before


def test_valid_encounter_edit_reloads_and_preserves_unknown_bytes(files):
    root,source,destination=files;original=source.read_bytes()
    result=formats.save_encounters([header_edit(),slot_edit()])
    assert result['saved']==2
    expected=bytearray(original);expected[0]=255
    expected[4]&=0x7F;expected[5]|=0x80;expected[6]&=0x7F;expected[7]|=0x80
    expected[8:14]=b'\x00\x80\xff\x7f\x00\x00'
    expected[0x38]=encounters.ENEMY_ID_BASE;expected[0x78]=100
    assert destination.read_bytes()==bytes(expected)
    assert source.read_bytes()==original
    row=encounters.read_rows(destination.read_bytes(),{0:'Authored enemy'})['rows'][0]
    assert row['stageId']==255
    slot=row['slots'][0]
    assert all(slot[key]==value for key,value in slot_edit().items() if key!='id')
    assert len(snapshot(root))==2


def test_encounter_http_rejects_batch_and_reloads_valid_save(files):
    root,_,destination=files;before=snapshot(root)
    server=create_server(0);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_address[1]}/api/encounters/save'
    def request(edits):
        return Request(url,data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        for field,value in [('id',.5),('x',True),('level',100.5),('enabled',1)]:
            bad=deepcopy(slot_edit(1));bad[field]=value
            with pytest.raises(HTTPError) as failure:
                urlopen(request([slot_edit(),bad]),timeout=5)
            assert failure.value.code==400
            failure.value.close()
            assert snapshot(root)==before
        with urlopen(request([header_edit(),slot_edit()]),timeout=5) as response:
            assert json.load(response)['saved']==2
        assert encounters.read_rows(destination.read_bytes(),{0:'Authored enemy'})['rows'][0]['slots'][0]['x']==-32768
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
