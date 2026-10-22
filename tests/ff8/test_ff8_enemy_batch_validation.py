"""Enemy batches validate all DAT files and Scan text before any writes."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats, paths, scan_text
from plugins.ff8.server import create_server


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'vanilla';source.mkdir();output=tmp_path/'mod'
    raw=bytearray([0xA5])*432
    for offset,value in [(0,2),(4,64),(8,400),(12,432)]:raw[offset:offset+4]=value.to_bytes(4,'little')
    for identifier in (0,1):(source/f'c0m{identifier:03d}.dat').write_bytes(raw)
    def current(filename,dataset='current'):
        candidate=output/'battle'/filename
        return candidate if dataset=='current' and candidate.exists() else source/filename
    scan_path=output/'direct'/'ff8'/'en'/'exe'/'battle_scans.msd'
    monkeypatch.setattr(formats,'_enemy_source_path',current)
    monkeypatch.setattr(formats,'_enemy_output_path',lambda filename:output/'battle'/filename)
    monkeypatch.setattr(paths,'DIRECT_ROOT',output/'direct')
    monkeypatch.setattr(formats,'MONSTERS',[dict(com_id=i,entity_id=i,name=f'Authored enemy {i}') for i in (0,1)])
    monkeypatch.setattr(formats,'_scan_descriptions',lambda dataset:
                        scan_text.read_msd(scan_path) if dataset=='current' and scan_path.exists()
                        else ['Original Scan']*scan_text.SCAN_COUNT)
    return tmp_path,source,output,scan_path


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('field,value',[
    ('id',True),('id',.5),('xp',True),('xp',1.5),('xp',float('inf')),('xp',float('nan')),
    ('flying',0),('flying',1),('flying','false'),('mug_rate',True),
    ('mug_rate',float('inf')),('mug_rate',float('nan')),('scan_description',None),
    ('scan_description',True),('unknown_field',1),('xp',65536),('mug_rate',101)])
def test_rejected_enemy_batches_preserve_all_files(files,field,value):
    root,_,output,_=files;before=snapshot(root)
    bad=dict(id=value if field=='id' else 1,field='xp' if field=='id' else field,
             value=1 if field=='id' else value)
    with pytest.raises(ValueError):formats.save_enemies([dict(id=0,field='xp',value=65535),bad])
    assert snapshot(root)==before
    assert not output.exists()


def test_scan_encoding_failure_preserves_prepared_enemy_output(files):
    root,_,output,_=files;before=snapshot(root)
    with pytest.raises(ValueError):
        formats.save_enemies([dict(id=0,field='xp',value=1),
                             dict(id=1,field='scan_description',value='\U0010ffff')])
    assert snapshot(root)==before
    assert not output.exists()


def test_valid_enemy_and_scan_save_reloads_and_preserves_unknown_bytes(files):
    _,source,output,scan_path=files;originals={p.name:p.read_bytes() for p in source.iterdir()}
    edits=[dict(id=0,field='xp',value=65535),dict(id=0,field='flying',value=True),
           dict(id=0,field='mug_rate',value=12.5),dict(id=1,field='xp',value=1),
           dict(id=0,field='scan_description',value='Authored Scan')]
    result=formats.save_enemies(edits);assert result['saved']==5 and len(result['files'])==3
    expected=bytearray(originals['c0m000.dat'])
    expected[64+0x102:64+0x104]=b'\xff\xff';expected[64+0xF7]|=2;expected[64+0x14C]=32
    assert (output/'battle'/'c0m000.dat').read_bytes()==bytes(expected)
    expected=bytearray(originals['c0m001.dat']);expected[64+0x102:64+0x104]=b'\x01\x00'
    assert (output/'battle'/'c0m001.dat').read_bytes()==bytes(expected)
    rows=formats.enemy_rows()['rows'];fields={f['field']:f['value'] for f in rows[0]['fields']}
    assert fields['xp']==65535 and fields['flying'] is True and fields['mug_rate']==12.5
    assert rows[0]['scanDescription']=='Authored Scan'
    assert scan_text.read_msd(scan_path)[1:]==['Original Scan']*(scan_text.SCAN_COUNT-1)
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


def test_enemy_http_rejects_later_file_before_writes_then_reloads_valid_save(files):
    root,_,_,_=files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_address[1]}/api/enemies/save'
    def request(edits):
        return Request(url,data=json.dumps({'edits':edits}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([dict(id=0,field='xp',value=1),dict(id=1,field='xp',value=1.5)]),timeout=5)
        assert failure.value.code==400;failure.value.close()
        assert snapshot(root)==before
        with urlopen(request([dict(id=0,field='xp',value=65535)]),timeout=5) as response:
            assert json.load(response)['saved']==1
        assert next(f['value'] for f in formats.enemy_rows()['rows'][0]['fields'] if f['field']=='xp')==65535
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
