"""Production HTTP save/reopen and fault injection for the weight/Hext pair."""
from hashlib import sha256
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import encounter_chances as chances, paths, project_files, server, world_map, world_names
from test_ff8_encounter_rules import _synthetic_wmset, GROUPS


@pytest.fixture
def service(tmp_path, monkeypatch):
    project, game = tmp_path/'mod', tmp_path/'game'
    project.mkdir()
    game.mkdir()
    (project/'mod.json').write_text('{"name":"Authored encounter fixture"}', encoding='utf-8')
    exe = b'authored executable signature fixture'
    (game/'FF8_EN.exe').write_bytes(exe)
    monkeypatch.setattr(chances, 'SUPPORTED_EXE_SHA256', sha256(exe).hexdigest())
    monkeypatch.setattr(paths, 'PROJECT_ROOT', project)
    monkeypatch.setattr(paths, 'DIRECT_ROOT', project/'direct')
    monkeypatch.setattr(paths, 'GAME_ROOT', game)
    monkeypatch.delenv('LEXEDITOR_MOD_READ_ONLY', raising=False)
    baseline = tmp_path/'wmsetus.obj'
    baseline.write_bytes(_synthetic_wmset())
    monkeypatch.setattr(world_map, 'ensure_baseline', lambda: baseline)
    rail = tmp_path/'rail.obj'
    rail.write_bytes(b'authored rail fixture')
    monkeypatch.setattr(world_map, 'rail_source_path', lambda dataset='current': rail)
    monkeypatch.setattr(world_map, 'parse_rail', lambda data: {'tracks': []})
    monkeypatch.setattr(world_map.world_textures, 'rows', lambda dataset: {'textures': [], 'source': 'fixture', 'sha256': 'fixture'})
    monkeypatch.setattr(world_map.world_geometry, 'rows', lambda dataset: {'segments': [], 'source': 'fixture', 'sha256': 'fixture'})
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    def request(body=None, *, include_hash=True):
        url = f'http://127.0.0.1:{http.server_address[1]}/api/world-map'
        if body is None:
            req = Request(url)
        else:
            if include_hash:
                body = {'sha256': sha256(world_map.source_path().read_bytes()).hexdigest(), **body}
            req = Request(url+'/save', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    request.base_url = f'http://127.0.0.1:{http.server_address[1]}'
    yield project, baseline, request
    http.shutdown()
    http.server_close()
    thread.join(timeout=5)


def edit(group=0, weights=None):
    return {'kind': 'group', 'id': group, 'encounters': GROUPS[group],
            'initialOutcomes': weights if weights is not None else [256]+[0]*7}


def files(project):
    return {path.relative_to(project): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in project.rglob('*') if path.is_file()}


def test_http_save_read_merge_and_exact_default_restore(service):
    project, baseline, request = service
    assert request({'edits': [edit()]})[0] == 200
    status, payload = request()
    assert status == 200
    assert payload['groups'][0]['initialOutcomes'] == [256]+[0]*7
    assert payload['groups'][1]['initialOutcomes'] == list(chances.DEFAULT_OUTCOMES)
    assert request({'edits': [edit(2, [0]*7+[256])]})[0] == 200
    status, payload = request()
    assert payload['groups'][0]['initialOutcomes'] == [256]+[0]*7
    assert payload['groups'][2]['initialOutcomes'] == [0]*7+[256]
    patch = project/chances.HEXT_RELATIVE
    assert patch.read_text().count(' = ') == 1
    assert request({'edits': [edit(0, list(chances.DEFAULT_OUTCOMES)), edit(2, list(chances.DEFAULT_OUTCOMES))]})[0] == 200
    assert (project/'direct'/world_map.DIRECT_RELATIVE).read_bytes() == baseline.read_bytes()
    assert patch.read_bytes() == b''
    assert request()[1]['groups'][0]['initialOutcomes'] == list(chances.DEFAULT_OUTCOMES)
    assert not (project/'.world-recovery').exists()


def test_http_malformed_and_stale_batches_write_nothing(service):
    project, _, request = service
    before = files(project)
    for weights in (None, [], [32]*7, [31]*8, [True]+[32]*7, ['32']*8, [32.0]*8, [257]+[0]*7):
        malformed = edit()
        malformed['initialOutcomes'] = weights
        assert request({'edits': [malformed]})[0] == 400
        assert files(project) == before
    assert request({'edits': [edit()]}, include_hash=False)[0] == 400
    assert request({'sha256': 'stale', 'edits': [edit()]})[0] == 400
    assert request({'edits': [edit(), edit()]})[0] == 400
    assert files(project) == before
    assert request({'edits': [edit()]})[0] == 200


@pytest.mark.parametrize('existing', [False, True])
@pytest.mark.parametrize('point', ['stage0', 'stage1', 'publish0', 'publish1'])
def test_http_pair_failure_preserves_bytes_timestamps_and_retry(service, monkeypatch, existing, point):
    project, _, request = service
    if existing:
        assert request({'edits': [edit(0, [32]*8)]})[0] == 200
    before = files(project)
    replace, write = project_files.os.replace, Path.write_bytes
    fired = False

    def fail_write(path, data):
        nonlocal fired
        if not fired and point.startswith('stage') and path.name == point[-1]+'.after':
            fired = True
            raise OSError('Injected staging failure')
        return write(path, data)

    def fail_replace(source, destination):
        nonlocal fired
        if not fired and point.startswith('publish') and Path(source).name == point[-1]+'.after':
            fired = True
            raise OSError('Injected publication failure')
        return replace(source, destination)

    monkeypatch.setattr(Path, 'write_bytes', fail_write)
    monkeypatch.setattr(project_files.os, 'replace', fail_replace)
    assert request({'edits': [edit()]})[0] == 400
    assert fired and files(project) == before
    assert not (project/'.world-recovery').exists()
    assert request({'edits': [edit()]})[0] == 200
    assert request()[1]['groups'][0]['initialOutcomes'] == [256]+[0]*7


def test_failed_restore_retains_pair_and_blocks_further_saves(service, monkeypatch):
    project, _, request = service
    assert request({'edits': [edit(0, [32]*8)]})[0] == 200
    before = files(project)
    replace = project_files.os.replace

    def fail(source, destination):
        if Path(source).name == '1.after' or Path(source).name.startswith('.ff8-'):
            raise OSError('Injected publish/restore failure')
        return replace(source, destination)

    monkeypatch.setattr(project_files.os, 'replace', fail)
    assert request({'edits': [edit()]})[0] == 400
    recovery = project/'.world-recovery'
    assert (recovery/'0.before').read_bytes() == before[Path('direct')/world_map.DIRECT_RELATIVE][0]
    assert (recovery/'1.before').read_bytes() == before[Path(chances.HEXT_RELATIVE)][0]
    retained = files(project)
    assert request({'edits': [edit(1)]})[0] == 400
    assert files(project) == retained


def test_external_hext_and_unsupported_executable_are_preserved(service):
    project, _, request = service
    assert request({'edits': [edit(0, [32]*8)]})[0] == 200
    patch = project/chances.HEXT_RELATIVE
    patch.write_bytes(b'external change')
    before = files(project)
    assert request({'edits': [edit()]})[0] == 400
    assert files(project) == before
    (paths.GAME_ROOT/'FF8_EN.exe').write_bytes(b'unsupported')
    assert request({'edits': [edit()]})[0] == 400
    assert files(project) == before


def test_source_change_during_staging_is_preserved_and_retry_reads_it(service, monkeypatch):
    project, baseline, request = service
    before = files(project)
    raw = baseline.read_bytes()
    write = Path.write_bytes
    fired = False

    def change(path, data):
        nonlocal fired
        result = write(path, data)
        if not fired and path.name == '1.after':
            fired = True
            write(baseline, raw+b'external source bytes')
        return result

    monkeypatch.setattr(Path, 'write_bytes', change)
    assert request({'edits': [edit()]})[0] == 400
    assert baseline.read_bytes() == raw+b'external source bytes'
    assert files(project) == before
    assert request({'edits': [edit()]})[0] == 200


def test_external_hext_after_first_publication_rolls_back_only_owned_file(service, monkeypatch):
    project, _, request = service
    assert request({'edits': [edit(0, [32]*8)]})[0] == 200
    before = files(project)
    patch = project/chances.HEXT_RELATIVE
    replace = project_files.os.replace

    def change(source, destination):
        result = replace(source, destination)
        if Path(source).name == '0.after':
            patch.write_bytes(b'external patch while saving')
        return result

    monkeypatch.setattr(project_files.os, 'replace', change)
    assert request({'edits': [edit()]})[0] == 400
    wmset = Path('direct')/world_map.DIRECT_RELATIVE
    assert files(project)[wmset] == before[wmset]
    assert patch.read_bytes() == b'external patch while saving'
    assert not (project/'.world-recovery').exists()


def test_combined_ground_name_failure_leaves_pair_and_names_unchanged(service, monkeypatch):
    project, _, request = service
    names = project/world_names.FILENAME
    names.write_text('{"1":"Before","2":"Keep"}', encoding='utf-8')
    before = files(project)
    write = Path.write_bytes
    fired = False

    def fail(path, data):
        nonlocal fired
        if not fired and path.name == '2.after':
            fired = True
            raise OSError('Injected names staging failure')
        return write(path, data)

    monkeypatch.setattr(Path, 'write_bytes', fail)
    body = {'edits': [edit(), {'kind': 'groundName', 'id': 1, 'name': 'After'}]}
    assert request(body)[0] == 400
    assert files(project) == before
    assert request(body)[0] == 200
    assert json.loads(names.read_text()) == {'1': 'After', '2': 'Keep'}
