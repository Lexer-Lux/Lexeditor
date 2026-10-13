"""Weapon recipes validate their kernel edits before either file is written."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats
from plugins.ff8.server import create_server


def recipe(identifier=0):
    return dict(id=identifier,upgradePrice=150,
                ingredients=[dict(itemId=1,quantity=2)]+[dict(itemId=0,quantity=0) for _ in range(3)],
                fields=[dict(field='attack_power',value=250)])


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'vanilla';source.mkdir();output=tmp_path/'mod'
    record=bytearray([0xA5]*12);record[3]=1;record[4:]=bytes(8)
    (source/'mwepon.bin').write_bytes(record*2)
    schema=formats.SECTIONS[5];kernel=bytearray(256)+bytearray([0xA5])*schema['number_sub_section']*schema['sub_section_size']
    kernel[20:24]=(256).to_bytes(4,'little');(source/'kernel.bin').write_bytes(kernel)
    def current(name,dataset='current'):
        candidate=output/name
        return candidate if dataset=='current' and candidate.exists() else source/name
    monkeypatch.setattr(formats,'source_path',current)
    monkeypatch.setattr(formats,'output_path',lambda name:output/name)
    monkeypatch.setattr(formats,'source_label',lambda name:'Authored source')
    monkeypatch.setattr(formats,'ITEM_NAMES',{0:'None',1:'Authored ingredient'})
    return tmp_path,source,output


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('field',['id','upgradePrice','itemId','quantity','kernelValue'])
@pytest.mark.parametrize('value',[True,False,.5,float('inf'),float('nan'),'1.5'])
def test_weapon_nonintegers_preserve_both_files(files,field,value):
    root,_,output=files;before=snapshot(root);bad=recipe(1)
    if field in ('id','upgradePrice'):bad[field]=value
    elif field=='kernelValue':bad['fields'][0]['value']=value
    else:bad['ingredients'][0][field]=value
    with pytest.raises(ValueError,match='integer'):
        formats.save_weapons([recipe(),bad])
    assert snapshot(root)==before
    assert not output.exists()


@pytest.mark.parametrize('field,value',[
    ('attack_power',256),('unknown_field',1),('shots_per_atb',2)])
def test_rejected_kernel_field_does_not_overwrite_existing_recipe(files,field,value):
    root,source,output=files;output.mkdir()
    for name in ('kernel.bin','mwepon.bin'):(output/name).write_bytes((source/name).read_bytes())
    before=snapshot(root);bad=recipe();bad['fields']=[dict(field=field,value=value)]
    with pytest.raises(ValueError):formats.save_weapons([bad])
    assert snapshot(root)==before


@pytest.mark.parametrize('target',['section','id','value'])
@pytest.mark.parametrize('value',[True,.5,float('inf')])
def test_direct_kernel_save_rejects_noninteger_scalars(files,target,value):
    root,_,_=files;before=snapshot(root);section=5;edit=dict(id=0,field='attack_power',value=250)
    if target=='section':section=value
    else:edit[target]=value
    with pytest.raises(ValueError,match='integer'):formats.save_kernel(section,[edit])
    assert snapshot(root)==before


def test_valid_weapon_save_reloads_both_formats_and_preserves_unknown_bytes(files):
    _,source,output=files;originals={p.name:p.read_bytes() for p in source.iterdir()}
    assert formats.save_weapons([recipe()])['saved']==1
    expected=bytearray(originals['mwepon.bin']);expected[3]=15;expected[4:6]=b'\x01\x02'
    assert (output/'mwepon.bin').read_bytes()==bytes(expected)
    expected_kernel=bytearray(originals['kernel.bin']);expected_kernel[256+6]=250
    assert (output/'kernel.bin').read_bytes()==bytes(expected_kernel)
    row=formats.weapon_rows()['rows'][0]
    assert row['upgradePrice']==150
    assert row['ingredients'][0]==dict(slot=0,itemId=1,quantity=2)
    assert next(f['value'] for f in row['fields'] if f['field']=='attack_power')==250
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


def test_weapon_and_kernel_http_reject_before_writes_then_reload_valid_save(files):
    root,_,_=files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    def request(path,payload):
        return Request(base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root);bad=deepcopy(recipe());bad['fields'][0]['value']=250.5
        for path,payload in [('/api/weapons/save',{'edits':[bad]}),
                             ('/api/kernel/save',{'section':5.5,'edits':recipe()['fields']})]:
            with pytest.raises(HTTPError) as failure:urlopen(request(path,payload),timeout=5)
            assert failure.value.code==400;failure.value.close()
            assert snapshot(root)==before
        with urlopen(request('/api/weapons/save',{'edits':[recipe()]}),timeout=5) as response:
            assert json.load(response)['saved']==1
        assert formats.weapon_rows()['rows'][0]['upgradePrice']==150
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
