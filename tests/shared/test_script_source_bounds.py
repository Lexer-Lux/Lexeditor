"""Hostile source/cache trees cannot force unbounded discovery or JSON reads."""
import json
from pathlib import Path
import pytest

from core import script_mods


@pytest.fixture(autouse=True)
def supported_pathlib(monkeypatch):
    # The desktop's Python 3.10 has no Path.is_junction. Keep every source
    # discovery/import boundary covered on that API surface even on newer CI.
    monkeypatch.delattr(Path,'is_junction',raising=False)


def project(tmp_path):
    (tmp_path/'script').mkdir()
    (tmp_path/'script/tweak.py').write_text('def build(settings,context): return {}')
    (tmp_path/'mod.json').write_text(json.dumps({'name':'Example','script':{'version':1}}))
    return tmp_path


def test_private_directories_are_pruned_before_scanning(tmp_path,monkeypatch):
    root = project(tmp_path)
    for name in ('.git','__pycache__'):
        (root/'script'/name).mkdir()
    original = script_mods.os.scandir
    def guarded(path):
        assert Path(path).name not in ('.git','__pycache__')
        return original(path)
    monkeypatch.setattr(script_mods.os,'scandir',guarded)
    assert script_mods.consumed_files(root) == [Path('mod.json'),Path('script/tweak.py')]


def test_node_limit_fails_instead_of_caching_an_incomplete_source_set(tmp_path,monkeypatch):
    root = project(tmp_path)
    (root/'script/second.py').write_text('')
    monkeypatch.setattr(script_mods,'MAX_SOURCE_NODES',1)
    with pytest.raises(script_mods.ScriptModError,match='too many entries'):
        script_mods.source_fingerprint(root)


def test_metadata_size_and_recursion_fail_as_owned_mod_errors(tmp_path,monkeypatch):
    root = project(tmp_path)
    path = root/script_mods.MANIFEST_FILE
    monkeypatch.setattr(script_mods,'MAX_METADATA_BYTES',32)
    path.write_bytes(b' '*33)
    with pytest.raises(script_mods.ScriptModError,match='metadata limit'):
        script_mods._read_json(path)
    monkeypatch.setattr(script_mods,'MAX_METADATA_BYTES',8192)
    path.write_text('{}')
    def exhausted(*_):
        raise RecursionError('nested metadata')
    monkeypatch.setattr(script_mods.json,'loads',exhausted)
    with pytest.raises(script_mods.ScriptModError,match='not readable JSON'):
        script_mods._read_json(path)


def test_source_size_limits_do_not_return_reusable_partial_hashes(tmp_path,monkeypatch):
    root = project(tmp_path)
    monkeypatch.setattr(script_mods,'MAX_SOURCE_BYTES',4)
    with pytest.raises(script_mods.ScriptModError,match='size limit'):
        script_mods.source_fingerprint(root)
    monkeypatch.setattr(script_mods,'MAX_SOURCE_BYTES',1024)
    monkeypatch.setattr(script_mods,'MAX_SOURCE_TOTAL',4)
    with pytest.raises(script_mods.ScriptModError,match='size limit'):
        script_mods.source_fingerprint(root)


def test_non_object_metadata_has_actionable_error(tmp_path):
    root = project(tmp_path)
    (root/'mod.json').write_text('[]')
    with pytest.raises(script_mods.ScriptModError,match='must be an object'):
        script_mods.source_fingerprint(root)


def test_import_clears_only_expected_bytecode_without_recursive_cache_walk(tmp_path,monkeypatch):
    root = project(tmp_path)
    (root/'script/__init__.py').write_text('')
    (root/'script/__pycache__').mkdir()
    unrelated = root/'script/__pycache__/unrelated.pyc'
    unrelated.write_bytes(b'private')
    def forbidden(*_):
        pytest.fail('Import recursively walked the private cache')
    monkeypatch.setattr(Path,'rglob',forbidden)
    assert script_mods.load_script(root).build({},None) == {}
    assert unrelated.read_bytes() == b'private'


def test_windows_utf8_bom_metadata_is_still_recognized_as_a_script_mod(tmp_path):
    root = project(tmp_path)
    path = root/'mod.json'
    path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes())
    (root/script_mods.SCHEMA_FILE).write_bytes(b'\xef\xbb\xbf{"fields":[]}')
    (root/script_mods.VALUES_FILE).write_bytes(b'\xef\xbb\xbf{"values":{}}')
    assert script_mods.is_script_mod(root)
    assert script_mods.schema(root)['fields']==[]
    assert script_mods.values(root)=={}
