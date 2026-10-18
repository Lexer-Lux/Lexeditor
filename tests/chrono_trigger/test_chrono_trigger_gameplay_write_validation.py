"""Equipment stat saves validate complete tables and canonical record tokens."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.gameplay_data import save_weapons, save_armor, save_helmets
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['weapons', 'armor', 'helmets'])
def files(tmp_path, request):
    route = request.param
    filename, count, width, field, save = {
        'weapons': ('Weapon', 111, 2, 'attack', save_weapons),
        'armor': ('Armor', 50, 1, 'defense', save_armor),
        'helmets': ('Helmet', 39, 1, 'defense', save_helmets),
    }[route]
    path = 'Game/common/' + filename + 'DataTable.dat'
    unknown = b'\xA1\xB2\xC3' if width == 2 else b'\xA1\xB2'
    record = (7).to_bytes(width, 'little') + unknown
    original = struct.pack('<I', count) + record * count + b'OPAQUE'
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    good = dict(token='0', values={field: (1 << (width * 8)) - 1})
    expected = original[:4] + b'\xFF' * width + original[4 + width:]
    return tmp_path, game, project, store, path, original, good, expected, save, route, field, count, width


BAD = [dict(value=value) for value in (False, .5, float('inf'), float('nan'), '1.5', None)] + [
    dict(token=token) for token in (False, 1, 1.5, '01', '+1', ' 1', '1.0', '-1', '9999', '')] + [
    dict(values=None), dict(values=[]), dict(values=False), dict(values=dict(unknownBytes='00')), dict(values=dict(byteOffset=0))]


@pytest.mark.parametrize('changes', BAD)
def test_invalid_later_record_preserves_new_and_existing_outputs(files, changes):
    root, _, project, store, path, original, good, _, save, _, field, _, _ = files
    if 'value' in changes:
        changes = dict(values={field: changes['value']})
    later = dict(token='1', values={}) | changes
    for existing in (False, True):
        if existing:
            save(store, digest(original), [good])
        payload = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, digest(payload), [good, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('later', [None, [], False, dict(token='0')])
def test_malformed_or_duplicate_edit_rejects(files, later):
    root, _, _, store, _, original, good, _, save, _, _, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save(store, digest(original), [good, later])
    assert snapshot(root) == before


@pytest.mark.parametrize('damage', ['header', 'count', 'records'])
def test_malformed_existing_table_rejects_before_writing(files, damage):
    root, _, project, store, path, original, good, _, save, _, _, count, _ = files
    payload = b'ABC' if damage == 'header' else struct.pack('<I', count - 1) + original[4:] if damage == 'count' else original[:8]
    target = project / path
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    before = snapshot(root)
    with pytest.raises(ValueError):
        save(store, digest(payload), [good])
    assert snapshot(root) == before


def test_valid_bounds_exact_bytes_and_unchanged_source(files):
    _, game, project, store, path, original, good, expected, save, _, field, _, width = files
    vanilla = snapshot(game)
    result = save(store, digest(original), [good])
    assert (project / path).read_bytes() == expected
    assert result['rows'][0][field] == good['values'][field]
    result = save(store, digest(expected), [dict(token='0', values={field: 0})])
    assert (project / path).read_bytes() == original[:4] + bytes(width) + original[4 + width:]
    assert result['rows'][0][field] == 0
    assert snapshot(game) == vanilla
    for value in (-1, 1 << (width * 8)):
        before = snapshot(project)
        with pytest.raises(ValueError):
            save(store, result['sha256'], [dict(token='0', values={field: value})])
        assert snapshot(project) == before


def test_http_rejection_and_valid_reload(files):
    _, game, project, _, path, original, good, expected, _, route, field, _, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/' + route + '/save', data=json.dumps(dict(
                sha256=digest(payload), edits=edits)).encode(), headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    assert json.load(response)['rows'][0][field] == good['values'][field]
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            for later in (dict(token='1', values={field: .5}), dict(token='01', values={field: 9}), dict(token='1', values=None), dict(token='1', values=dict(unknownBytes='00'))):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, later], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
