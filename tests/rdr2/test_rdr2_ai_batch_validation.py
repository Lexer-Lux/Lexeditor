"""AI batches validate before source creation, cache mutation or publication."""
import json
import threading
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from plugins.rdr2 import server as s
from test_rdr2_catalog_numeric_validation import fixture, snapshot

XML = b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>\n<Root><!--keep--><Amount value="1"/><Enabled>true</Enabled><Mode>A</Mode><Mode>B</Mode><Opaque keep="yes">source</Opaque></Root>'
FIRST = {'path': [1], 'kind': 'attr', 'value': '0.125'}


@pytest.fixture
def ai(fixture, monkeypatch):
    root, _ = fixture
    path = s.data_file_path(s.PED_PERCEPTION_FILE, 'mine')
    source = root / 'vanilla.meta'
    source.write_bytes(XML)
    monkeypatch.setattr(s, 'VANILLA_PED_PERCEPTION_FILE', source)
    install = s.ds_dir('mine') / 'install.xml'
    install.write_text('<Install><!--mapping comment--><Resources/></Install>')
    return root, path, source, install


BAD = [None, {}, False, '', [None], [{}], [dict(FIRST, extra=1)],
       [dict(FIRST, path=[])], [dict(FIRST, path={})], [dict(FIRST, path=[0])],
       [dict(FIRST, path=[-1])], [dict(FIRST, path=[1.5])], [dict(FIRST, path=[True])],
       [dict(FIRST, path=['1'])], [dict(FIRST, path=[99])], [FIRST],
       [dict(FIRST, kind='text')], [{'path': [5], 'kind': 'text', 'value': 'change'}]]
BAD += [[dict(FIRST, path=[2], kind='text', value='maybe')]]
BAD += [[dict(FIRST, value=v)] for v in [None, True, [], {}, '', 'NaN', 'Inf', '1_0', '1e999']]


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('bad', BAD)
def test_invalid_later_edit_preserves_absent_existing_source_and_cache(ai, bad, existing):
    root, path, source, _ = ai
    entry = None
    if existing:
        path.parent.mkdir(parents=True)
        path.write_bytes(source.read_bytes())
        entry = s.load_file(s.PED_PERCEPTION_FILE)
        original_root = entry['root']
    before = snapshot(root)
    with pytest.raises(ValueError):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST, *bad] if isinstance(bad, list) else bad)
    assert snapshot(root) == before
    if entry:
        assert entry['root'] is original_root
        assert ET.tostring(original_root) == ET.tostring(s.parse_with_comments(source))


@pytest.mark.parametrize('existing,failure', [(False, 1), (False, 2), (True, 1), (True, 2), (True, 3)])
@pytest.mark.parametrize('staging', [False, True])
def test_failed_publication_restores_mapping_file_backup_and_cache(ai, monkeypatch, existing, failure, staging):
    root, path, source, _ = ai
    entry = None
    if existing:
        path.parent.mkdir(parents=True)
        path.write_bytes(source.read_bytes())
        entry = s.load_file(s.PED_PERCEPTION_FILE)
    before = snapshot(root)
    original_replace = s.tempfile.NamedTemporaryFile if staging else s.os.replace
    calls = 0
    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == failure:
            raise OSError('injected AI publication failure')
        return original_replace(*args, **kwargs)
    monkeypatch.setattr(s.tempfile if staging else s.os, 'NamedTemporaryFile' if staging else 'replace', fail_once)
    with pytest.raises(OSError, match='injected'):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST])
    assert snapshot(root) == before
    if entry:
        assert entry['root'].find('Amount').get('value') == '1'
    assert not list(root.rglob('*.tmp'))
    assert not list(root.rglob('.lexeditor-save-recovery-*'))


@pytest.mark.parametrize('existing', [False, True])
def test_real_http_rejects_then_saves_exact_values_and_comment_paths(ai, existing):
    root, path, source, install = ai
    if existing:
        path.parent.mkdir(parents=True)
        path.write_bytes(source.read_bytes())
    assert s.get_ai_file(s.PED_PERCEPTION_FILE)['fields'][0]['path'] == [1]
    http = s.create_server(0)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    def post(edits):
        return Request(f'http://127.0.0.1:{http.server_port}/api/ai/{s.PED_PERCEPTION_FILE}/save',
                       data=json.dumps({'edits': edits}).encode(), headers={'Content-Type': 'application/json'})
    try:
        before = snapshot(root)
        with pytest.raises(HTTPError) as error:
            urlopen(post([FIRST, dict(FIRST, path=[-1])]), timeout=5)
        assert error.value.code == 400
        assert snapshot(root) == before
        edits = [dict(FIRST, value='9007199254740993'), {'path': [2], 'kind': 'text', 'value': 'false'},
                 {'path': [3], 'kind': 'text', 'value': 'B'}]
        assert json.load(urlopen(post(edits), timeout=5))['saved'] == 3
        s._files.clear()
        rows = s.get_ai_file(s.PED_PERCEPTION_FILE)['fields']
        assert [r['value'] for r in rows[:3]] == ['9007199254740993', 'false', 'B']
        assert path.read_bytes().startswith(b'\xef\xbb\xbf<?xml')
        assert b'<!--keep-->' in path.read_bytes()
        assert b'<!--mapping comment-->' in install.read_bytes()
        assert ET.parse(install).find('.//GamePath').text == s.PED_PERCEPTION_GAME_PATH
        assert source.read_bytes() == XML
        if existing:
            assert path.with_suffix(path.suffix + '.bak').read_bytes() == XML
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


@pytest.mark.parametrize('loader,match', [('<Install/>', 'Resources'), ('<broken', 'Invalid install')])
def test_empty_readonly_and_invalid_loader_do_not_create_source(ai, loader, match):
    root, path, _, install = ai
    before = snapshot(root)
    assert s.apply_ai_edits(s.PED_PERCEPTION_FILE, []) == 0
    s.DATASETS['mine']['readonly'] = True
    with pytest.raises(ValueError, match='read-only'):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST])
    assert snapshot(root) == before
    s.DATASETS['mine']['readonly'] = False
    install.write_text(loader)
    before = snapshot(root)
    with pytest.raises(ValueError, match=match):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST])
    assert snapshot(root) == before
    assert not path.exists()


@pytest.mark.parametrize('existing', [False, True])
def test_loader_changed_after_preparation_is_preserved_without_ai_publication(ai, monkeypatch, existing):
    root, path, source, install = ai
    if existing:
        path.parent.mkdir(parents=True)
        path.write_bytes(source.read_bytes())
    before = snapshot(root)
    commit = s._commit_file_outputs
    external = b'<Install><Resources/><External/></Install>'
    def changed(outputs, label, **kwargs):
        install.write_bytes(external)
        return commit(outputs, label, **kwargs)
    monkeypatch.setattr(s, '_commit_file_outputs', changed)
    with pytest.raises(ValueError, match='changed since preparation'):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST])
    before[str(install.relative_to(root))] = external
    assert snapshot(root) == before


@pytest.mark.parametrize('existing', [False, True])
def test_validate_only_checks_complete_batch_and_loader_without_publication(ai, existing):
    root, path, source, install = ai
    entry = None
    if existing:
        path.parent.mkdir(parents=True)
        path.write_bytes(source.read_bytes())
        entry = s.load_file(s.PED_PERCEPTION_FILE)
        original_root = entry['root']
    before = snapshot(root)
    assert s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST], validate_only=True) == 1
    with pytest.raises(ValueError):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST, dict(FIRST, path=[-1])], validate_only=True)
    assert snapshot(root) == before
    if entry:
        assert entry['root'] is original_root
    install.write_text('<Install/>')
    before = snapshot(root)
    with pytest.raises(ValueError, match='Resources'):
        s.apply_ai_edits(s.PED_PERCEPTION_FILE, [FIRST], validate_only=True)
    assert snapshot(root) == before


def test_source_enum_choices_remain_valid_when_two_rows_swap(ai):
    _, path, _, _ = ai
    assert s.apply_ai_edits(s.PED_PERCEPTION_FILE, [
        {'path': [3], 'kind': 'text', 'value': 'B'},
        {'path': [4], 'kind': 'text', 'value': 'A'},
    ]) == 2
    assert [node.text for node in s.parse_with_comments(path).findall('Mode')] == ['B', 'A']
