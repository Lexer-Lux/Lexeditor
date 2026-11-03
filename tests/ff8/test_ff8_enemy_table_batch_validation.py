"""All nine enemy-table families reject scalar coercion before batch writes."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import enemy_tables, formats
from plugins.ff8.server import create_server
from test_ff8_enemy_batch_validation import files, snapshot


def edits():
    return {
        'ability':dict(id=0,kind='ability',tier='low',slot=0,type=0,animation=255,abilityId=0),
        'draw':dict(id=0,kind='draw',tier='low',slot=0,valueId=0,quantity=255),
        'mug':dict(id=0,kind='mug',tier='low',slot=0,valueId=1,quantity=255),
        'drop':dict(id=0,kind='drop',tier='low',slot=0,valueId=1,quantity=255),
        'card':dict(id=0,kind='card',slot=0,cardId=0),
        'devour':dict(id=0,kind='devour',slot=0,devourId=0),
        'renzokuken':dict(id=0,kind='renzokuken',slot=0,value=65535),
        'elementDefence':dict(id=0,kind='elementDefence',slot=0,stored=255),
        'statusDefence':dict(id=0,kind='statusDefence',slot=0,stored=255),
    }


@pytest.fixture
def table_files(files):
    root,source,output,scan_path=files
    for file in source.iterdir():
        raw=bytearray(file.read_bytes())+bytearray([0xA5])*128
        raw[8:12]=(len(raw)-32).to_bytes(4,'little');raw[12:16]=len(raw).to_bytes(4,'little')
        file.write_bytes(raw)
    return root,source,output


CASES=[(kind,field) for kind,edit in edits().items() for field in edit if field not in ('kind','tier')]


@pytest.mark.parametrize('kind,field',CASES)
@pytest.mark.parametrize('value',[True,.5,float('inf'),'1.5'])
def test_enemy_table_scalars_preserve_batch_after_prior_enemy(table_files,kind,field,value):
    root,_,output=table_files;before=snapshot(root);bad=deepcopy(edits()[kind]);bad['id']=1;bad[field]=value
    with pytest.raises(ValueError,match='integer'):
        formats.save_enemy_tables([edits()['renzokuken'],bad])
    assert snapshot(root)==before
    assert not output.exists()


def test_unknown_later_table_preserves_existing_mod_outputs(table_files):
    root,source,output=table_files;(output/'battle').mkdir(parents=True)
    for file in source.iterdir():(output/'battle'/file.name).write_bytes(file.read_bytes())
    before=snapshot(root)
    with pytest.raises(ValueError):
        formats.save_enemy_tables([edits()['renzokuken'],dict(id=1,kind='unknown',slot=0)])
    assert snapshot(root)==before


def test_all_enemy_table_families_reload_and_preserve_unknown_bytes(table_files):
    _,source,output=table_files;originals={p.name:p.read_bytes() for p in source.iterdir()}
    batch=list(edits().values());second=dict(edits()['mug'],id=1,quantity=5)
    result=formats.save_enemy_tables(batch+[second]);assert result['saved']==10
    expected=bytearray(originals['c0m000.dat'])
    for offset,data in [(0x34,b'\x00\xff\x00\x00'),(0x104,b'\x00\xff'),
                        (0x11C,b'\x01\xff'),(0x134,b'\x01\xff'),(0xF8,b'\x00'),
                        (0xFB,b'\x00'),(0x150,b'\xff\xff'),(0x160,b'\xff'),(0x168,b'\xff')]:
        expected[64+offset:64+offset+len(data)]=data
    assert (output/'battle'/'c0m000.dat').read_bytes()==bytes(expected)
    expected=bytearray(originals['c0m001.dat']);expected[64+0x11C:64+0x11E]=b'\x01\x05'
    assert (output/'battle'/'c0m001.dat').read_bytes()==bytes(expected)
    tables=enemy_tables.read_tables((output/'battle'/'c0m000.dat').read_bytes(),64)
    assert tables['abilities']['low'][0]['animation']==255
    assert tables['draw']['low'][0]['quantity']==255
    assert tables['renzokuken'][0]['value']==65535
    assert tables['elementDefence'][0]['stored']==tables['statusDefence'][0]['stored']==255
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


def test_enemy_table_http_rejection_and_valid_reload(table_files):
    root,_,output=table_files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_address[1]}/api/enemy-tables/save'
    def request(batch):
        return Request(url,data=json.dumps({'edits':batch}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root);bad=dict(edits()['mug'],id=1,quantity=1.5)
        with pytest.raises(HTTPError) as failure:urlopen(request([edits()['renzokuken'],bad]),timeout=5)
        assert failure.value.code==400;failure.value.close();assert snapshot(root)==before
        with urlopen(request(list(edits().values())),timeout=5) as response:assert json.load(response)['saved']==9
        tables=enemy_tables.read_tables((output/'battle'/'c0m000.dat').read_bytes(),64)
        assert tables['renzokuken'][0]['value']==65535
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
