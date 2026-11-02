"""Native toggles reuse unchanged data and verified installed menu recipes."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_ds1_tweak_save_rebuild import game, library  # noqa: F401


def test_direct_data_edit_stays_pending_until_its_bytes_are_installed(game, library, monkeypatch):
    from plugins.ds1 import tweak_mods
    from plugins.ds1.mod_support import Ds1ModAdapter
    from plugins.ds1.store import RELATIVE
    from plugins.ds1.formats import ItemDocument
    from ds1_fixture import make_archive
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    (game/RELATIVE).parent.mkdir(parents=True)
    original=make_archive()
    (game/RELATIVE).write_bytes(original)
    folder=library/'Data'
    (folder/RELATIVE).parent.mkdir(parents=True)
    (folder/'mod.json').write_text(json.dumps({'name':'Data','enabled':True,'order':30}))
    (folder/RELATIVE).write_bytes(make_archive(field_values={'EquipParamGoods':{100:{'sellValue':17}}}))
    adapter=Ds1ModAdapter();adapter.attach_context(library_root=library)
    paths=[library/'Alpha',library/'Beta',folder]
    adapter.activate(paths,game)
    from plugins.ds1 import runtime_mods
    with monkeypatch.context() as check:
        check.setattr(runtime_mods,'inspect',lambda *_:pytest.fail('Freshness reparsed a committed native module'))
        assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert ItemDocument((game/RELATIVE).read_bytes()).value('EquipParamGoods',100,'sellValue')==17
    (folder/RELATIVE).write_bytes(make_archive(field_values={'EquipParamGoods':{100:{'sellValue':18}}}))
    assert tweak_mods.needs_rebuild(game,library)['needed']
    adapter.activate(paths,game)
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert ItemDocument((game/RELATIVE).read_bytes()).value('EquipParamGoods',100,'sellValue')==18
    adapter._report_path().unlink()
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    metadata=json.loads((folder/'mod.json').read_text());metadata['enabled']=False
    (folder/'mod.json').write_text(json.dumps(metadata))
    assert tweak_mods.needs_rebuild(game,library)['needed']
    adapter.activate(paths[:-1],game)
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert (game/RELATIVE).read_bytes()==original


def test_freshness_reads_shared_python_inputs_once_per_scan_and_checks_them_next_time(game,library,monkeypatch):
    from plugins.ds1 import tweak_mods
    from core import build_dependencies
    monkeypatch.setenv(tweak_mods.MODS_ENV,str(library))
    for name in ('Alpha','Beta'):
        path=library/name/'script/tweak.py'
        path.write_text('from plugins.ds1 import formats\n'+path.read_text())
    tweak_mods.apply(game,library)
    original=build_dependencies.fingerprint
    calls=[]
    changed={'value':False}
    def fingerprint(name):
        calls.append(name)
        return '0'*64 if changed['value'] and name=='plugins/ds1/formats.py' else original(name)
    monkeypatch.setattr(build_dependencies,'fingerprint',fingerprint)
    assert not tweak_mods.needs_rebuild(game,library)['needed']
    assert calls.count('plugins/ds1/formats.py')==1
    calls.clear();changed['value']=True
    assert tweak_mods.needs_rebuild(game,library)['stale']==['alpha','beta']
    assert calls.count('plugins/ds1/formats.py')==1
    changed['value']=False
    for _ in range(2):
        calls.clear()
        tweak_mods.build_specs(library,game)
        assert calls.count('plugins/ds1/formats.py')==1


def test_menu_recipe_tracks_its_codec_without_global_editor_revision(tmp_path, monkeypatch):
    from plugins.ds1 import tweak_mods, menu_layout, menu_scripts, formats, esd, mod_loader
    for module in (menu_layout, menu_scripts, formats, esd):
        source = tmp_path / (module.__name__.replace('.', '_') + '.py')
        source.write_bytes(b'first codec')
        monkeypatch.setattr(module, '__file__', str(source))
    specs = [{'owner': 'UI', 'nodes': [], 'moves': []}]
    identity = tweak_mods._menu_identity(b'original', specs, tweak_mods.LAYOUT)
    assert identity is not None
    monkeypatch.setattr(mod_loader, '_composition_revision', lambda: b'unrelated editor change')
    assert tweak_mods._menu_identity(b'original', specs, tweak_mods.LAYOUT) == identity
    Path(menu_layout.__file__).write_bytes(b'changed layout codec')
    assert tweak_mods._menu_identity(b'original', specs, tweak_mods.LAYOUT) != identity
    assert tweak_mods._menu_identity(b'changed original', specs, tweak_mods.LAYOUT) != identity


def test_inserted_menu_blobs_preserve_existing_nodes_and_roundtrip():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_ds1_menu_layout import drb
    from plugins.ds1.menu_layout import Drb
    layout = Drb(drb())
    def blobs(parsed):
        return {(dialog, node.name): (parsed._blob('SHAP', 'SHPR', node.shape),
                                     parsed._blob('CTRL', 'CTPR', node.control))
                for dialog in parsed.dialogs() for node in parsed.nodes(dialog)}
    original = blobs(layout)
    for index in range(80):
        layout.add_text('data_simple_arms', f'added_{index}', 'text_param_receive', index, 16,
                        before='text_receive_name' if index % 2 else None)
    current = blobs(layout)
    assert all(current[key] == value for key, value in original.items())
    assert blobs(Drb(layout.to_bytes())) == current

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
        {'name':'Iframe Display', 'path':str(native), 'enabled':True}, {'name':'Data', 'path':str(data), 'enabled':True}])
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=library)
    monkeypatch.setattr(adapter, '_report_path', lambda: tmp_path/'report.json')
    ordered = adapter._ordered_mods([data])
    adapter._save_report(game, ordered, [], installed=True, menu_inputs=[])
    assert adapter._ordered_mods([native, data]) == ordered
    monkeypatch.setattr(tweak_mods, 'ensure_game_closed', lambda: None)
    monkeypatch.setattr(tweak_mods, 'locked', lambda root: nullcontext())
    monkeypatch.setattr(tweak_mods, 'prepare', lambda *args, **kwargs: {'files':[], 'runtime':{}})
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
    monkeypatch.setattr(tweak_mods, '_menu_baseline', lambda *_: True)
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
    # An unsupported optional cache representation must never become a build
    # failure, nor count as a matching recipe when both identities are absent.
    assert tweak_mods._compose_menu(original, [{'internal':object()}], managed, tmp_path,
                                   current=installed, manifest={**manifest,'inputs':None}) == b'new menu'
    assert len(calls) == 7


def test_prepared_texture_order_invalidates_only_the_installed_pair_reuse(tmp_path,monkeypatch):
    """A fresh layout cannot reuse a TPF ordered for the previous TEXI table."""
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from drb_fixture import make_drb, make_dcx, sprite_shape
    from tpf_fixture import make_tpf, make_dds_rgba
    from ds1_fixture import make_archive
    from plugins.ds1 import mod_loader,mod_support,tweak_mods,texture_packs,formats,deployment
    from plugins.ds1.formats import ItemDocument
    from plugins.ds1.store import RELATIVE
    game,library = tmp_path/'game',tmp_path/'library'
    folder,native = library/'textures',library/'native-only'
    for root in (game,folder):
        (root/RELATIVE).parent.mkdir(parents=True)
        (root/RELATIVE).write_bytes(make_archive())
        (root/'menu').mkdir(exist_ok=True)
    native.mkdir()
    for root in (folder,native):
        (root/'mod.json').write_text(json.dumps({'name':root.name,'id':root.name,'enabled':True}))
    document = ItemDocument((folder/RELATIVE).read_bytes())
    document.edit('EquipParamGoods',100,'sellValue',12)
    (folder/RELATIVE).write_bytes(document.export())
    images = {name:make_dds_rgba(2,2,[color]*4) for name,color in
              [('Base',(255,0,0,255)),('Warp',(0,0,255,255)),('Estus',(0,255,0,255))]}
    stock = make_dcx(make_tpf([(name,images[name]) for name in ('Base','Warp')]))
    added = make_dcx(make_tpf([(name,images[name]) for name in ('Base','Warp','Estus')]))
    main,split = Path('menu/menu.tpf.dcx'),Path('menu/menu_3.tpf.dcx')
    (game/main).write_bytes(stock)
    (game/split).write_bytes(stock)
    (folder/split).write_bytes(added)
    layout = {'value':make_dcx(make_drb(['Base','Warp'],{}))}
    tweak_mods.LAYOUT.live(game).write_bytes(layout['value'])
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    def prepare(*args,**kwargs):
        return {'runtime':{},'files':[{'managed':tweak_mods.LAYOUT,'before':tweak_mods.LAYOUT.live(game).read_bytes(),
                          'after':layout['value']}]}
    monkeypatch.setattr(tweak_mods,'prepare',prepare)
    monkeypatch.setattr(tweak_mods,'commit',lambda root,plan:tweak_mods.LAYOUT.live(root).write_bytes(plan['files'][0]['after']))
    adapter = mod_support.Ds1ModAdapter()
    adapter.attach_context(library_root=library)
    monkeypatch.setattr(adapter,'_report_path',lambda:tmp_path/'report.json')
    # Count actual archive composition, not inexpensive cache lookup calls.
    expensive = []
    real_compose = mod_loader.compose
    def compose(*args,**kwargs):
        expensive.append(True)
        return real_compose(*args,**kwargs)
    monkeypatch.setattr(mod_loader,'compose',compose)
    adapter.activate([folder],game)
    count = len(expensive)
    report_before = json.loads((tmp_path/'report.json').read_text())
    assert report_before['installedOrder'] == [str(folder.resolve())]
    layout['value'] = make_dcx(make_drb(['Base','Estus','Warp'],{}))
    result = adapter.activate([folder,native],game)
    assert not result['timings']['reusedInstalledData']
    assert len(expensive) == count, 'Unchanged archive outputs must come from their existing cache'
    expected = texture_packs.menu_texture_names(tweak_mods.LAYOUT.live(game).read_bytes())
    _,rows = texture_packs.read(formats.inflate((game/main).read_bytes()))
    assert [row.name for row in rows][:len(expected)] == expected == ['Base','Estus','Warp']
    assert rows[1].data == images['Estus']
    assert ItemDocument((game/RELATIVE).read_bytes()).value('EquipParamGoods',100,'sellValue') == 12
    assert deployment._backup_path(game,main).read_bytes() == stock
    # Non-TEXI layout changes leave this verified pair reusable.
    layout['value'] = make_dcx(make_drb(expected,{'Changed panel':[('sprite',sprite_shape((0,0,2,2),(0,0,2,2),1))]}))
    monkeypatch.setattr(mod_loader,'compose_installed',lambda *args,**kwargs:pytest.fail('Unchanged TEXI must retain fast native/layout-only reuse'))
    assert adapter.activate([folder,native],game)['timings']['reusedInstalledData']
    # The derived main atlas is a dependency even when no mod carries it.
    (game/main).write_bytes(stock)
    assert adapter._read_report(game,adapter._ordered_mods([folder,native])) is None


def test_standalone_startup_uses_the_same_prepared_layout_texture_pair(tmp_path,monkeypatch):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from drb_fixture import make_drb,make_dcx
    from tpf_fixture import make_tpf,make_dds_rgba
    from plugins.ds1 import standalone_runtime,tweak_mods,texture_packs,formats
    game,library = tmp_path/'game',tmp_path/'library'
    folder = library/'atlas'
    for root in (game,folder):
        (root/'menu').mkdir(parents=True)
    (folder/'mod.json').write_text(json.dumps({'id':'atlas','name':'Atlas','enabled':True}))
    (folder/'layout').mkdir()
    component = folder/'layout/atlas.json'
    component.write_text('{}')
    images = {name:make_dds_rgba(2,2,[color]*4) for name,color in
              [('Base',(255,0,0,255)),('Warp',(0,0,255,255)),('Estus',(0,255,0,255))]}
    stock = make_dcx(make_tpf([(name,images[name]) for name in ('Base','Warp')]))
    (game/'menu/menu.tpf.dcx').write_bytes(stock)
    (game/'menu/menu_3.tpf.dcx').write_bytes(stock)
    (folder/'menu/menu_3.tpf.dcx').write_bytes(make_dcx(make_tpf(list(images.items()))))
    original = make_dcx(make_drb(['Base','Warp'],{}))
    managed = tweak_mods.Managed('menu/menu.drb.dcx','fixture menu',1024*1024,lambda value:value==original)
    managed.live(game).write_bytes(original)
    monkeypatch.setattr(tweak_mods,'LAYOUT',managed)
    monkeypatch.setattr(tweak_mods,'ensure_game_closed',lambda:None)
    wanted = [make_dcx(make_drb(['Base','Estus','Warp'],{}))]
    monkeypatch.setattr(standalone_runtime,'_specs',lambda rows,kind,validate:
        [{'owner':'Atlas','folder':str(folder),'nodes':[],'moves':[]}] if kind=='layout' else [])
    monkeypatch.setattr(tweak_mods,'_compose_menu',lambda *args,**kwargs:wanted[0])
    for index in range(2):
        if index:
            wanted[0] = make_dcx(make_drb(['Estus','Warp','Base'],{}))
            component.write_text('{"changed":true}')
        report = standalone_runtime.run(game,[library])
        assert report['loaded'] == ['atlas'] and not report['disabled']
        expected = texture_packs.menu_texture_names(managed.live(game).read_bytes())
        _,textures = texture_packs.read(formats.inflate((game/'menu/menu.tpf.dcx').read_bytes()))
        assert [texture.name for texture in textures] == expected
        assert textures[expected.index('Estus')].data == images['Estus']
        assert standalone_runtime.run(game,[library])['reused']

