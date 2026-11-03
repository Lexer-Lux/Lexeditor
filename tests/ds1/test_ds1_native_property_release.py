"""Editor-native properties remain editable and load without the editor."""
import json
import os
from pathlib import Path
import struct

import pytest

from core import mods_service
from plugins.ds1 import exe_patches, native_rules, native_support, runtime_mods, standalone_runtime, tweak_mods
from plugins.ds1.store import ItemStore, MARKER, RELATIVE
from test_ds1_band_composition import original
from ds1_native_fixture import make_native_archive
from test_ds1_exe_patches import HOOK_A


@pytest.fixture
def project(tmp_path,monkeypatch,original):
    game,library = tmp_path/'game',tmp_path/'library'
    mod = library/'native-editor'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_native_archive())
    (game/exe_patches.EXECUTABLE).write_bytes(original)
    mod.mkdir(parents=True);(mod/MARKER).touch()
    (mod/'mod.json').write_text('{"id":"native-editor","name":"Native editor fixture","enabled":true}')
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    mods_service.set_enabled(tweak_mods.ensure_loader_mod(library),True)
    rules = native_rules.NativeRules(game,mod,False)
    rules.edit_row(0,'baseRecovery',67)
    rules.save()
    return game,library,mod,rules,original


def recovery_value(patch):
    decoded = exe_patches.read_runtime_patch(patch)
    record = next(row for row in decoded['records'] if row[0] == exe_patches.HOOK and row[1] == 0x1500)
    return struct.unpack('<f',record[3][record[2]:])[0]


def test_property_only_release_loads_without_builder_and_keeps_editable_values(project,tmp_path,monkeypatch):
    game,_library,mod,_rules,original = project
    exported = runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    assert runtime_mods.inspect(runtime_mods.read(exported))['requiresData']
    assert (exported/native_support.RULES_FILE).is_file()
    assert native_rules.NativeRules(game,exported,True).saved['baseRecovery'] == 67
    from plugins.ds1 import mod_loader
    assert native_support.RULES_FILE.as_posix() in mod_loader.loaded_files(exported)
    assert native_rules.SETTINGS_FILE in mod_loader.loaded_files(exported)
    def forbidden(*_args,**_kwargs):
        pytest.fail('Standalone loading must consume built properties, not compile their source')
    monkeypatch.setattr(native_rules,'patch_spec',forbidden)
    monkeypatch.setattr(native_support,'build_sources',forbidden)
    report = standalone_runtime._run(game,[exported.parent],lambda:None)
    assert report['loaded'] == ['native-editor'] and not report['disabled']
    assert recovery_value((game/tweak_mods.RUNTIME_PATCH).read_bytes()) == 67
    assert (game/exe_patches.EXECUTABLE).read_bytes() == original


def test_library_activation_and_disable_own_the_native_properties(project):
    game,library,mod,_rules,original = project
    plan = tweak_mods.prepare(game,library)
    assert plan['runtime']['project'] is None
    assert recovery_value(plan['runtime']['patch']) == 67
    tweak_mods.commit(game,plan)
    assert native_rules.NativeRules(game,mod,False).deployment_status()['nativeProjectActive']
    mods_service.set_enabled(mod,False)
    tweak_mods.commit(game,tweak_mods.prepare(game,library))
    assert (game/tweak_mods.RUNTIME_PATCH).read_bytes() == b''
    assert not native_rules.NativeRules(game,mod,False).deployment_status()['nativeProjectActive']
    assert (game/exe_patches.EXECUTABLE).read_bytes() == original


def test_updated_imported_properties_preserve_opaque_module_and_reexport(project,tmp_path):
    game,_library,mod,_rules,original = project
    spec = exe_patches.validate({'version':1,'hooks':[
        {'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]},'Opaque native mod')
    opaque = runtime_mods.build(original,[spec])
    (mod/runtime_mods.FILENAME).write_bytes(opaque)
    imported = runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    rules = native_rules.NativeRules(game,imported,False)
    rules.edit_row(0,'baseRecovery',71);rules.save()
    # Export regenerates from saved properties, even though the imported
    # support artifact describes the prior saved values.
    exported = runtime_mods.write_release(imported,tmp_path/'second-release',original,game_root=game)
    module = runtime_mods.inspect(runtime_mods.read(exported))
    assert module['requiresData']
    for key in ('patch','claims','fixups','fixed'):
        assert module[key] == runtime_mods.inspect(opaque)[key]
    assert native_rules.NativeRules(game,exported,True).saved['baseRecovery'] == 71
    report = standalone_runtime._run(game,[exported.parent],lambda:None)
    assert report['loaded'] == ['native-editor']
    assert recovery_value((game/tweak_mods.RUNTIME_PATCH).read_bytes()) == 71


@pytest.mark.parametrize('damage',['support','settings','stamp','missing'])
def test_bad_property_mod_is_disabled_without_stopping_healthy_data(project,tmp_path,damage):
    game,_library,mod,_rules,original = project
    exported = runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    good = exported.parent/'healthy';good.mkdir()
    (good/'mod.json').write_text('{"id":"healthy","name":"Healthy","enabled":true}')
    (good/'menu').mkdir();(game/'menu').mkdir()
    (game/'menu/example.bin').write_bytes(b'original')
    (good/'menu/example.bin').write_bytes(b'healthy mod')
    if damage == 'support':
        (exported/native_support.RULES_FILE).write_bytes(b'{')
    elif damage == 'settings':
        (exported/native_rules.SETTINGS_FILE).write_bytes(b'[]')
    elif damage == 'missing':
        (exported/native_support.RULES_FILE).unlink()
        # Other valid data cannot mask the missing native contribution.
        (exported/'menu').mkdir();(exported/'menu/another.bin').write_bytes(b'valid data')
        (game/'menu/another.bin').write_bytes(b'original')
    else:
        source = exported/native_rules.SETTINGS_FILE
        content = json.loads(source.read_bytes());content['rules']['baseRecovery'] = 72
        source.write_text(json.dumps(content))
    report = standalone_runtime._run(game,[exported.parent],lambda:None)
    assert report['loaded'] == ['healthy']
    assert [row['id'] for row in report['disabled']] == ['native-editor']
    assert (game/'menu/example.bin').read_bytes() == b'healthy mod'
    assert (game/tweak_mods.RUNTIME_PATCH).read_bytes() == b''


def test_old_global_project_recipe_retires_when_its_library_mod_is_disabled(project):
    game,library,mod,rules,original = project
    contribution = rules._contribution(original)
    patch = exe_patches.runtime_patch(original,[exe_patches.validate(contribution['spec'],'Old project')])
    tweak_mods._write_runtime(game,patch,[],contribution,library=library)
    mods_service.set_enabled(mod,False)
    tweak_mods.commit(game,tweak_mods.prepare(game,library))
    assert tweak_mods._runtime(game)['record']['project'] is None
    assert (game/tweak_mods.RUNTIME_PATCH).read_bytes() == b''
    # The standalone path makes the same migration, including an off mod
    # which discovery deliberately excludes from the enabled row set.
    tweak_mods._write_runtime(game,patch,[],contribution,library=library)
    standalone_runtime._run(game,[library],lambda:None)
    assert tweak_mods.runtime_record(game)[0]['project'] is None
    assert (game/tweak_mods.RUNTIME_PATCH).read_bytes() == b''


def test_reuse_cannot_hide_native_source_changes_after_successful_loading(project,tmp_path):
    game,_library,mod,_rules,original = project
    exported = runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    assert standalone_runtime._run(game,[exported.parent],lambda:None)['loaded'] == ['native-editor']
    assert standalone_runtime._run(game,[exported.parent],lambda:None)['reused']
    source = exported/native_rules.SETTINGS_FILE
    content = json.loads(source.read_bytes());content['rules']['baseRecovery'] = 72
    source.write_text(json.dumps(content))
    report = standalone_runtime._run(game,[exported.parent],lambda:None)
    assert [row['id'] for row in report['disabled']] == ['native-editor']
    assert not report['loaded']
    assert (game/tweak_mods.RUNTIME_PATCH).read_bytes() == b''


def test_apply_uses_library_switch_instead_of_a_hidden_global_project(project):
    game,_library,mod,rules,_original = project
    store = ItemStore(game,mod,False);store.save()
    mods_service.set_enabled(mod,False)
    state = rules.apply(store)
    assert json.loads((mod/'mod.json').read_text())['enabled'] is True
    assert state['nativeProjectActive'] and not state['nativeStale']
    assert tweak_mods.runtime_record(game)[0]['project'] is None
    assert recovery_value((game/tweak_mods.RUNTIME_PATCH).read_bytes()) == 67


def test_apply_reports_a_disabled_owner_instead_of_silent_success(project):
    game,_library,mod,rules,_original = project
    (mod/native_support.FOLDER).mkdir()
    (mod/native_support.FOLDER/'broken.json').write_bytes(b'{')
    state = rules.apply(ItemStore(game,mod,False))
    assert [row['folder'] for row in state['disabledMods']] == [mod.name]
    assert json.loads((mod/'mod.json').read_text())['enabled'] is False
    assert not state['nativeProjectActive']


def test_shared_property_conflict_is_attributed_to_its_mod(project,tmp_path):
    game,_library,mod,_rules,original = project
    conflict = exe_patches.validate({'version':1,'hooks':[
        {'rva':0x1500,'original':struct.pack('<f',45).hex(),'bytes':struct.pack('<f',99).hex()}]},'Opaque conflict')
    (mod/runtime_mods.FILENAME).write_bytes(runtime_mods.build(original,[conflict]))
    with pytest.raises(tweak_mods.TweakError,match='conflict') as caught:
        tweak_mods.prepare(game,mod.parent)
    assert [Path(folder) for folder in caught.value.folders] == [mod]
    with pytest.raises(exe_patches.PatchError,match='conflict'):
        runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    assert not (tmp_path/'release'/mod.name).exists()


def test_imported_properties_render_in_existing_controls(project,tmp_path,monkeypatch):
    from playwright.sync_api import sync_playwright
    from plugins.ds1.plugin import DS1Session
    game,_library,mod,_rules,original = project
    exported = runtime_mods.write_release(mod,tmp_path/'release',original,game_root=game)
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(exported.parent))
    mods_service.set_enabled(tweak_mods.ensure_loader_mod(exported.parent),True)
    tweak_mods.apply(game,exported.parent)
    status = native_rules.NativeRules(game,exported,False).deployment_status()
    assert status['nativeProjectActive'] and status['sourceReady']
    with DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(exported),
                     'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0',
                     tweak_mods.MODS_ENV:str(exported.parent)}) as session:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1440,'height':900})
                # The service process cannot inherit the synthetic PE identity
                # patched into this test. Render the actual parent-side status.
                page.route('**/api/deployment',lambda route:route.fulfill(json=status))
                errors = []
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]')
                page.locator('.lex-plugin-loading-screen').wait_for(state='detached')
                page.evaluate('navigate("misc","misc","NativeRules:0")')
                field = page.locator('[data-field-key="baseRecovery"]')
                field.wait_for()
                assert float(field.input_value()) == 67
                assert field.get_attribute('type') == 'number' and field.is_enabled()
                screenshot = os.environ.get('LEXEDITOR_NATIVE_PROPERTY_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot)
                page.evaluate('navigate("info")')
                page.wait_for_function("Array.from(document.querySelectorAll('input.lex-readonly-field')).some(input=>input.value==='Selected library mod')")
                assert "Yes, this mod's native rules" in page.locator('input.lex-readonly-field').evaluate_all('inputs=>inputs.map(input=>input.value)')
                assert page.get_by_role('button',name='Apply',exact=True).is_enabled()
                if screenshot:
                    page.screenshot(path=str(Path(screenshot).with_name('native-property-information.png')))
                assert not errors,errors
            finally:
                browser.close()
