"""Metadata is validated and composed within the gameplay settings transaction."""
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from core import script_mods
from plugins.ff8 import gameplay_settings as settings, gf_spellbooks, reptile_atb, runtime_layout, paths
from plugins.ff8.server import create_server
from verify_ff8_gameplay_quarantine_issue_21 import make


DOCUMENT=dict(schemaVersion=1,books=[dict(gfId=0,pages=[[dict(magicId=1,abilityId=None)]])])
ENABLE={'tweaks':{'gf-spellbooks':{'enabled':True},'monogamy':{'enabled':True}}}


@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setenv(script_mods.TRUST_ENV,str(tmp_path/'trust.json'))
    root=tmp_path/'project';game=tmp_path/'game';game.mkdir()
    baseline=tmp_path/'baseline';baseline.mkdir()
    for mod_id in ['gf-spellbooks','monogamy','shared-party-magic-inventory']:
        make(root/'.lexeditor-mods',mod_id,mod_id,{'fields':[]})
    monkeypatch.setattr(paths,'PROJECT_ROOT',root)
    monkeypatch.setattr(paths,'GAME_ROOT',game)
    monkeypatch.setattr(paths,'BASELINE_ROOT',baseline)
    monkeypatch.setattr(paths,'RUNTIME_ROOT',root/'.lexeditor-runtime')
    gf_spellbooks.save(root,DOCUMENT)
    reptile_atb.write(root,enabled=True,reptile_enemy_ids=[0])
    return root,game


def snapshot(root):
    return {str(path.relative_to(root)):path.read_bytes() for path in root.rglob('*') if path.is_file()}


def save(project,data):
    root,game=project
    return settings.save(data,game_root=game,project_root=root,runtime_root=root/'.lexeditor-runtime')


@pytest.mark.parametrize('kind',['book','reptile'])
@pytest.mark.parametrize('existing',[False,True])
def test_invalid_metadata_preserves_all_settings_and_outputs(project,kind,existing):
    root,game=project
    if existing:save(project,ENABLE)
    target=root/(gf_spellbooks.FILE_NAME if kind=='book' else reptile_atb.RELATIVE_PATH)
    target.write_text('invalid metadata')
    before=snapshot(root)
    with pytest.raises(ValueError):save(project,ENABLE)
    assert snapshot(root)==before
    if not existing:
        assert not any(row['enabled'] for row in settings._tweak_payload(root,game))


def test_enable_disable_and_shared_inventory_compose_matching_snapshot(project):
    root,_=project
    active=root/'.lexeditor-runtime'/gf_spellbooks.RUNTIME_RELATIVE
    before=(root/reptile_atb.RELATIVE_PATH).read_bytes()
    result=save(project,ENABLE)
    assert result['gfSpellbooksEnabled'] and result['singleGf']
    assert gf_spellbooks.parse_runtime(active.read_bytes())==DOCUMENT
    assert active.read_bytes()==(root/gf_spellbooks.RUNTIME_RELATIVE).read_bytes()
    save(project,{'tweaks':{'shared-party-magic-inventory':{'enabled':True}}})
    assert gf_spellbooks.parse_runtime(active.read_bytes())['books']==[]
    assert gf_spellbooks.load(root)==DOCUMENT
    save(project,{'tweaks':{'shared-party-magic-inventory':{'enabled':False}}})
    assert gf_spellbooks.parse_runtime(active.read_bytes())==DOCUMENT
    save(project,{'tweaks':{'gf-spellbooks':{'enabled':False}}})
    assert gf_spellbooks.parse_runtime(active.read_bytes())['books']==[]
    assert (root/reptile_atb.RELATIVE_PATH).read_bytes()==before


def test_disabling_spellbooks_can_preserve_unreadable_inactive_document(project):
    root,_=project
    save(project,ENABLE)
    target=root/gf_spellbooks.FILE_NAME;target.write_text('unreadable')
    save(project,{'tweaks':{'gf-spellbooks':{'enabled':False}}})
    assert target.read_text()=='unreadable'
    assert gf_spellbooks.parse_runtime((root/'.lexeditor-runtime'/gf_spellbooks.RUNTIME_RELATIVE).read_bytes())['books']==[]


def test_composition_failure_restores_source_snapshot_and_switches(project,monkeypatch):
    root,game=project
    save(project,ENABLE)
    source=root/gf_spellbooks.RUNTIME_RELATIVE
    active=root/'.lexeditor-runtime'/gf_spellbooks.RUNTIME_RELATIVE
    previous=source.read_bytes()
    manifests={path:path.read_bytes() for path in (root/'.lexeditor-mods').rglob('mod.json')}
    original=runtime_layout.compose
    calls=[]
    def fail_once(*args,**kwargs):
        calls.append(1)
        if len(calls)==1:raise OSError('authored composition failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(runtime_layout,'compose',fail_once)
    with pytest.raises(OSError,match='authored composition failure'):
        save(project,{'tweaks':{'gf-spellbooks':{'enabled':False}}})
    assert source.read_bytes()==previous and active.read_bytes()==previous
    assert {path:path.read_bytes() for path in manifests}==manifests
    assert settings.load(root,game)['gfSpellbooksEnabled']
    assert len(calls)==2


@pytest.mark.parametrize('kind',['book','reptile'])
def test_http_metadata_rejection_preserves_outputs(project,kind):
    root,_=project
    target=root/(gf_spellbooks.FILE_NAME if kind=='book' else reptile_atb.RELATIVE_PATH)
    target.write_text('invalid metadata')
    server=create_server(0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        request=Request(f'http://127.0.0.1:{server.server_port}/api/settings/save',data=json.dumps(ENABLE).encode(),headers={'Content-Type':'application/json'})
        before=snapshot(root)
        with pytest.raises(HTTPError) as error:urlopen(request,timeout=10).read()
        assert error.value.code==400
        assert snapshot(root)==before
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
