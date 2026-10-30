"""Legacy records never authorize writing, moving or deleting an executable."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from plugins.ds1 import deployment, exe_patches, tweak_mods
from test_ds1_exe_patches import VANILLA, HOOK_A


@pytest.fixture
def game(tmp_path,monkeypatch):
    monkeypatch.setattr(exe_patches,'VANILLA_SIZE',len(VANILLA))
    monkeypatch.setattr(exe_patches,'VANILLA_SHA256',hashlib.sha256(VANILLA).hexdigest())
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    root,library = tmp_path/'game',tmp_path/'library'
    root.mkdir();library.mkdir()
    spec = exe_patches.validate({'version':1,'hooks':[
        {'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]},'Synthetic fixture')
    monkeypatch.setattr(tweak_mods,'build_specs',lambda *_args,**_kwargs:[spec])
    built = exe_patches.compose(VANILLA,[spec])
    (root/exe_patches.EXECUTABLE).write_bytes(built)
    (root/tweak_mods.BACKUP_FILE).write_bytes(VANILLA)
    (root/tweak_mods.MANIFEST_FILE).write_text(json.dumps({
        'version':2,'sha256':hashlib.sha256(built).hexdigest(),'mods':['Synthetic fixture'],
        'project':None,'pending':None}))
    return root,library,built


def copies(root):
    return {path.name:path.read_bytes() for path in root.glob(exe_patches.EXECUTABLE+'*')
            if path.name != tweak_mods.LOCK_FILE}


def test_native_apply_preserves_old_executable_and_directs_verification_to_steam(game):
    root,library,_built = game
    before = copies(root)
    with pytest.raises(tweak_mods.TweakError,match='Verify.*Steam'):
        tweak_mods.apply(root,library)
    assert copies(root) == before
    assert not (root/tweak_mods.RUNTIME_DLL).exists()


@pytest.mark.parametrize('pending',[None,'original','built'])
def test_restore_does_not_resume_any_old_executable_write(game,pending):
    root,library,built = game
    manifest = root/tweak_mods.MANIFEST_FILE
    record = json.loads(manifest.read_text())
    if pending:
        record['pending'] = {'sha256':hashlib.sha256(VANILLA if pending=='original' else built).hexdigest(),
                             'mods':[],'project':None}
        manifest.write_text(json.dumps(record))
    before = copies(root)
    result = tweak_mods.restore(root,library)
    assert copies(root) == before
    assert 'Verify' in result['problem']
    assert not result['pendingRecovery']


@pytest.mark.parametrize('damaged',['journal','backup'])
def test_verified_executable_is_not_blocked_by_obsolete_damaged_records(game,damaged):
    root,library,_built = game
    (root/exe_patches.EXECUTABLE).write_bytes(VANILLA)  # Simulated Steam verification.
    (root/(tweak_mods.MANIFEST_FILE if damaged=='journal' else tweak_mods.BACKUP_FILE)).write_bytes(b'obsolete damage')
    before = copies(root)
    result = tweak_mods.apply(root,library)
    assert copies(root) == before
    assert result['state'] == 'tweaked' and not result['problem']
    assert (root/tweak_mods.RUNTIME_DLL).is_file()
    tweak_mods.restore(root,library)
    assert copies(root) == before


@pytest.mark.parametrize('helper',['put','remove','move','managed'])
def test_writer_boundaries_refuse_executable_mutation(game,helper):
    root,_library,built = game
    path = root/exe_patches.EXECUTABLE
    with pytest.raises(tweak_mods.TweakError,match='never'):
        if helper == 'put':
            tweak_mods._put(root,path,VANILLA)
        elif helper == 'remove':
            tweak_mods._remove(root,path)
        elif helper == 'move':
            tweak_mods._move_aside(root,path,PermissionError('pinned'))
        else:
            tweak_mods._write(root,built,VANILLA,[],tweak_mods.EXECUTABLE)
    assert path.read_bytes() == built
    assert not list(root.glob(exe_patches.EXECUTABLE+tweak_mods.LOCKED_SUFFIX+'*'))


@pytest.mark.parametrize('target',['DarkSoulsRemastered.exe','chr/another.exe','../outside.bin',
                                   'menu/item.bin:stream','menu/NUL.bin'])
def test_data_batch_rejects_executables_and_unsafe_targets_before_any_file_changes(game,target):
    root,library,_built = game
    project = library/'example'
    project.mkdir();(project/'mod.json').write_text('{"name":"Example"}')
    (root/'menu').mkdir()
    valid = root/'menu/valid.bin'
    valid.write_bytes(b'original valid file')
    before = copies(root)
    with pytest.raises(ValueError):
        deployment.apply(root,project,composed={Path('menu/valid.bin'):b'new valid bytes',Path(target):b'bad'})
    assert valid.read_bytes() == b'original valid file'
    assert not deployment._backup_path(root,Path('menu/valid.bin')).exists()
    assert copies(root) == before


@pytest.mark.parametrize('helper',['apply','restore'])
def test_low_level_data_writer_cannot_bypass_the_executable_guard(game,helper):
    root,library,built = game
    before = copies(root)
    with pytest.raises(ValueError,match='never writes'):
        if helper == 'apply':
            deployment._apply_file(root,library,Path(exe_patches.EXECUTABLE),library/'saved',VANILLA,'unused')
        else:
            deployment._restore_file(root,Path(exe_patches.EXECUTABLE))
    assert copies(root) == before and (root/exe_patches.EXECUTABLE).read_bytes() == built


def test_native_reader_uses_actual_executable_not_obsolete_data_journal(game):
    root,_library,built = game
    marker = deployment._marker_path(root,Path(exe_patches.EXECUTABLE))
    marker.write_bytes(b'old unsupported executable data journal')
    path = deployment.vanilla_source(root,Path(exe_patches.EXECUTABLE))
    assert path == root/exe_patches.EXECUTABLE and path.read_bytes() == built
    assert marker.read_bytes() == b'old unsupported executable data journal'


def test_bad_executable_mod_is_isolated_while_healthy_data_mod_loads(game,monkeypatch):
    from plugins.ds1 import standalone_runtime
    root,library,built = game
    good,bad = library/'good',library/'bad'
    for folder in (good,bad):
        folder.mkdir()
        (folder/'mod.json').write_text(json.dumps({'id':folder.name,'name':folder.name,'enabled':True}))
    (root/'menu').mkdir();(good/'menu').mkdir()
    (root/'menu/example.bin').write_bytes(b'original data')
    (good/'menu/example.bin').write_bytes(b'healthy mod data')
    (root/'chr').mkdir();(bad/'chr').mkdir()
    (root/'chr/extra.exe').write_bytes(b'unowned executable')
    (bad/'chr/extra.exe').write_bytes(b'unsupported executable replacement')
    marker = deployment._marker_path(root,Path('chr/extra.exe'))
    marker.write_bytes(b'bad obsolete journal')
    rows = [{'id':folder.name,'name':folder.name,'path':folder,'enabled':True,'prebuilt':True} for folder in (good,bad)]
    monkeypatch.setattr(standalone_runtime,'discover',lambda *_:rows)
    result = standalone_runtime._run(root,[],lambda:None)
    assert [row['id'] for row in result['disabled']] == ['bad']
    assert (root/'menu/example.bin').read_bytes() == b'healthy mod data'
    assert (root/'chr/extra.exe').read_bytes() == b'unowned executable'
    assert marker.read_bytes() == b'bad obsolete journal'
    assert (root/exe_patches.EXECUTABLE).read_bytes() == built
    assert json.loads((bad/'mod.json').read_text())['enabled'] is False


def test_owned_runtime_removal_preserves_modified_executable_and_pinned_copies(game,monkeypatch):
    root,library,built = game
    prior = root/(exe_patches.EXECUTABLE+tweak_mods.LOCKED_SUFFIX)
    prior.write_bytes(b'previous pinned executable copy')
    unrelated = root/('another-mod.bin'+tweak_mods.LOCKED_SUFFIX)
    unrelated.write_bytes(b'not owned by Lexeditor')
    tweak_mods._write_runtime(root,b'',[],None,library=library)
    before = copies(root)
    real_unlink = Path.unlink
    def pinned(self,*args,**kwargs):
        if self.name == tweak_mods.RUNTIME_DLL:
            raise PermissionError(13,'Access is denied')
        return real_unlink(self,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',pinned)
    result = tweak_mods.restore(root,library)
    assert copies(root) == before
    assert unrelated.read_bytes() == b'not owned by Lexeditor'
    assert not (root/tweak_mods.RUNTIME_DLL).exists()
    assert (root/(tweak_mods.RUNTIME_DLL+tweak_mods.LOCKED_SUFFIX)).is_file()
    assert not result['canRestore'] and 'Verify' in result['problem']
    monkeypatch.setattr(Path,'unlink',real_unlink)
    tweak_mods._clear_moved_aside(root)
    assert copies(root) == before and unrelated.exists()
    assert not (root/(tweak_mods.RUNTIME_DLL+tweak_mods.LOCKED_SUFFIX)).exists()


def test_cooperating_writers_do_not_enter_together(game):
    with tweak_mods._exclusive(game[0]):
        with pytest.raises(OSError):
            with tweak_mods._exclusive(game[0]):
                pytest.fail('The second writer acquired the same lock')


def test_unsafe_moved_aside_cache_does_not_block_cleanup_or_loader_replacement(game):
    root,_library,_built = game
    original = root/'unrelated.bin'
    original.write_bytes(b'preserve linked bytes')
    unsafe = root/(tweak_mods.RUNTIME_DLL+tweak_mods.LOCKED_SUFFIX)
    os.link(original,unsafe)
    tweak_mods._clear_moved_aside(root)
    assert original.read_bytes() == unsafe.read_bytes() == b'preserve linked bytes'
    live = root/tweak_mods.RUNTIME_DLL
    live.write_bytes(b'pinned DLL')
    tweak_mods._move_aside(root,live,PermissionError('pinned'))
    assert not live.exists()
    assert (root/(tweak_mods.RUNTIME_DLL+tweak_mods.LOCKED_SUFFIX+'-1')).read_bytes() == b'pinned DLL'
    assert unsafe.exists()


def test_info_page_restores_owned_loader_with_modified_executable(game):
    from ds1_fixture import make_archive
    from plugins.ds1.store import RELATIVE,MARKER
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright
    root,library,built = game
    (root/RELATIVE).parent.mkdir(parents=True)
    (root/RELATIVE).write_bytes(make_archive())
    project = library/'example'
    project.mkdir();(project/MARKER).touch()
    tweak_mods._write_runtime(root,b'',[],None,library=library)
    before = copies(root)
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(root),'LEXEDITOR_DS1_PROJECT':str(project),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0',tweak_mods.MODS_ENV:str(library)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                errors = []
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("info")')
                page.get_by_text(tweak_mods.EXECUTABLE_CHANGED,exact=True).wait_for()
                button = page.get_by_role('button',name='Restore original',exact=True)
                assert button.is_enabled()
                screenshot = os.environ.get('LEXEDITOR_EXECUTABLE_BOUNDARY_SCREENSHOT')
                if screenshot:
                    Path(screenshot).parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=screenshot)
                button.click()
                page.locator('.lex-dialog').get_by_role('button',name='Restore original',exact=True).click()
                page.wait_for_function('state.deployment?.native?.canRestore===false')
                assert copies(root) == before
                assert (root/exe_patches.EXECUTABLE).read_bytes() == built
                assert not (root/tweak_mods.RUNTIME_DLL).exists()
                assert not errors,errors
            finally:
                browser.close()
