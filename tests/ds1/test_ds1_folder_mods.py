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


def test_shared_support_links_beyond_independently_built_fixed_mod(vanilla):
    fixed_spec = spec()
    fixed_spec['islands'][0]['rva'] = 0x10000
    fixed = runtime_mods.build(vanilla, [fixed_spec])
    support = exe_patches.validate({'version':2,
        'islands':[island('shared',relocations=[{'at':8,'rel32':HOOK_A}])],
        'hooks':[{'rva':HOOK_B,'original':'488d1500000000','pad':'9090','branch':
                  {'opcode':'E8','island':'shared','offset':4}}]},'Shared support')
    patch = runtime_mods.shared_patch(vanilla,[support],[fixed])
    decoded = exe_patches.read_runtime_patch(patch)
    block = next(row for row in decoded['records'] if row[0] == exe_patches.BLOCK)
    assert block[1] >= 0x20000
    assert block[1]+12+struct.unpack_from('<i',block[3],8)[0] == HOOK_A
    hook = next(row for row in decoded['records'] if row[0] == exe_patches.HOOK)
    assert hook[1]+5+struct.unpack_from('<i',hook[3],hook[2]+1)[0] == block[1]+4


def test_standalone_cache_tracks_fixed_allocations_and_ignores_broken_native_siblings(vanilla,tmp_path):
    from plugins.ds1 import standalone_runtime
    folder = tmp_path/'fixed'
    folder.mkdir()
    row = {'path':folder,'id':'fixed','name':'Fixed'}
    baseline = standalone_runtime._identity([],tmp_path,[])
    fixed_spec = spec()
    fixed_spec['islands'][0]['rva'] = 0x10000
    (folder/'runtime.lxd').write_bytes(runtime_mods.build(vanilla,[fixed_spec]))
    assert standalone_runtime._identity([row],tmp_path,[]) != baseline
    assert len(standalone_runtime._fixed_modules([row])) == 1
    (folder/'runtime.lxd').write_bytes(b'Broken native module')
    assert standalone_runtime._fixed_modules([row]) == []
    assert standalone_runtime._identity([row],tmp_path,[]) == baseline


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





def test_export_contains_a_prebuilt_mod_without_developer_files(vanilla, tmp_path):
    source = tmp_path/'source'
    (source/'native').mkdir(parents=True)
    (source/'mod.json').write_text(json.dumps({'id':'example','name':'Example','enabled':False}))
    raw = {'version':1,'hooks':[{'rva':HOOK_A,'original':'e800000000','bytes':'9090909090'}]}
    (source/'native/example.json').write_text(json.dumps(raw))
    (source/'native/second-component.json').write_text(json.dumps({'version':1,
        'hooks':[{'rva':HOOK_B,'original':'488d1500000000','bytes':'90909090909090'}]}))
    (source/'research.md').write_text('Development notes')
    output = runtime_mods.write_release(source, tmp_path/'release', vanilla)
    assert {file.name for file in output.iterdir()} == {'mod.json','runtime.lxd'}
    metadata = json.loads((output/'mod.json').read_text())
    assert metadata['enabled'] is True and 'script' not in metadata
    records = runtime_mods.inspect((output/'runtime.lxd').read_bytes())['records']
    assert {row[1] for row in records if row[0] == exe_patches.HOOK} == {HOOK_A, HOOK_B}
    for unsafe in ('map','mods','../escape',r'nested\mod','CON','native:'):
        (source/'mod.json').write_text(json.dumps({'id':unsafe,'name':'Example'}))
        with pytest.raises(ValueError):
            runtime_mods.write_release(source,tmp_path/'rejected',vanilla)
    assert not (tmp_path/'rejected').exists()


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
            'native/example.json','native/unrelated.json','runtime.lxd'} <= loaded
    assert not loaded & {'tests/test_mod.py','script/__pycache__/tweak.pyc'}
    from plugins.ds1 import mod_loader
    # A filtered reader still returns a mod with no matching files. Library
    # composition excludes that empty contribution without changing the API.
    assert mod_loader.read_mod(folder,'Example').files == {}
    assert mod_loader.active_mods(tmp_path,folder) == []


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
@pytest.mark.parametrize('compiler',['zig','msvc'])
def test_native_folder_loader_isolates_broken_disabled_and_conflicting_mods(tmp_path, compiler):
    from test_ds1_runtime_loader import build_module
    harness = tmp_path/'harness.exe'
    source = Path(__file__).with_name('folder_mod_harness.c')
    build = build_module()
    if compiler == 'zig':
        try:
            zig = build.find_zig(None)
        except SystemExit:
            pytest.skip('Zig is not installed; MSVC covers native loading on CI')
        subprocess.run([zig,'cc','-target','x86_64-windows-gnu','-O1','-o',str(harness),
                        str(source),'-lshell32'],check=True,capture_output=True)
    else:
        try:
            vcvars = build.find_vcvars()
        except SystemExit:
            pytest.skip('MSVC is not installed')
        batch = tmp_path/'build-native.bat'
        batch.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                         f'cl /nologo /O1 /std:c17 /D_CRT_SECURE_NO_WARNINGS "{source}" '
                         f'/Fe:"{harness}" /Fo:"{tmp_path / "harness.obj"}" /link shell32.lib\n')
        subprocess.run(['cmd','/c',str(batch)],cwd=tmp_path,check=True,capture_output=True)
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
    # Empty development folders are not data dependencies of a compiled
    # native-only module. It can load without the optional data helper.
    (tmp_path/'first/sfx').mkdir()
    native_only = subprocess.run([str(harness),str(tmp_path)],capture_output=True,text=True,timeout=20)
    assert native_only.returncode == 0 and 'results=42,77' in native_only.stdout, native_only
    provider = library/'data-provider'
    (provider/RELATIVE).parent.mkdir(parents=True)
    (provider/'mod.json').write_text(json.dumps({'id':'data-provider','name':'Data provider','enabled':True}))
    (provider/RELATIVE).write_bytes(make_archive())
    second = library/'second/mod.json'
    info = json.loads(second.read_text())
    second.write_text(json.dumps({**info,'requires':['data-provider']}))
    prepared = subprocess.run([str(harness),str(tmp_path),'--prepare-data'],capture_output=True,text=True,timeout=20)
    assert prepared.returncode == 0 and 'results=42,77' in prepared.stdout, prepared
    # A data-only dependency is satisfied by the merger's verified result,
    # never by the mere presence of a folder with the right name.
    unavailable = subprocess.run([str(harness),str(tmp_path)],capture_output=True,text=True,timeout=20)
    assert unavailable.returncode == 0 and 'results=42,1' in unavailable.stdout, unavailable
    assert 'second: Missing, failed or cyclic dependency' in unavailable.stdout
    # A successful helper for someone else's data must not satisfy this
    # module's own missing prebuilt data requirement.
    import zlib
    module = bytearray((library/'second/runtime.lxd').read_bytes())
    struct.pack_into('<I',module,28,1)
    struct.pack_into('<I',module,len(module)-4,zlib.crc32(module[:-4]))
    (library/'second/runtime.lxd').write_bytes(module)
    missing_own = subprocess.run([str(harness),str(tmp_path),'--prepare-data'],capture_output=True,text=True,timeout=20)
    assert missing_own.returncode == 0 and 'results=42,1' in missing_own.stdout, missing_own
    assert not json.loads(second.read_text())['enabled']


@pytest.mark.skipif(os.name != 'nt', reason='Windows native hook workers')
def test_competing_mod_hook_workers_install_and_repair_without_freezing(tmp_path):
    from test_ds1_runtime_loader import build_module
    build = build_module()
    try:
        vcvars = build.find_vcvars()
    except SystemExit:
        pytest.skip('MSVC is not installed')
    source = Path(__file__).with_name('concurrent_hook_harness.c')
    executable = tmp_path/'concurrent-hooks.exe'
    batch = tmp_path/'build-concurrent.bat'
    batch.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b %errorlevel%\n'
                     f'cl /nologo /O1 /std:c17 /D_CRT_SECURE_NO_WARNINGS "{source}" '
                     f'/Fe:"{executable}" /Fo:"{tmp_path / "concurrent.obj"}" /link shell32.lib\n')
    subprocess.run(['cmd','/c',str(batch)],cwd=tmp_path,check=True,capture_output=True)
    result = subprocess.run([str(executable)],capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result
    assert 'installed=24 repaired=22 protection=RX responsive=1' in result.stdout


@pytest.mark.skipif(os.name != 'nt', reason='Windows input proxy chaining')
def test_foreign_input_proxy_loads_once_and_broken_chain_preserves_system_input(tmp_path):
    from test_ds1_runtime_loader import build_module
    build = build_module()
    try:
        vcvars = build.find_vcvars()
    except SystemExit:
        pytest.skip('MSVC is not installed')
    source = Path(__file__).with_name('chain_loader_harness.c')
    fixture = source.with_name('chain_loader_fixture.c')
    executable = tmp_path/'chain-harness.exe'
    valid = tmp_path/'valid.dll'
    no_export = tmp_path/'no-export.dll'
    batch = tmp_path/'build-chain.bat'
    batch.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b %errorlevel%\n'
        f'cl /nologo /O1 /std:c17 /D_CRT_SECURE_NO_WARNINGS "{source}" /Fe:"{executable}" /Fo:"{tmp_path / "harness.obj"}"\n'
        'if errorlevel 1 exit /b %errorlevel%\n'
        f'cl /nologo /O1 /LD /std:c17 "{fixture}" /Fe:"{valid}" /Fo:"{tmp_path / "fixture.obj"}"\n'
        'if errorlevel 1 exit /b %errorlevel%\n'
        f'cl /nologo /O1 /LD /std:c17 /DLX_WITHOUT_INPUT_EXPORT "{fixture}" /Fe:"{no_export}" /Fo:"{tmp_path / "no-export.obj"}"\n')
    subprocess.run(['cmd','/c',str(batch)],cwd=tmp_path,check=True,capture_output=True)
    folder = tmp_path/'game with spaces 中文'
    folder.mkdir()
    chain = folder/'dinput8.chain.dll'
    def run(mode):
        result = subprocess.run([str(executable),str(folder),mode],capture_output=True,text=True,timeout=10)
        assert result.returncode == 0,result
        return result.stdout
    assert 'system=1' in run('system')
    chain.write_bytes(valid.read_bytes())
    result = run('chain')
    assert 'chain=42' in result and result.count('forwarding its input calls') == 1
    chain.write_bytes(no_export.read_bytes())
    result = run('system')
    assert 'without an input export' in result and 'system=1' in result
    chain.write_bytes(b'Damaged DLL')
    result = run('system')
    assert 'Could not load dinput8.chain.dll' in result and 'system=1' in result
    assert chain.read_bytes() == b'Damaged DLL'


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
    # Export uses only the built outputs and refuses to package newer source.
    release = runtime_mods.write_release(root,tmp_path/'release',vanilla)
    assert (release/'runtime.lxd').is_file() and not (release/'script').exists()
    (root/'script/tweak.py').write_text('raise RuntimeError("must never run during export")')
    with pytest.raises(ValueError,match='Save and build'):
        runtime_mods.write_release(root,tmp_path/'stale-release',vanilla)


def test_player_zip_exports_prebuilt_mod_with_loader_and_declared_dependencies(vanilla,tmp_path,monkeypatch):
    import zipfile
    from plugins.ds1 import deployment, runtime_package
    from plugins.ds1.mod_support import Ds1ModAdapter
    game = tmp_path/'game'
    game.mkdir()
    executable = game/exe_patches.EXECUTABLE
    executable.write_bytes(vanilla)
    monkeypatch.setattr(deployment,'vanilla_source',lambda *_:executable)
    folder = tmp_path/'mod'
    folder.mkdir()
    (folder/'mod.json').write_text(json.dumps({'id':'example','name':'Example','requires':['another-mod']}))
    module = runtime_mods.build(vanilla,[spec()])
    (folder/'runtime.lxd').write_bytes(module)
    def package(destination):
        destination.mkdir()
        (destination/'dinput8.dll').write_bytes(b'loader')
        (destination/'lexeditor-runtime').mkdir()
        (destination/'lexeditor-runtime/pythonw.exe').write_bytes(b'private runtime')
        return destination
    monkeypatch.setattr(runtime_package,'package',package)
    output = tmp_path/'release.zip'
    adapter = Ds1ModAdapter()
    result = adapter.export_release(folder,game,output)
    assert result['path'] == str(output)
    with zipfile.ZipFile(output) as archive:
        assert {'dinput8.dll','lexeditor-runtime/pythonw.exe','mods/example/runtime.lxd'} <= set(archive.namelist())
        assert archive.read('mods/example/runtime.lxd') == module
        assert json.loads(archive.read('mods/example/mod.json'))['requires'] == ['another-mod']
    before = output.read_bytes()
    with pytest.raises(ValueError,match='existing'):
        adapter.export_release(folder,game,output)
    assert output.read_bytes() == before
    (folder/'runtime.lxd').write_bytes(runtime_mods.build(vanilla,[spec()],requires_data=True))
    with pytest.raises(ValueError,match='missing its required data'):
        adapter.export_release(folder,game,tmp_path/'missing-data.zip')
    assert not (tmp_path/'missing-data.zip').exists()


def test_shared_export_action_locks_ui_and_recovers_from_failure(tmp_path):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
    from test_mods_tab import HOST
    root = Path(__file__).resolve().parents[2]
    host = HOST.replace('canManage: true,','canManage: true,canExport:true,').replace(
        'window.shell = LexeditorUI.mountShell', '''
      window.exports=[];
      window.pywebview.api.export_mod=async(...args)=>{
        exports.push(args);await new Promise(resolve=>setTimeout(resolve,150));
        if(window.exportError)throw new Error('Save and build this mod before exporting');
        return {path:'C:/exports/Mine.zip'};
      };
      window.shell = LexeditorUI.mountShell''')
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width':1400,'height':900})
            page.route('http://fixture/**',lambda route:route.fulfill(body='<main id="main"></main>',content_type='text/html'))
            page.goto('http://fixture/')
            page.add_style_tag(path=str(root/'ui/framework.css'))
            page.add_script_tag(path=str(root/'ui/framework.js'))
            page.evaluate(host,{'firstRun':False})
            page.locator('[data-tab="mods"]').click()
            button = page.get_by_role('button',name='Export Mine for players',exact=True)
            button.click()
            page.wait_for_function('exports.length===1 && document.body.inert')
            page.wait_for_function('!document.body.inert')
            assert page.evaluate('exports[0]') == ['game','C:/lib/game/Mine']
            screenshot = os.environ.get('LEXEDITOR_EXPORT_SCREENSHOT')
            if screenshot: page.screenshot(path=screenshot)
            page.evaluate('window.exportError=true')
            button.click()
            page.get_by_role('alertdialog',name='Could not export the mod').wait_for()
            page.wait_for_function('!document.body.inert')
            assert page.get_by_role('button',name='Close',exact=True).is_enabled()
        finally:
            browser.close()


def test_export_host_validates_library_selection_and_respects_save_dialog_cancel(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import threading
    from core.desktop_host import HostApi
    folder = tmp_path/'library/example'
    folder.mkdir(parents=True)
    (folder/'mod.json').write_text(json.dumps({'name':'Example'}))
    exports, dialogs = [], []
    selection = []
    def choose(*args,**kwargs):
        dialogs.append((args,kwargs))
        return selection
    adapter = SimpleNamespace(export_release=lambda *args:exports.append(args) or {'path':str(args[-1])})
    host = SimpleNamespace(_game_mods=lambda _:folder.parent,_mod_adapter=lambda _:adapter,
        _installations=SimpleNamespace(snapshot=lambda _:{'root':str(tmp_path/'game')}),
        _bound_window=lambda:SimpleNamespace(create_file_dialog=choose),_mod_library_lock=threading.RLock())
    monkeypatch.setitem(sys.modules,'webview',SimpleNamespace(SAVE_DIALOG='save'))
    assert HostApi.export_mod(host,'ds1',str(folder)) == {'cancelled':True}
    assert exports == []
    destination = tmp_path/'chosen.zip'
    selection.append(str(destination))
    assert HostApi.export_mod(host,'ds1',str(folder)) == {'path':str(destination)}
    assert exports == [(folder,tmp_path/'game',destination)]
    assert dialogs[-1][1]['save_filename'] == 'example.zip'
    with pytest.raises(ValueError):
        HostApi.export_mod(host,'ds1',str(tmp_path/'elsewhere'))
    assert len(dialogs) == 2


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
    from plugins.ds1.formats import ItemDocument
    for mod_id,row_id,price in [('first',100,12),('second',101,24),('broken',102,36)]:
        folder = library/mod_id
        (folder/RELATIVE).parent.mkdir(parents=True)
        (folder/'mod.json').write_text(json.dumps({'id':mod_id,'name':mod_id,'enabled':True,'script':{'version':1}}))
        (folder/'runtime.lxd').write_bytes(binary_module(0x1000,42))
        document = ItemDocument(make_archive())
        document.edit('EquipParamGoods',row_id,'sellValue',price)
        (folder/RELATIVE).write_bytes(document.export() if mod_id != 'broken' else b'Broken data')
        (folder/'script').mkdir()
        (folder/'script/tweak.py').write_text('raise RuntimeError("Players never run builders")')
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
    assert set(report['loaded']) == {'first','second'} and not report.get('error')
    assert [row['id'] for row in report['disabled']] == ['broken']
    merged = ItemDocument((game/RELATIVE).read_bytes())
    assert merged.value('EquipParamGoods',100,'sellValue') == 12
    assert merged.value('EquipParamGoods',101,'sellValue') == 24


def test_standalone_menu_failure_disables_only_its_owner(tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods, standalone_runtime
    from test_ds1_menu_scripts import archive, build_script, script, passes_of
    original = archive({'i02-00.esd':build_script().to_bytes()})
    managed = tweak_mods.Managed('menu/ingame.menuesdbnd.dcx','test menu scripts',1024*1024,
                                 lambda data:data == original)
    monkeypatch.setattr(tweak_mods,'ESD',(managed,))
    monkeypatch.setattr(tweak_mods,'ESD_ARCHIVE',{managed:'ingame'})
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    game,library = tmp_path/'game',tmp_path/'library'
    managed.live(game).parent.mkdir(parents=True)
    managed.live(game).write_bytes(original)
    for mod_id,member in [('healthy','i02-00.esd'),('broken','missing.esd')]:
        folder = library/mod_id
        (folder/'esd').mkdir(parents=True)
        (folder/'mod.json').write_text(json.dumps({'id':mod_id,'name':mod_id,'enabled':True}))
        (folder/'esd/component.json').write_text(json.dumps(script(member=member)))
    report = standalone_runtime.run(game,[library])
    assert [row['id'] for row in report['disabled']] == ['broken']
    assert report['loaded'] == ['healthy']
    assert json.loads((library/'healthy/mod.json').read_text())['enabled']
    assert [command.id for command in passes_of(managed.live(game).read_bytes())] == [15,29,20]
    # An unattributed game-file problem must not blame or disable every mod.
    managed.live(game).write_bytes(b'Externally changed menu')
    with pytest.raises(tweak_mods.TweakError,match='changed outside'):
        standalone_runtime.run(game,[library])
    assert json.loads((library/'healthy/mod.json').read_text())['enabled']


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
