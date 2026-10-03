"""Seven shell layers publish backups/XML/mappings as one guarded batch."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pytest
from plugins.rdr2 import server as s
from test_rdr2_issue_repairs import ProjectFixture


@pytest.fixture
def shell():
    fixture=ProjectFixture(methodName='runTest');fixture.setUp();fixture.stack()
    try:yield fixture
    finally:fixture.doCleanups()


def snapshot(root):return {path:path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('backup,position',[(backup,position) for backup,count in [(False,15),(True,8)] for position in range(1,count+1)])
@pytest.mark.parametrize('staging',[False,True])
def test_every_output_failure_preserves_files_backups_cache_and_times(shell,monkeypatch,backup,position,staging):
    if backup:
        for path in shell.files[:7]:path.with_suffix(path.suffix+'.bak').write_bytes(b'original backup')
    entries=[s.load_file(relative) for _,relative in s.WEAPON_STACK[:7]]
    old=[(entry['root'],ET.tostring(entry['root']),entry['mtime'],entry['source_digest']) for entry in entries]
    before=snapshot(shell.mine);times={path:path.stat().st_mtime_ns for path in before}
    owner,method=(s.tempfile,'NamedTemporaryFile') if staging else (s.os,'replace')
    original=getattr(owner,method);calls=0
    def fail_once(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==position:raise OSError('injected shell batch failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(owner,method,fail_once)
    with pytest.raises(OSError,match='injected shell batch'):s.apply_weapon_shell_vfx(False)
    assert calls>=position and snapshot(shell.mine)==before
    assert {path:path.stat().st_mtime_ns for path in times}==times
    for entry,(root,raw,mtime,digest) in zip(entries,old):
        assert entry['root'] is root and ET.tostring(root)==raw
        assert entry['mtime']==mtime and entry['source_digest']==digest
    assert not list(shell.mine.rglob('*.tmp')) and not list(shell.mine.rglob('.lexeditor-save-recovery-*'))


@pytest.mark.parametrize('loader',['<LML/>','<broken'])
def test_malformed_loader_is_rejected_before_shells_or_backups(shell,loader):
    (shell.mine/'install.xml').write_text(loader);before=snapshot(shell.mine)
    with pytest.raises(ValueError):s.apply_weapon_shell_vfx(False)
    assert snapshot(shell.mine)==before


def test_external_loader_changes_survive_prepared_batch(shell,monkeypatch):
    install=shell.mine/'install.xml';before=snapshot(shell.mine)
    original=s._prepare_file_replacements
    external=b'<LML><Resources><Resource/><External/></Resources></LML>'
    def modify(*args,**kwargs):
        payload=original(*args,**kwargs);install.write_bytes(external);return payload
    monkeypatch.setattr(s,'_prepare_file_replacements',modify)
    with pytest.raises(ValueError,match='changed'):s.apply_weapon_shell_vfx(False)
    before[install]=external
    assert snapshot(shell.mine)==before


def test_readonly_noop_and_mapping_only_transaction(shell):
    before=snapshot(shell.mine);s.DATASETS['mine']['readonly']=True
    with pytest.raises(ValueError,match='read-only'):s.apply_weapon_shell_vfx(False)
    assert snapshot(shell.mine)==before;s.DATASETS['mine']['readonly']=False
    assert s.apply_weapon_shell_vfx(True)==0
    assert len(s.install_replacements())==len(s.WEAPON_STACK)
    mapped=snapshot(shell.mine)
    assert s.apply_weapon_shell_vfx(True)==0 and snapshot(shell.mine)==mapped
    assert not list(shell.mine.rglob('*.bak'))


def test_shell_validation_checks_mapping_without_publication(shell,monkeypatch):
    before=snapshot(shell.mine)
    entries=[s.load_file(relative) for _,relative in s.WEAPON_STACK[:7]]
    roots=[entry['root'] for entry in entries]
    def forbidden(*args,**kwargs):raise AssertionError('validation published files')
    monkeypatch.setattr(s,'_commit_xml_roots',forbidden);monkeypatch.setattr(s,'_commit_file_outputs',forbidden)
    assert s.apply_weapon_shell_vfx(False,validate_only=True)==7
    assert s.apply_weapon_shell_vfx(True,validate_only=True)==0
    assert snapshot(shell.mine)==before
    assert all(entry['root'] is root for entry,root in zip(entries,roots))
    (shell.mine/'install.xml').write_text('<LML/>');before=snapshot(shell.mine)
    with pytest.raises(ValueError):s.apply_weapon_shell_vfx(False,validate_only=True)
    assert snapshot(shell.mine)==before


def test_http_requires_explicit_boolean_then_restores_all_layers(shell):
    http=s.create_server(0);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
    def post(body):
        request=Request(f'http://127.0.0.1:{http.server_port}/api/weapons/shell-vfx/save',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        return json.load(urlopen(request,timeout=5))
    try:
        before=snapshot(shell.mine)
        for body in [{},{'blanked':None},{'blanked':'false'},{'blanked':0},{'blanked':False,'extra':1},[],None]:
            with pytest.raises(HTTPError) as error:post(body)
            assert error.value.code==400 and snapshot(shell.mine)==before
        assert post({'blanked':False})=={'saved':7}
        assert s.get_weapon_shell_vfx_status()['blank']==0
        for path in shell.files[:7]:assert path.with_suffix(path.suffix+'.bak').read_bytes()==before[path]
        assert post({'blanked':True})=={'saved':7}
        assert s.get_weapon_shell_vfx_status()['blanked']
        for path in shell.files[:7]:assert path.with_suffix(path.suffix+'.bak').read_bytes()==before[path]
    finally:http.shutdown();http.server_close();worker.join()
