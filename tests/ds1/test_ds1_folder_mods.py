"""Portable native builds, independent linking and external library changes."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugins.ds1 import exe_patches, runtime_mods
from test_ds1_exe_patches import VANILLA, HOOK_A, HOOK_B, island


@pytest.fixture
def vanilla(monkeypatch):
    monkeypatch.setattr(exe_patches, 'VANILLA_SIZE', len(VANILLA))
    monkeypatch.setattr(exe_patches, 'VANILLA_SHA256', hashlib.sha256(VANILLA).hexdigest())
    return VANILLA


def spec():
    return exe_patches.validate({'version': 2,
        'islands': [island('code', relocations=[{'at': 8, 'rel32': HOOK_A}])],
        'hooks': [{'rva': HOOK_A, 'original': 'e800000000', 'branch': {'opcode': 'E8', 'island': 'code', 'offset': 4}},
                  {'rva': HOOK_B, 'original': '488d1500000000', 'bytes': '488d1500000000',
                   'relocations': [{'at': 3, 'island': 'code', 'offset': 4}]}]}, 'Example')


def test_prebuilt_link_moves_code_hooks_and_unwind_together(vanilla):
    module = runtime_mods.build(vanilla, [spec()])
    old = runtime_mods.inspect(module)
    source_base = next(rva for kind, rva, _, _ in old['records'] if kind == exe_patches.BLOCK)
    new_base = source_base + 0x20000
    after = exe_patches.read_runtime_patch(runtime_mods.link(module, new_base))
    block = next(record for record in after['records'] if record[0] == exe_patches.BLOCK)
    assert block[1] == new_base
    assert new_base + 12 + struct.unpack_from('<i', block[3], 8)[0] == HOOK_A
    functions = next(record for record in after['records'] if record[0] == exe_patches.FUNCTIONS)
    assert struct.unpack('<3I', functions[3]) == (new_base+4, new_base+12, new_base)
    for kind, rva, length, payload in after['records']:
        if kind == exe_patches.HOOK:
            offset = 1 if rva == HOOK_A else 3
            assert rva + offset + 4 + struct.unpack_from('<i', payload, length+offset)[0] == new_base+4


def test_damaged_module_is_rejected_without_linking(vanilla):
    payload = bytearray(runtime_mods.build(vanilla, [spec()]))
    payload[80] ^= 1
    with pytest.raises(exe_patches.PatchError, match='damaged'):
        runtime_mods.inspect(payload)


@pytest.mark.skipif(os.name != 'nt', reason='Windows pre-entry event')
def test_runtime_writes_require_a_live_pre_entry_window(monkeypatch):
    import ctypes
    from ctypes import wintypes
    from plugins.ds1 import standalone_runtime, tweak_mods
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.ResetEvent.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    pid = os.getpid()
    handle = kernel.CreateEventW(None, True, True, f'Local\\Lexeditor.DS1.Startup.{pid}')
    assert handle
    def running():
        raise ValueError('Game is already running')
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', running)
    try:
        with standalone_runtime.write_window(pid) as guard:
            guard()
            kernel.ResetEvent(handle)
            with pytest.raises(ValueError, match='ended'):
                guard()
        with pytest.raises(ValueError, match='running'):
            with standalone_runtime.write_window() as guard:
                guard()
    finally:
        kernel.CloseHandle(handle)
    with pytest.raises(ValueError, match='unavailable'):
        with standalone_runtime.write_window(pid):
            pytest.fail('A closed pre-entry window must not authorize writes')


def test_native_toggle_reuses_installed_data_without_composition(tmp_path, monkeypatch):
    from plugins.ds1 import mod_support, mod_loader, tweak_mods
    from plugins.ds1.store import MARKER, RELATIVE
    from core import mods_service
    from contextlib import nullcontext
    game, library = tmp_path/'game', tmp_path/'library'
    game.mkdir()
    native, data = library/'iframe-display', library/'data'
    for folder in (native, data):
        folder.mkdir(parents=True)
        (folder/MARKER).write_bytes(b'project')
    (native/'native').mkdir()
    (native/'native/iframe-display.json').write_text('{}')
    (data/RELATIVE).parent.mkdir(parents=True)
    (data/RELATIVE).write_bytes(b'data input')
    monkeypatch.setattr(mods_service, 'library_rows', lambda root: [
        {'name':'Iframe Display', 'path':str(native)}, {'name':'Data', 'path':str(data)}])
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=library)
    monkeypatch.setattr(adapter, '_report_path', lambda: tmp_path/'report.json')
    ordered = adapter._ordered_mods([data])
    adapter._save_report(game, ordered, [], installed=True)
    assert adapter._ordered_mods([native, data]) == ordered
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    monkeypatch.setattr(tweak_mods, 'locked', lambda root: nullcontext())
    monkeypatch.setattr(tweak_mods, 'prepare', lambda *args, **kwargs: {})
    monkeypatch.setattr(tweak_mods, 'commit', lambda *args: None)
    def no_composition(*args, **kwargs):
        pytest.fail('A native toggle must not recompose or redeploy unchanged game data')
    monkeypatch.setattr(mod_loader, 'compose_installed', no_composition)
    monkeypatch.setattr(mod_support.deployment, 'apply', no_composition)
    assert adapter.activate([native, data], game)['timings']['reusedInstalledData']
    assert adapter.activate([data], game)['timings']['reusedInstalledData']
    # An external edit still invalidates the installed recipe immediately.
    (data/RELATIVE).write_bytes(b'changed data input')
    assert adapter._read_report(game, ordered) is None


def test_menu_reuses_verified_install_even_after_cache_eviction(tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods, menu_layout
    original, installed = b'original menu', b'composed menu'
    managed = tweak_mods.Managed('menu/menu.drb.dcx', 'test menu', 1024, lambda value: value == original)
    monkeypatch.setattr(tweak_mods, 'LAYOUT', managed)
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    live = managed.live(tmp_path)
    live.parent.mkdir()
    live.write_bytes(original)
    specs = [{'owner':'UI', 'nodes':[1]}]
    identity = tweak_mods._menu_identity(original, specs, managed)
    tweak_mods._write(tmp_path, original, installed, ['UI'], managed, inputs=identity)
    manifest = tweak_mods._manifest(tmp_path, managed)
    def compose(*args):
        pytest.fail('An unchanged verified menu must survive disposable cache eviction')
    monkeypatch.setattr(menu_layout, 'compose', compose)
    assert tweak_mods._compose_menu(original, specs, managed, None,
                                   current=installed, manifest=manifest) == installed
    # An interrupted write uses its matching pending recipe, not the old one.
    pending = {**manifest, 'inputs':'0'*64,
               'pending':{'sha256':tweak_mods._sha(installed), 'mods':['UI'],
                          'project':None, 'inputs':identity}}
    tweak_mods._save_manifest(tmp_path, pending, managed)
    assert tweak_mods._compose_menu(original, specs, managed, None, current=installed,
                                   manifest=tweak_mods._manifest(tmp_path, managed)) == installed
    calls = []
    monkeypatch.setattr(menu_layout, 'compose', lambda *args: calls.append(args) or b'new menu')
    assert tweak_mods._compose_menu(original, specs+[{'owner':'New'}], managed, None,
                                   current=installed, manifest=manifest) == b'new menu'
    for invalid in (None, {}, ['broken'], 'bad cache'):
        assert tweak_mods._compose_menu(original, specs, managed, None, current=installed,
                                       manifest={**manifest,'inputs':invalid}) == b'new menu'
    assert tweak_mods._compose_menu(original, specs, managed, None, current=b'external edit',
                                   manifest=manifest) == b'new menu'
    assert len(calls) == 6


def test_export_contains_a_prebuilt_mod_without_developer_files(vanilla, tmp_path):
    source = tmp_path/'source'
    (source/'native').mkdir(parents=True)
    (source/'mod.json').write_text(json.dumps({'id':'example','name':'Example','script':{'version':1},'enabled':False}))
    raw = {'version':1,'hooks':[{'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]}
    (source/'native/example.json').write_text(json.dumps(raw))
    (source/'research.md').write_text('Development notes')
    output = runtime_mods.write_release(source, tmp_path/'release', vanilla)
    assert {file.name for file in output.iterdir()} == {'mod.json','runtime.lxd'}
    metadata = json.loads((output/'mod.json').read_text())
    assert metadata['enabled'] is True and 'script' not in metadata
    assert runtime_mods.inspect((output/'runtime.lxd').read_bytes())['records']


def test_files_report_marks_build_inputs_and_matching_payloads(tmp_path):
    from plugins.ds1.mod_loader import loaded_files
    folder = tmp_path/'example'
    for name in ('script/__init__.py','script/tweak.py','script/native_patch.py','script/code.S',
                 'script/__pycache__/tweak.pyc','tests/test_mod.py','native/example.json','native/unrelated.json',
                 'settings.json','settings.schema.json','runtime.lxd'):
        path = folder/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    (folder/'mod.json').write_text(json.dumps({'id':'example','name':'Example','script':{'version':1}}))
    loaded = set(loaded_files(folder))
    assert {'mod.json','script/tweak.py','script/native_patch.py','settings.json','settings.schema.json',
            'native/example.json','runtime.lxd'} <= loaded
    assert not loaded & {'tests/test_mod.py','script/__pycache__/tweak.pyc','native/unrelated.json'}


def test_watcher_notifies_after_burst_and_keeps_multiple_clients_current(tmp_path):
    from core.mod_watch import ModWatcher, COALESCE_SEC
    watcher = ModWatcher(str(tmp_path))
    try:
        watcher.notify('example/script/tweak.py')
        time.sleep(COALESCE_SEC + .03)
        first = watcher.snapshot(0)
        assert 'example' in first['changed']
        watcher.notify('other/native/other.json')
        assert watcher.snapshot(first['revision'])['revision'] == first['revision']
        time.sleep(COALESCE_SEC + .03)
        second = watcher.snapshot(first['revision'])
        assert second['revision'] > first['revision'] and 'other' in second['changed']
        assert 'example' in watcher.snapshot(0)['changed']
        watcher.notify('example/__pycache__/tweak.pyc')
        time.sleep(COALESCE_SEC + .03)
        assert watcher.snapshot(second['revision'])['revision'] == second['revision']
    finally:
        watcher.close()
    assert not watcher._thread.is_alive()


@pytest.mark.skipif(os.name != 'nt', reason='Windows directory notifications')
def test_real_directory_changes_detect_edits_without_restart(tmp_path):
    from core.mod_watch import ModWatcher
    folder = tmp_path/'example/script'
    folder.mkdir(parents=True)
    source = folder/'tweak.py'
    source.write_text('before')
    watcher = ModWatcher(str(tmp_path))
    try:
        deadline = time.monotonic()+5
        while watcher._handle is None and time.monotonic()<deadline:
            time.sleep(.02)
        time.sleep(.3)
        before = watcher.snapshot()['revision']
        source.write_text('after!')  # Same file size; no content polling.
        deadline = time.monotonic()+5
        while time.monotonic()<deadline:
            current = watcher.snapshot(before)
            if current['revision'] > before and 'example' in current['changed']:
                break
            time.sleep(.05)
        else:
            pytest.fail(watcher.snapshot(before))
    finally:
        watcher.close()


def binary_module(rva, result, external=False):
    import zlib
    block = 0x10000
    original = bytes.fromhex('b801000000')
    code = bytes([0xb8,result,0,0,0,0xc3])
    if external:
        code = bytes.fromhex('4883ec28e8')+struct.pack('<i',0x1200-block-9)+bytes([0x83,0xc0,result-3])+bytes.fromhex('4883c428c3')
    end = len(code)
    code += b'\x90'*(-len(code)%4)
    unwind = len(code)
    code += bytes.fromhex('0104010004420000') if external else bytes.fromhex('01000000')
    hook = b'\xe9'+struct.pack('<i', block-rva-5)
    patch = (b'LXD1PAT\0'+struct.pack('<4I',1,0x3000,0x1234abcd,3)
             +struct.pack('<3I',2,block,len(code))+code
             +struct.pack('<3I',3,0,1)+struct.pack('<3I',block,block+end,block+unwind)
             +struct.pack('<3I',1,rva,5)+original+hook)
    # BLOCK record RVA and hook replacement rel32.
    function_at = 24+12+len(code)+12
    fixes = [(28,3),(function_at,3),(function_at+4,3),(function_at+8,3),
             (function_at+12+12+5+1,1)]
    if external:
        fixes.append((24+12+5,2))
    raw = runtime_mods.HEADER.pack(runtime_mods.MAGIC,1,len(patch),len(fixes),0,0,0)+patch+b''.join(struct.pack('<2I',*fix) for fix in fixes)
    return raw+struct.pack('<I',zlib.crc32(raw))


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows loader')
def test_native_folder_loader_isolates_broken_disabled_and_conflicting_mods(tmp_path):
    from test_ds1_runtime_loader import build_module
    zig = build_module().find_zig(None)
    harness = tmp_path/'harness.exe'
    subprocess.run([zig,'cc','-target','x86_64-windows-gnu','-O1','-o',str(harness),
                    str(Path(__file__).with_name('folder_mod_harness.c')),'-lshell32'],check=True,
                   capture_output=True)
    library = tmp_path/'Global library 中文 with spaces'/'ds1'
    library.mkdir(parents=True)
    engine = Path(__file__).resolve().parents[2]
    (tmp_path/'lexeditor-ds1.ini').write_text('[Mods]\nLibrary='+str(library)+'\n[Runtime]\nPython='+sys.executable+'\nEngine='+str(engine)+'\n',encoding='utf-16')
    for name, rva, value, enabled, order in [('first',0x1000,42,True,1),('second',0x1100,77,True,2),
                                           ('disabled',0x1000,99,False,0),('conflicting',0x1000,99,True,3)]:
        folder=(tmp_path if name == 'first' else library)/name
        folder.mkdir()
        (folder/'mod.json').write_text(json.dumps({'id':name,'name':name,'enabled':enabled,'order':order}))
        (folder/'runtime.lxd').write_bytes(binary_module(rva,value,external=name=='second'))
    broken = library/'broken'
    broken.mkdir()
    (broken/'mod.json').write_text(json.dumps({'id':'broken','name':'broken','enabled':True}))
    (broken/'runtime.lxd').write_bytes(b'Damaged file')
    from ds1_fixture import make_archive
    from plugins.ds1.store import RELATIVE
    (tmp_path/RELATIVE).parent.mkdir(parents=True)
    (tmp_path/RELATIVE).write_bytes(make_archive())
    result = subprocess.run([str(harness),str(tmp_path),'--prepare-data'],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result
    assert 'results=42,77' in result.stdout, result.stdout
    assert 'prepared=1' in result.stdout, result.stdout
    assert 'unwind=1,1' in result.stdout, result.stdout
    assert 'broken: Damaged' in result.stdout
    assert 'conflicting: Conflicts' in result.stdout
    assert 'disabled:' not in result.stdout


def test_standalone_discovery_and_adoption_preserve_one_mod_copy(tmp_path):
    from core.standalone_mods import adopt
    from plugins.ds1.mod_support import Ds1ModAdapter
    game, library = tmp_path/'game', tmp_path/'Documents/Mods/ds1'
    mod = game/'Standalone example'
    mod.mkdir(parents=True)
    metadata = {'id':'example','name':'Example','enabled':True,'order':3}
    (mod/'mod.json').write_text(json.dumps(metadata))
    (mod/'runtime.lxd').write_bytes(binary_module(0x1000,42))
    reserved = game/'map'
    reserved.mkdir()
    (reserved/'mod.json').write_text(json.dumps(metadata))
    (reserved/'runtime.lxd').write_bytes(binary_module(0x1000,42))
    adapter = Ds1ModAdapter()
    discovered = adapter.standalone_mods(game)
    assert [row['path'] for row in discovered] == [str(mod)]
    moved = adopt(mod,library,discovered)
    assert moved.parent == library and not mod.exists()
    assert json.loads((moved/'mod.json').read_text()) == metadata
    assert adapter.standalone_mods(game) == []
    with pytest.raises(ValueError,match='Choose one'):
        adopt(reserved,library,[])


def test_editor_build_writes_independent_modules_and_preserves_original_executable(vanilla, tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods
    from test_ds1_tweak_mods import enable_loader, SPECS, TWEAK
    game, library = tmp_path/'game', tmp_path/'library'
    game.mkdir()
    executable = game/exe_patches.EXECUTABLE
    executable.write_bytes(vanilla)
    root = library/'alpha'
    (root/'script').mkdir(parents=True)
    (root/'script/__init__.py').write_text('')
    (root/'script/tweak.py').write_text(TWEAK % ('alpha',repr(SPECS['alpha'])))
    (root/'mod.json').write_text(json.dumps({'id':'alpha','name':'Alpha','enabled':True,'script':{'version':1}}))
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    enable_loader(library)
    plan = tweak_mods.prepare(game,library)
    assert plan['runtime']['patch'] == b'', 'Ordinary mod hooks must not also appear in the combined patch'
    assert len(plan['runtime']['moduleWrites']) == 1
    tweak_mods.commit(game,plan)
    assert (root/'runtime.lxd').is_file()
    runtime_mods.inspect((root/'runtime.lxd').read_bytes())
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert str(library) in (game/tweak_mods.RUNTIME_CONFIG).read_text(encoding='utf-16')
    (root/'runtime.lxd').write_bytes(b'Corrupt build output')
    assert tweak_mods.needs_rebuild(game,library)['needed']
    tweak_mods.commit(game,tweak_mods.prepare(game,library))
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert executable.read_bytes() == vanilla


def test_standalone_data_merger_combines_records_and_disables_only_broken_mod(tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    from ds1_fixture import make_archive
    from plugins.ds1.formats import ItemDocument
    from plugins.ds1.store import RELATIVE
    from plugins.ds1.standalone_runtime import run
    game, library = tmp_path/'game', tmp_path/'mods'
    (game/RELATIVE).parent.mkdir(parents=True)
    original = make_archive()
    (game/RELATIVE).write_bytes(original)
    for name, row_id, value in [('First',100,12),('Second',101,24),('Broken',102,36)]:
        folder = library/name
        (folder/RELATIVE).parent.mkdir(parents=True)
        (folder/'mod.json').write_text(json.dumps({'name':name,'id':name,'enabled':True,'order':row_id,'script':{'version':1}}))
        document = ItemDocument(original)
        document.edit('EquipParamGoods',row_id,'sellValue',value)
        (folder/RELATIVE).write_bytes(document.export() if name != 'Broken' else b'Broken archive')
        (folder/'script').mkdir()
        (folder/'script/tweak.py').write_text('raise RuntimeError("A player must never run this builder")')
    report = run(game,[library])
    assert [row['id'] for row in report['disabled']] == ['Broken']
    merged = ItemDocument((game/RELATIVE).read_bytes())
    assert merged.value('EquipParamGoods',100,'sellValue') == 12
    assert merged.value('EquipParamGoods',101,'sellValue') == 24
    assert run(game,[library])['reused'] is True
    native = library/'Iframe Display'
    native.mkdir()
    (native/'mod.json').write_text(json.dumps({'id':'iframe-display','name':'Iframe Display','enabled':True}))
    # Editor activation rewrites its native record/patch. Unchanged data must
    # still be reused when enabling, then disabling, a native-only sibling.
    for enabled in (True,False):
        (native/'mod.json').write_text(json.dumps({'id':'iframe-display','name':'Iframe Display','enabled':enabled}))
        (game/tweak_mods.RUNTIME_RECORD).write_text(json.dumps({'project':None,'mods':['Iframe Display'] if enabled else []}))
        (game/tweak_mods.RUNTIME_PATCH).write_bytes((game/tweak_mods.RUNTIME_PATCH).read_bytes())
        assert run(game,[library])['reused'] is True
    (game/'lexeditor-ds1-load.json').write_bytes(b'Broken cache')
    assert run(game,[library])['loaded'] == ['First','Second']


@pytest.mark.skipif(os.name != 'nt', reason='Windows private runtime')
def test_packaged_merger_runs_without_an_editor_or_python_installation(tmp_path):
    from plugins.ds1 import runtime_package
    from plugins.ds1.store import RELATIVE
    from ds1_fixture import make_archive
    supplied = os.environ.get('LEXEDITOR_TEST_LOADER_PACKAGE')
    package = Path(supplied) if supplied else runtime_package.package(tmp_path/'Loader package')
    game = tmp_path/'standalone game'
    library = game/'mods'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    library.mkdir()
    runtime = package/'lexeditor-runtime'
    env = {**os.environ,'PYTHONHOME':str(tmp_path/'Not installed'),'PYTHONPATH':str(tmp_path/'No editor')}
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateEventW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateEventW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateEventW(None,True,True,f'Local\\Lexeditor.DS1.Startup.{os.getpid()}')
    assert handle
    try:
        result = subprocess.run([str(runtime/'pythonw.exe'),'-I',str(runtime/'engine/plugins/ds1/standalone_entry.py'),
                                 '--game',str(game),'--root',str(library),'--startup-pid',str(os.getpid())],
                                env=env,timeout=30,capture_output=True)
    finally:
        kernel.CloseHandle(handle)
    assert result.returncode == 0, result
    report = json.loads((game/'lexeditor-ds1-load.json').read_text())
    assert report['loaded'] == [] and not report.get('error')


def test_adoption_prompt_and_used_files_render_without_changing_selection(tmp_path):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
    from test_mods_tab import HOST
    root = Path(__file__).resolve().parents[2]
    host = HOST.replace('window.shell = LexeditorUI.mountShell', '''
      window.moves=[];
      window.pywebview.api.unmanaged_mods=async()=>({mods:[{path:'F:/game/Example',name:'Example'},
        {path:'F:/game/Other',name:'Other'}],root:'D:/Documents/Mods/game'});
      window.pywebview.api.adopt_mod=async(plugin,path)=>{moves.push(path);return {path:'D:/Documents/Mods/game/Example'}};
      window.shell = LexeditorUI.mountShell''')
    assert host != HOST
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':1400,'height':900})
            page.route('http://fixture/**',lambda route:route.fulfill(body='<main id="main"></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(root/'ui/framework.css'))
            page.add_script_tag(path=str(root/'ui/framework.js'))
            page.evaluate(host,{'firstRun':False})
            dialog = page.get_by_role('dialog',name='Standalone mods found')
            dialog.wait_for()
            dialog.get_by_role('checkbox',name='Other',exact=True).uncheck()
            screenshot = os.environ.get('LEXEDITOR_ADOPTION_SCREENSHOT')
            if screenshot:
                page.screenshot(path=screenshot)
            dialog.get_by_role('button',name='Move to library',exact=True).click()
            page.wait_for_function('moves.length===1 && !document.body.inert')
            assert page.evaluate('moves') == ['F:/game/Example']
            assert not dialog.get_by_role('checkbox',name='Other',exact=True).is_checked()
            assert 'Some mods could not be moved' not in dialog.inner_text()
            dialog.get_by_role('button',name='Later',exact=True).click()
            page.evaluate('''()=>{window.__modContents={changes:[],canDescribe:true,files:[
              {relative:'mod.json',sizeLabel:'10 B',loaded:true},
              {relative:'native/example.json',sizeLabel:'1 KB',loaded:true},
              {relative:'script/tweak.py',sizeLabel:'1 KB',loaded:true},
              {relative:'tests/test_mod.py',sizeLabel:'1 KB',loaded:false}]}}''')
            page.locator('[data-tab="mods"]').click()
            page.locator('.lex-mods-page').wait_for()
            page.locator('[data-subtab="files"]').click()
            page.get_by_text('native/example.json',exact=True).wait_for()
            rows = page.locator('.lex-mod-contents .lex-list-row')
            used = page.locator('.lex-mod-file-loaded').all_text_contents()
            assert any('native/example.json' in row for row in used)
            assert any('script/tweak.py' in row for row in used)
            assert not any('tests/test_mod.py' in row for row in used)
            screenshot = os.environ.get('LEXEDITOR_USED_FILES_SCREENSHOT')
            if screenshot:
                page.screenshot(path=screenshot)
        finally:
            browser.close()


def test_external_mod_edit_updates_save_badge_without_restarting_or_losing_edits(tmp_path):
    from ds1_fixture import make_archive
    from plugins.ds1 import tweak_mods
    from plugins.ds1.store import RELATIVE, MARKER
    from plugins.ds1.plugin import DS1Session
    from playwright.sync_api import sync_playwright
    game, library, project = tmp_path/'game',tmp_path/'library',tmp_path/'project'
    (game/RELATIVE).parent.mkdir(parents=True)
    (game/RELATIVE).write_bytes(make_archive())
    project.mkdir()
    (project/MARKER).touch()
    folder = library/'Watched'
    (folder/'script').mkdir(parents=True)
    (folder/'mod.json').write_text(json.dumps({'id':'watched','name':'Watched','enabled':True,'script':{'version':1}}))
    (folder/'script/__init__.py').write_text('')
    source = folder/'script/tweak.py'
    source.write_text('def build(settings,context):\n    return {}\n')
    dll = tweak_mods.loader_bytes(online=True)
    (game/tweak_mods.RUNTIME_DLL).write_bytes(dll)
    (game/tweak_mods.RUNTIME_PATCH).write_bytes(b'')
    record = {'version':1,'mods':['Watched'],'project':None,'patchSha256':hashlib.sha256(b'').hexdigest(),
              'dllSha256':hashlib.sha256(dll).hexdigest(),'built':{'watched':tweak_mods.build_fingerprint(folder)}}
    (game/tweak_mods.RUNTIME_RECORD).write_text(json.dumps(record))
    session = DS1Session({'LEXEDITOR_DS1_ROOT':str(game),'LEXEDITOR_DS1_PROJECT':str(project),
                          'LEXEDITOR_DS1_MODS_ROOT':str(library),'LEXEDITOR_NO_MOD':'0','LEXEDITOR_MOD_READ_ONLY':'0'})
    session.start()
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={'width':1500,'height':950})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(session.url)
                page.wait_for_selector('body[data-ds1-ready="true"]',timeout=60000)
                page.wait_for_function('modRevision>0 && !state.tweaksNeedRebuild')
                page.evaluate('navigate("items","consumables","EquipParamGoods:100")')
                page.wait_for_function('state.selected==="EquipParamGoods:100" && state.row?.id===100')
                page.evaluate('''async()=>{
                  const result=await api('/api/edit',{table:'EquipParamGoods',id:100,field:'sellValue',value:55,sub:'consumables'});
                  state.dirty=result.dirtyCount;state.changes=result.changes;
                  fieldHistory.record({table:'EquipParamGoods',id:100,field:'sellValue',before:0,after:55});
                  await loadDetail();render();
                  window.beforeWatch={selected:state.selected,dirty:state.dirty,history:fieldHistory.undoStack.length};shell.refresh();
                }''')
                source.write_text('def build(settings,context):\n    return {} # changed by another chat\n')
                page.wait_for_function('state.tweaksNeedRebuild===true',timeout=15000)
                assert page.evaluate('({selected:state.selected,dirty:state.dirty,history:fieldHistory.undoStack.length})') == page.evaluate('beforeWatch')
                assert page.evaluate('state.dirty') > 0
                assert page.locator('#global-save').is_enabled()
                screenshot = os.environ.get('LEXEDITOR_MOD_WATCH_SCREENSHOT')
                if screenshot:
                    page.screenshot(path=screenshot)
                assert not errors, errors
            finally:
                browser.close()
    finally:
        session.stop()
