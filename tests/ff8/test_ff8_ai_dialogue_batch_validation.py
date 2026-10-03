"""AI and dialogue rejection never writes an earlier enemy in the same batch."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import enemy_ai, enemy_battle_text, formats, kernel_text
from plugins.ff8.server import create_server
from test_ff8_enemy_ai import dat
from test_ff8_enemy_batch_validation import files, snapshot


@pytest.fixture
def script_files(files):
    root,source,output,_=files
    text=kernel_text.encode('Original')+b'\0';text+=bytes((-len(text))%4)
    raw=bytearray(dat(b'\x0d\x01\x00\x00')[:-4]+text)
    raw[12:16]=len(raw).to_bytes(4,'little')
    for file in source.iterdir():file.write_bytes(raw)
    return root,source,output,bytes(raw)


def operand(identifier=0):
    return dict(id=identifier,script=0,offset=0,operand=0,value=2)


@pytest.mark.parametrize('field',['id','script','offset','operand'])
@pytest.mark.parametrize('value',[False,.5,float('inf'),'1.5'])
def test_ai_identity_scalars_reject_without_writes(script_files,field,value):
    root,_,output,_=script_files;before=snapshot(root);bad=operand(1);bad[field]=value
    with pytest.raises(ValueError,match='integer'):formats.save_enemy_ai([operand(),bad])
    assert snapshot(root)==before and not output.exists()


@pytest.mark.parametrize('field,value',[('id',False),('id',.5),('line',False),('line',.5),
                                      ('text',None),('text','\U0010ffff'),('text','A'*101)])
def test_dialogue_rejects_later_enemy_without_writes(script_files,field,value):
    root,_,output,_=script_files;before=snapshot(root);bad=dict(id=1,line=0,text='Changed');bad[field]=value
    with pytest.raises(ValueError):
        formats.save_enemy_battle_text([dict(id=0,line=0,text='Changed'),bad])
    assert snapshot(root)==before and not output.exists()


def test_invalid_later_ai_document_preserves_existing_outputs(script_files):
    root,source,output,raw=script_files;(output/'battle').mkdir(parents=True)
    for file in source.iterdir():(output/'battle'/file.name).write_bytes(file.read_bytes())
    scripts=enemy_ai.read(raw)['scripts'];bad=deepcopy(scripts)
    bad[0]['instructions'][0]['opcode']=255
    before=snapshot(root)
    with pytest.raises(ValueError):formats.save_enemy_ai([operand()],documents=[dict(id=1,scripts=bad)])
    assert snapshot(root)==before
    with pytest.raises(ValueError,match='integer'):
        formats.save_enemy_ai([],documents=[dict(id=.5,scripts=scripts)])
    assert snapshot(root)==before


def test_ai_and_dialogue_valid_saves_reload_and_preserve_other_sections(script_files):
    _,source,output,raw=script_files
    assert formats.save_enemy_ai([operand(),operand(1)])['saved']==2
    for identifier in (0,1):
        target=output/'battle'/f'c0m{identifier:03d}.dat';saved=target.read_bytes()
        parsed=enemy_ai.read(saved)
        assert parsed['scripts'][0]['instructions'][0]['operands'][0]['value']==2
        assert saved[16:20]==b'KEEP'
        assert enemy_battle_text.read(saved)['lines'][0]['text']=='Original'
        assert sum(a!=b for a,b in zip(raw,saved))==1
    assert formats.save_enemy_battle_text([dict(id=i,line=0,text='Changed') for i in (0,1)])['saved']==2
    for identifier in (0,1):
        saved=(output/'battle'/f'c0m{identifier:03d}.dat').read_bytes()
        assert enemy_battle_text.read(saved)['lines'][0]['text']=='Changed'
        assert enemy_ai.read(saved)['scripts'][0]['instructions'][0]['operands'][0]['value']==2
        assert saved[16:20]==b'KEEP'
    assert all(file.read_bytes()==raw for file in source.iterdir())


def test_structured_and_source_ai_documents_reload_without_changing_dialogue(script_files):
    _,source,output,raw=script_files
    scripts=enemy_ai.read(raw)['scripts'];structured=deepcopy(scripts)
    structured[0]['instructions'][0]['operands'][0]['value']=4
    sources=[script['source'] for script in scripts]
    assert 'u8=1' in sources[0]
    sources[0]=sources[0].replace('u8=1','u8=3')
    result=formats.save_enemy_ai([],documents=[dict(id=0,scripts=structured),dict(id=1,sources=sources)])
    assert result['saved']==2
    for identifier,value in ((0,4),(1,3)):
        saved=(output/'battle'/f'c0m{identifier:03d}.dat').read_bytes()
        assert enemy_ai.read(saved)['scripts'][0]['instructions'][0]['operands'][0]['value']==value
        assert enemy_battle_text.read(saved)['lines'][0]['text']=='Original'
        assert saved[16:20]==b'KEEP'
    assert all(file.read_bytes()==raw for file in source.iterdir())


def test_ai_dialogue_http_rejection_and_valid_reload(script_files):
    root,_,output,_=script_files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def request(path,batch):
        return Request(base+path,data=json.dumps({'edits':batch}).encode(),headers={'Content-Type':'application/json'})
    try:
        for path,valid,bad in [('/api/enemy-ai/save',operand(),dict(operand(1),offset=.5)),
                               ('/api/enemy-battle-text/save',dict(id=0,line=0,text='Changed'),dict(id=1,line=.5,text='Changed'))]:
            before=snapshot(root)
            with pytest.raises(HTTPError) as failure:urlopen(request(path,[valid,bad]),timeout=5)
            assert failure.value.code==400;failure.value.close();assert snapshot(root)==before
            with urlopen(request(path,[valid]),timeout=5) as response:assert json.load(response)['saved']==1
        saved=(output/'battle'/'c0m000.dat').read_bytes()
        assert enemy_ai.read(saved)['scripts'][0]['instructions'][0]['operands'][0]['value']==2
        assert enemy_battle_text.read(saved)['lines'][0]['text']=='Changed'
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
