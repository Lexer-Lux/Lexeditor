"""All FF8 text sources validate identities and text before batch writes."""
from copy import deepcopy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import executable_text, formats, kernel_text, mngrp_text, paths
from plugins.ff8.server import create_server
from test_ff8_kernel_text import fixture as kernel_fixture


def edits():
    return {
        'kernel':dict(source='kernel',sectionId=32,recordId=0,slot=0,value='Changed'),
        'mngrp':dict(source='mngrp',sectionId=39,recordId=0,slot=0,value='Changed'),
        'exe':dict(source='exe_draw_point',sectionId=61,recordId=0,slot=0,value='Changed'),
    }


@pytest.fixture
def files(tmp_path,monkeypatch):
    source=tmp_path/'vanilla';source.mkdir();output=tmp_path/'mod'
    kernel,schema=kernel_fixture();(source/'kernel.bin').write_bytes(kernel)
    sections=[mngrp_text.Section(39,16,64,'Authored menu'),mngrp_text.Section(40,80,64,'Other menu')]
    menu=bytearray([0xA5])*160
    for section in sections:
        block=b'\x01\x00\x04\x00'+kernel_text.encode('Hi')+b'\0'
        menu[section.offset:section.offset+section.size]=block+bytes(section.size-len(block))
    (source/'mngrp.bin').write_bytes(menu)
    monkeypatch.setattr(formats,'SECTIONS',schema)
    monkeypatch.setattr(mngrp_text,'SECTIONS',sections);monkeypatch.setattr(mngrp_text,'BY_ID',{s.id:s for s in sections})
    def current(name,dataset='current'):
        candidate=output/name
        return candidate if dataset=='current' and candidate.exists() else source/name
    monkeypatch.setattr(formats,'source_path',current)
    monkeypatch.setattr(formats,'output_path',lambda name:output/name)
    monkeypatch.setattr(paths,'DIRECT_ROOT',output/'direct')
    def executable(source,dataset):
        path=output/'direct'/'ff8'/'en'/'exe'/source.filename
        if dataset=='current' and path.exists():
            executable_text.read_msd(path,source)
            return path.read_bytes()
        return executable_text.build_msd(['Hi']*source.count,source)
    monkeypatch.setattr(formats,'_executable_text_msd',executable)
    return tmp_path,source,output,schema


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('kind',['kernel','mngrp','exe'])
@pytest.mark.parametrize('field',['sectionId','recordId','slot'])
@pytest.mark.parametrize('value',[False,.5,float('inf'),'1.5'])
def test_text_identity_rejection_preserves_all_sources(files,kind,field,value):
    root,_,output,_=files;before=snapshot(root);bad=deepcopy(edits()[kind]);bad[field]=value
    first=dict(edits()['kernel'],sectionId=33)
    with pytest.raises(ValueError,match='integer'):formats.save_text([first,bad])
    assert snapshot(root)==before and not output.exists()


@pytest.mark.parametrize('kind',['kernel','mngrp','exe'])
@pytest.mark.parametrize('value',[None,True,7,{'text':'Changed'}])
def test_nontext_values_reject_without_stringifying(files,kind,value):
    root,_,output,_=files;before=snapshot(root);bad=dict(edits()[kind],value=value)
    with pytest.raises(ValueError,match='text'):formats.save_text([dict(edits()['kernel'],sectionId=33),bad])
    assert snapshot(root)==before and not output.exists()


def test_menu_slot_identity_is_zero(files):
    root,_,_,_=files;before=snapshot(root)
    with pytest.raises(ValueError,match='zero'):formats.save_text([dict(edits()['mngrp'],slot=1)])
    assert snapshot(root)==before


def test_valid_three_source_text_save_reloads_and_preserves_unselected_rows(files):
    _,source,output,schema=files;originals={p.name:p.read_bytes() for p in source.iterdir()}
    result=formats.save_text(list(edits().values()));assert result['saved']==3 and len(result['files'])==3
    rows=kernel_text.rows((output/'kernel.bin').read_bytes(),schema)['rows']
    assert rows[0]['value']=='Changed' and all(row['value']=='Hi' for row in rows[1:])
    rows=mngrp_text.rows((output/'mngrp.bin').read_bytes())['rows']
    assert [row['value'] for row in rows]==['Changed','Hi']
    saved_menu=(output/'mngrp.bin').read_bytes();original_menu=originals['mngrp.bin']
    assert saved_menu[:16]==original_menu[:16] and saved_menu[80:]==original_menu[80:]
    spec=executable_text.BY_ID['exe_draw_point'];path=output/'direct'/'ff8'/'en'/'exe'/spec.filename
    assert executable_text.read_msd(path,spec)==['Changed']+['Hi']*(spec.count-1)
    assert {p.name:p.read_bytes() for p in source.iterdir()}==originals


def test_text_http_rejection_and_valid_reload(files):
    root,_,output,schema=files;server=create_server(0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    url=f'http://127.0.0.1:{server.server_address[1]}/api/text/save'
    def request(batch):
        return Request(url,data=json.dumps({'edits':batch}).encode(),headers={'Content-Type':'application/json'})
    try:
        before=snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edits()['kernel'],dict(edits()['exe'],recordId=.5)]),timeout=5)
        assert failure.value.code==400;failure.value.close();assert snapshot(root)==before
        with urlopen(request(list(edits().values())),timeout=5) as response:assert json.load(response)['saved']==3
        assert kernel_text.rows((output/'kernel.bin').read_bytes(),schema)['rows'][0]['value']=='Changed'
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
