"""Mixed binary/metadata batches validate completely before either output."""
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

import pytest
from plugins.ff8 import formats, paths, gameplay_settings, gf_spellbooks, reptile_atb
from plugins.ff8.server import create_server


BOOK=dict(id=0,field='__spellbook',value=[[dict(magicId=1,abilityId=None)]])
REPTILE=dict(id=0,field='reptile',value=True)
KERNEL=dict(id=0,field='gf_power',value=42)
ENEMY=dict(id=0,field='xp',value=42)


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir();output=tmp_path/'mod'
    section=formats.SECTIONS[3]
    kernel=bytearray(256)+bytearray([0xA5])*section['number_sub_section']*section['sub_section_size']
    kernel[12:16]=(256).to_bytes(4,'little');(source/'kernel.bin').write_bytes(kernel)
    enemy=bytearray([0xA5])*432
    for offset,value in [(0,2),(4,64),(8,400),(12,432)]:enemy[offset:offset+4]=value.to_bytes(4,'little')
    (source/'c0m000.dat').write_bytes(enemy)
    def current(name,dataset='current'):
        candidate=output/name
        return candidate if dataset=='current' and candidate.exists() else source/name
    monkeypatch.setattr(formats,'source_path',current)
    monkeypatch.setattr(formats,'output_path',lambda name:output/name)
    monkeypatch.setattr(formats,'_enemy_source_path',current)
    monkeypatch.setattr(formats,'_enemy_output_path',lambda name:output/name)
    monkeypatch.setattr(formats,'MONSTERS',[dict(com_id=0,entity_id=0,name='Authored enemy')])
    monkeypatch.setattr(paths,'PROJECT_ROOT',output)
    monkeypatch.setattr(paths,'DIRECT_ROOT',output/'direct')
    monkeypatch.setattr(gameplay_settings,'load',lambda *args,**kwargs:dict(gfSpellbooksEnabled=True,singleGf=True,sharedMagicInventory=False))
    return tmp_path,source,output


def snapshot(root):
    return {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}


def save(kind,edits):
    return formats.save_kernel(3,edits) if kind=='book' else formats.save_enemies(edits)


@pytest.mark.parametrize('kind',['book','reptile'])
@pytest.mark.parametrize('value',[True,False,0.5,float('inf'),float('nan'),'0.5',None,[],{}])
@pytest.mark.parametrize('existing',[False,True])
def test_metadata_identity_never_truncates_or_writes_binary(files,kind,value,existing):
    root,_,_=files
    metadata=BOOK if kind=='book' else REPTILE
    binary=KERNEL if kind=='book' else ENEMY
    if existing:save(kind,[binary,metadata])
    before=snapshot(root)
    with pytest.raises(ValueError):save(kind,[binary,{**metadata,'id':value}])
    assert snapshot(root)==before


@pytest.mark.parametrize('pages',[[],[[]]*9,[[dict(magicId=999,abilityId=None)]],
    [[dict(magicId=1,abilityId=116)]],[[dict(magicId=1,abilityId=None)]*2],
    [[dict(magicId=True,abilityId=None)]],[[dict(magicId=1,abilityId=None,extra=1)]]])
@pytest.mark.parametrize('existing',[False,True])
def test_invalid_pages_preserve_kernel_and_metadata(files,pages,existing):
    root,_,_=files
    if existing:save('book',[KERNEL,BOOK])
    before=snapshot(root)
    with pytest.raises(ValueError):save('book',[{**KERNEL,'value':43},{**BOOK,'value':pages}])
    assert snapshot(root)==before


@pytest.mark.parametrize('kind',['book','reptile'])
@pytest.mark.parametrize('bad',[None,[],{},dict(id=0,field=None,value=1),dict(id=0,field=[],value=1)])
def test_bad_edit_shapes_preserve_outputs(files,kind,bad):
    root,_,_=files;before=snapshot(root)
    with pytest.raises(ValueError):save(kind,[KERNEL if kind=='book' else ENEMY,bad])
    assert snapshot(root)==before


@pytest.mark.parametrize('kind',['book','reptile'])
@pytest.mark.parametrize('edits',[None,False,{},(),1,'text'])
def test_collection_is_an_array(files,kind,edits):
    root,_,_=files;before=snapshot(root)
    with pytest.raises(ValueError):save(kind,edits)
    assert snapshot(root)==before


@pytest.mark.parametrize('kind',['book','reptile'])
def test_corrupt_existing_metadata_rejects_before_binary_write(files,kind):
    root,_,output=files
    target=output/(gf_spellbooks.FILE_NAME if kind=='book' else reptile_atb.RELATIVE_PATH)
    target.parent.mkdir(parents=True);target.write_text('corrupt')
    before=snapshot(root)
    with pytest.raises(ValueError):save(kind,[KERNEL if kind=='book' else ENEMY,BOOK if kind=='book' else REPTILE])
    assert snapshot(root)==before


@pytest.mark.parametrize('kind',['book','reptile'])
@pytest.mark.parametrize('case',['duplicate','extra','binary'])
def test_duplicate_extra_and_invalid_binary_leave_existing_metadata_unchanged(files,kind,case):
    root,_,_=files
    binary=KERNEL if kind=='book' else ENEMY
    metadata=BOOK if kind=='book' else REPTILE
    save(kind,[binary,metadata]);before=snapshot(root)
    edits=[{**binary,'value':43},metadata]
    if case=='duplicate':edits.append(metadata)
    elif case=='extra':edits[-1]={**metadata,'offset':0}
    else:edits[0]={**binary,'value':-1}
    with pytest.raises(ValueError):save(kind,edits)
    assert snapshot(root)==before


def test_disabled_runtime_keeps_editable_book_but_writes_native_fallback(files,monkeypatch):
    _,_,output=files
    monkeypatch.setattr(gameplay_settings,'load',lambda *args,**kwargs:dict(gfSpellbooksEnabled=False,singleGf=True))
    save('book',[BOOK])
    assert gf_spellbooks.load(output)['books']==[dict(gfId=0,pages=BOOK['value'])]
    assert gf_spellbooks.parse_runtime((output/gf_spellbooks.RUNTIME_RELATIVE).read_bytes())['books']==[]


@pytest.mark.parametrize('kind',['book','reptile'])
def test_valid_mixed_save_matches_manual_bytes_and_reloads_metadata(files,kind):
    _,source,output=files
    originals=snapshot(source)
    result=save(kind,[KERNEL,BOOK] if kind=='book' else [ENEMY,REPTILE])
    assert result['saved']==2
    if kind=='book':
        expected=bytearray(originals['kernel.bin']);expected[256+7]=42
        assert (output/'kernel.bin').read_bytes()==bytes(expected)
        document=gf_spellbooks.load(output)
        assert document['books']==[dict(gfId=0,pages=BOOK['value'])]
        assert gf_spellbooks.parse_runtime((output/gf_spellbooks.RUNTIME_RELATIVE).read_bytes())==document
        save(kind,[{**BOOK,'id':'0','value':None}])
        assert gf_spellbooks.load(output)['books']==[]
    else:
        expected=bytearray(originals['c0m000.dat']);expected[64+0x102:64+0x104]=b'\x2a\x00'
        assert (output/'c0m000.dat').read_bytes()==bytes(expected)
        assert reptile_atb.load(output)['enemyIds']==[0]
        save(kind,[{**REPTILE,'id':'0','value':False}])
        assert reptile_atb.load(output)['enemyIds']==[]
    assert snapshot(source)==originals


@pytest.mark.parametrize('kind',['book','reptile'])
def test_http_rejects_mixed_invalid_metadata_before_writes(files,kind):
    root,_,_=files
    server=create_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        route='/api/kernel/save' if kind=='book' else '/api/enemies/save'
        bad={**BOOK,'value':[]} if kind=='book' else {**REPTILE,'id':.5}
        body=dict(edits=[KERNEL if kind=='book' else ENEMY,bad])
        if kind=='book':body['section']=3
        request=Request(f'http://127.0.0.1:{server.server_port}{route}',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:urlopen(request).read()
        assert error.value.code==400
        assert snapshot(root)==before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
