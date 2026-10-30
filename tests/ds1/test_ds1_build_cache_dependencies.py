"""Cache only the builder engine and each mod's observed repository inputs."""
import json
from pathlib import Path
import pytest

from core import build_dependencies,script_mods
from plugins.ds1 import script_worker,tweak_mods
from test_ds1_tweak_recovery import game


def mod(library,name,source):
    folder = library/name;(folder/'script').mkdir(parents=True)
    (folder/'mod.json').write_text(json.dumps({'name':name,'script':{'version':1}}))
    (folder/'script/__init__.py').write_text('')
    (folder/'script/tweak.py').write_text(source)
    return folder


def build(folder,game,library):
    return script_mods.build(folder,tweak_mods.BuildContext({},game,library),allowed_roots=tweak_mods.ALLOWED_ROOTS)


def record(folder):
    return json.loads((folder/script_mods.MANIFEST_FILE).read_text())['build']


def test_used_helper_change_rebuilds_its_consumer_and_preserves_unrelated_cache(game,monkeypatch):
    root,library,_built = game
    first = mod(library,'first','from plugins.ds1 import load_bands\n'
        'def build(settings,context):\n    return {"native/value.txt":str(load_bands.MAX_BANDS)}\n')
    second = mod(library,'second','def build(settings,context):\n    return {"native/value.txt":"unchanged"}\n')
    assert not build(first,root,library).get('cached')
    assert not build(second,root,library).get('cached')
    assert 'plugins/ds1/load_bands.py' in record(first)['inputs']['python']
    assert 'python' not in record(second)['inputs']
    assert build(first,root,library)['cached'] and build(second,root,library)['cached']
    previous = tweak_mods.build_fingerprint(first,produced=True)
    original = build_dependencies.fingerprint
    monkeypatch.setattr(build_dependencies,'fingerprint',lambda path: 'changed helper' if path=='plugins/ds1/load_bands.py' else original(path))
    assert tweak_mods.build_fingerprint(first) != previous
    assert tweak_mods.build_fingerprint(first,produced=True) == previous
    assert not build(first,root,library).get('cached')
    assert build(second,root,library)['cached']


def test_used_schema_changes_invalidate_the_reader_without_running_code_on_a_hit(game,monkeypatch):
    root,library,_built = game
    folder = mod(library,'reader','from plugins.ds1.formats import schema\n'
        'def build(settings,context):\n    return {"native/value.txt":str(schema("Magic")["size"])}\n')
    build(folder,root,library)
    inputs = record(folder)['inputs']['python']
    metadata = next(path for path in inputs if path.startswith('plugins/ds1/metadata/'))
    evaluate = script_worker.evaluate
    def forbidden(*_):
        raise AssertionError('A cache hit executed builder code')
    monkeypatch.setattr(script_worker,'evaluate',forbidden)
    assert build(folder,root,library)['cached']
    monkeypatch.setattr(script_worker,'evaluate',evaluate)
    original = build_dependencies.fingerprint
    monkeypatch.setattr(build_dependencies,'fingerprint',lambda path:'changed schema' if path==metadata else original(path))
    assert not build(folder,root,library).get('cached')


def test_installer_and_archive_engine_changes_do_not_change_the_script_engine_identity(game,monkeypatch):
    from plugins.ds1 import mod_loader
    root,library,_built = game
    folder = mod(library,'stable','def build(settings,context):\n    return {"native/value.txt":"safe"}\n')
    tweak_mods._script_compiler_revision.cache_clear()
    tweak_mods._installation_revision.cache_clear()
    before = tweak_mods._script_compiler_revision()
    build(folder,root,library)
    installed = tweak_mods.build_fingerprint(folder,produced=True)
    original = Path.read_bytes
    with monkeypatch.context() as changes:
        changes.setattr(Path,'read_bytes',lambda path:original(path)+b'\n# unrelated installer change' if path==Path(tweak_mods.__file__) else original(path))
        changes.setattr(mod_loader,'_composition_revision',lambda:b'unrelated archive engine change')
        tweak_mods._script_compiler_revision.cache_clear()
        tweak_mods._installation_revision.cache_clear()
        assert tweak_mods._script_compiler_revision() == before
        assert tweak_mods.build_fingerprint(folder) != installed
        assert build(folder,root,library)['cached']
    tweak_mods._script_compiler_revision.cache_clear()
    tweak_mods._installation_revision.cache_clear()


def test_incomplete_dependency_record_builds_but_never_reuses_stale_outputs(game):
    root,library,_built = game
    folder = mod(library,'simple','def build(settings,context):\n    return {"native/value.txt":"safe"}\n')
    build(folder,root,library)
    path = folder/script_mods.MANIFEST_FILE
    manifest = json.loads(path.read_text());manifest['build']['cacheable'] = False
    path.write_text(json.dumps(manifest))
    assert not build(folder,root,library).get('cached')
    assert (folder/'native/value.txt').read_text() == 'safe'
    assert build(folder,root,library)['cached']


def test_bad_optional_dependency_cache_does_not_disable_the_mod_or_hide_its_outputs(game):
    root,library,_built = game
    folder = mod(library,'simple','def build(settings,context):\n    return {"native/value.txt":"safe"}\n')
    build(folder,root,library)
    before = tweak_mods.build_fingerprint(folder,produced=True)
    path = folder/script_mods.MANIFEST_FILE
    manifest = json.loads(path.read_text())
    manifest['build']['inputs']['python'] = {'../outside.txt':'0'*64}
    path.write_text(json.dumps(manifest))
    assert tweak_mods.build_fingerprint(folder) != before
    assert not build(folder,root,library).get('cached')
    assert (folder/'native/value.txt').read_text() == 'safe'


def test_contributor_set_and_source_changes_invalidate_without_importing_on_a_hit(game,monkeypatch):
    root,library,_built = game
    reader = mod(library,'reader','def build(settings,context):\n'
        '    return {"native/value.txt":str(sum(module.VALUE for _,module in context.contributors("contribution")))}\n')
    first = mod(library,'first','def build(settings,context): return {}\n')
    (first/'script/contribution.py').write_text('VALUE=4\n')
    def run(enabled):
        return script_mods.build(reader,tweak_mods.BuildContext(enabled,root,library),allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert not run({'first':first}).get('cached')
    assert (reader/'native/value.txt').read_text() == '4'
    with monkeypatch.context() as changes:
        changes.setattr(script_mods,'load_script',lambda *_:pytest.fail('Cache replay imported a provider'))
        assert run({'first':first})['cached']
    second = mod(library,'second','def build(settings,context): return {}\n')
    (second/'script/contribution.py').write_text('VALUE=7\n')
    assert not run({'first':first,'second':second}).get('cached')
    assert (reader/'native/value.txt').read_text() == '11'
    (first/'script/contribution.py').write_text('VALUE=5\n')
    assert not run({'first':first,'second':second}).get('cached')
    assert (reader/'native/value.txt').read_text() == '12'
    assert not run({}).get('cached')
    assert (reader/'native/value.txt').read_text() == '0'
    assert run({})['cached']


def test_bad_optional_contributor_is_attributed_to_provider_not_consumer(game):
    from core.mod_builds import ModBuildError
    root,library,_built = game
    reader = mod(library,'reader','def build(settings,context):\n'
        '    context.contributors("contribution")\n    return {}\n')
    provider = mod(library,'bad','def build(settings,context): return {}\n')
    (provider/'script/contribution.py').write_text('raise ValueError("broken provider")\n')
    with pytest.raises(ModBuildError,match='broken provider') as caught:
        script_mods.build(reader,tweak_mods.BuildContext({'bad':provider},root,library),allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert caught.value.folders == (provider.resolve(),)


def test_own_package_module_reference_does_not_reset_executing_build_state(game):
    root,library,_built = game
    reader = mod(library,'reader','from . import STATE\ndef build(settings,context):\n'
        '    STATE.append(7)\n    package=context.module("self","__init__")\n'
        '    return {"native/value.txt":str(package.STATE)}\n')
    (reader/'script/__init__.py').write_text('STATE=[]\n')
    script_mods.build(reader,tweak_mods.BuildContext({'self':reader},root,library),allowed_roots=tweak_mods.ALLOWED_ROOTS)
    assert (reader/'native/value.txt').read_text() == '[7]'
