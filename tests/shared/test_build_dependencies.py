"""Observe imports and data reads without treating worker setup as mod input."""
import builtins
import importlib
from pathlib import Path
import sys

import pytest

from core import build_dependencies


@pytest.fixture
def engine(tmp_path,monkeypatch):
    root = tmp_path/'engine';package = root/'dependency_fixture'
    package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    (package/'base.py').write_text('VALUE = 17\n')
    (package/'helper.json').write_text('{"extra":3}')
    (package/'helper.py').write_text(
        'from pathlib import Path\nimport json\nfrom .base import VALUE\n'
        'EXTRA = json.loads(Path(__file__).with_suffix(".json").read_text())["extra"]\n'
        'def result(): return VALUE+EXTRA\n')
    (package/'unused.py').write_text('VALUE = 99\n')
    script = tmp_path/'mod/script/tweak.py';script.parent.mkdir(parents=True)
    monkeypatch.syspath_prepend(str(root))
    yield root,script,package
    for name in list(sys.modules):
        if name == 'dependency_fixture' or name.startswith('dependency_fixture.'):
            del sys.modules[name]


def execute(script,source):
    scope = {'__file__':str(script)}
    exec(compile(source,str(script),'exec'),scope)
    return scope


def test_preloaded_helpers_keep_transitive_imports_and_metadata_without_unrelated_inputs(engine):
    root,script,package = engine
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        importlib.import_module('dependency_fixture.helper')
        importlib.import_module('dependency_fixture.unused')
        assert execute(script,'from dependency_fixture.helper import result\nvalue=result()')['value'] == 20
    inputs = observed.inputs()
    assert observed.complete
    assert {'dependency_fixture/helper.py','dependency_fixture/base.py','dependency_fixture/helper.json'} <= inputs.keys()
    assert 'dependency_fixture/unused.py' not in inputs
    before = inputs['dependency_fixture/base.py']
    (package/'base.py').write_text('VALUE = 19\n')
    assert build_dependencies.fingerprint('dependency_fixture/base.py',root) != before


def test_importlib_imports_from_mod_scripts_are_roots(engine):
    root,script,_package = engine
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        assert execute(script,'import importlib\nvalue=importlib.import_module("dependency_fixture.helper").result()')['value'] == 20
    assert 'dependency_fixture/helper.py' in observed.inputs()


def test_optional_missing_repository_file_tracks_its_absence(engine):
    root,script,_package = engine
    missing = root/'optional.json'
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        execute(script,f'from pathlib import Path\ntry: Path({str(missing)!r}).read_text()\nexcept FileNotFoundError: pass')
    assert observed.inputs() == {'optional.json':None}
    missing.write_text('{}')
    assert build_dependencies.fingerprint('optional.json',root) is not None


def test_observer_limits_disable_reuse_without_preventing_the_build(engine,monkeypatch):
    root,script,_package = engine
    monkeypatch.setattr(build_dependencies,'MAX_INPUTS',1)
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        assert execute(script,'from dependency_fixture.helper import result\nvalue=result()')['value'] == 20
    assert not observed.complete


def test_hash_failure_disables_reuse_and_import_hooks_are_restored(engine,monkeypatch):
    root,script,_package = engine
    previous = builtins.__import__,importlib.import_module
    def unavailable(*_):
        raise PermissionError('Optional dependency hashing unavailable')
    monkeypatch.setattr(build_dependencies,'fingerprint',unavailable)
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        assert execute(script,'from dependency_fixture.helper import result\nvalue=result()')['value'] == 20
    assert not observed.complete
    assert (builtins.__import__,importlib.import_module) == previous


def test_manifest_paths_cannot_select_files_outside_the_engine(engine,tmp_path):
    root,_script,_package = engine
    with pytest.raises(ValueError):
        build_dependencies.fingerprint('../outside.txt',root)


def test_import_observation_does_not_repeat_module_attribute_side_effects(engine):
    root,script,package = engine
    (package/'lazy.py').write_text('calls=0\ndef __getattr__(key):\n'
        '    global calls\n    if key=="VALUE":\n        calls+=1\n        return 7\n'
        '    raise AttributeError(key)\n')
    statement = 'from dependency_fixture.lazy import VALUE\n'
    execute(script,statement)
    baseline = sys.modules['dependency_fixture.lazy'].calls
    del sys.modules['dependency_fixture.lazy']
    with build_dependencies.BuildDependencies([script.parent],root=root):
        assert execute(script,statement)['VALUE'] == 7
    assert sys.modules['dependency_fixture.lazy'].calls == baseline


def test_python_package_inference_still_works_when_observation_cannot_resolve_it(engine):
    root,script,_package = engine
    importlib.import_module('dependency_fixture')
    with build_dependencies.BuildDependencies([script.parent],root=root) as observed:
        module = builtins.__import__('base',{'__name__':'dependency_fixture.helper','__file__':str(script)},None,('VALUE',),1)
        assert module.VALUE == 17
    assert not observed.complete
