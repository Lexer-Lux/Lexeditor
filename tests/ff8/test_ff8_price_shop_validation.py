"""Item prices and shop slots reject malformed batches before any writes."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import formats
from plugins.ff8.server import create_server


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'vanilla';source.mkdir()
    (source/'price.bin').write_bytes(b'\x01\x00\x02\xa5'*2)
    (source/'shop.bin').write_bytes(b'\x00\xff'*320)
    output=tmp_path/'mod'
    def current(name,dataset='current'):
        candidate=output/name
        return candidate if dataset=='current' and candidate.exists() else source/name
    monkeypatch.setattr(formats,'source_path',current)
    monkeypatch.setattr(formats,'output_path',lambda name:output/name)
    monkeypatch.setattr(formats,'source_label',lambda name:'Authored source')
    monkeypatch.setattr(formats,'ITEM_NAMES',{0:'None',1:'Authored item'})
    return tmp_path,source,output


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind,second=False):
    return (dict(id=int(second),buyPrice=100,sellMultiplier=3) if kind=='items'
            else dict(shopId=int(second),slot=0,itemId=1,rare=True))


@pytest.mark.parametrize('kind,field',[
    ('items','id'),('items','buyPrice'),('items','sellMultiplier'),
    ('shops','shopId'),('shops','slot'),('shops','itemId')])
@pytest.mark.parametrize('value',[True,False,.5,float('inf'),float('nan'),'1.5'])
def test_price_shop_nonintegers_preserve_files_after_valid_edit(files,kind,field,value):
    root,_,output=files;before=snapshot(root);bad=edit(kind,True);bad[field]=value
    with pytest.raises(ValueError,match='integer'):
        getattr(formats,f'save_{kind}')([edit(kind),bad])
    assert snapshot(root)==before
    assert not output.exists()


@pytest.mark.parametrize('value',[0,1,'false',None])
def test_shop_rarity_requires_boolean(files,value):
    root,_,_=files;before=snapshot(root);bad=edit('shops',True);bad['rare']=value
    with pytest.raises(ValueError,match='boolean'):
        formats.save_shops([edit('shops'),bad])
    assert snapshot(root)==before


@pytest.mark.parametrize('kind,field,value',[
    ('items','id',2),('items','buyPrice',-10),('items','buyPrice',655360),
    ('items','buyPrice',101),('items','sellMultiplier',256),
    ('shops','shopId',20),('shops','slot',16),('shops','itemId',2)])
def test_price_shop_bounds_preserve_files(files,kind,field,value):
    root,_,_=files;before=snapshot(root);bad=edit(kind,True);bad[field]=value
    with pytest.raises(ValueError):
        getattr(formats,f'save_{kind}')([edit(kind),bad])
    assert snapshot(root)==before


def test_price_shop_valid_saves_reload_and_preserve_source_and_unknown_bytes(files):
    _,source,output=files
    original_price=(source/'price.bin').read_bytes();original_shop=(source/'shop.bin').read_bytes()
    assert formats.save_items([dict(id=0,buyPrice=655350,sellMultiplier=255)])['saved']==1
    assert (output/'price.bin').read_bytes()==b'\xff\xff\xff\xa5'+original_price[4:]
    row=formats.item_rows()['rows'][0]
    assert (row['buyPrice'],row['sellMultiplier'])==(655350,255)
    assert formats.save_shops([dict(shopId=19,slot=15,itemId=1,rare=True)])['saved']==1
    assert (output/'shop.bin').read_bytes()==original_shop[:-2]+b'\x01\x00'
    slot=formats.shop_rows()['rows'][19]['slots'][15]
    assert slot['itemId']==1 and slot['rare'] is True
    assert (source/'price.bin').read_bytes()==original_price
    assert (source/'shop.bin').read_bytes()==original_shop


def test_price_shop_http_rejects_batches_and_reloads_valid_saves(files):
    root,_,_=files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        for kind in ('items','shops'):
            url=f'http://127.0.0.1:{server.server_address[1]}/api/{kind}/save'
            def request(batch):
                return Request(url,data=json.dumps({'edits':batch}).encode(),headers={'Content-Type':'application/json'})
            before=snapshot(root);bad=edit(kind,True)
            bad['id' if kind=='items' else 'slot']=.5
            with pytest.raises(HTTPError) as failure:
                urlopen(request([edit(kind),bad]),timeout=5)
            assert failure.value.code==400;failure.value.close()
            assert snapshot(root)==before
            with urlopen(request([edit(kind)]),timeout=5) as response:
                assert json.load(response)['saved']==1
            if kind=='items':
                assert formats.item_rows()['rows'][0]['buyPrice']==100
            else:
                assert formats.shop_rows()['rows'][0]['slots'][0]['rare'] is True
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
