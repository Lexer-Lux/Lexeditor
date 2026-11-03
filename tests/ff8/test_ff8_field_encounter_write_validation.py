"""Field formation/rate codecs and service retain invalid drafts without writes."""
import json
import struct
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.ff8 import field_data, field_encounters, paths
from plugins.ff8.server import create_server


@pytest.fixture
def files(tmp_path, monkeypatch):
    source = tmp_path / 'vanilla'
    source.mkdir()
    output = tmp_path / 'mod'
    for key in ('one', 'two'):
        (source / f'{key}.mrt').write_bytes(struct.pack('<4H', 10, 20, 30, 40))
        (source / f'{key}.rat').write_bytes(bytes([1, 2, 3, 4]))
    monkeypatch.setattr(paths, 'DIRECT_ROOT', output)
    monkeypatch.setattr(field_data, '_map_row', lambda key: dict(name=key, group='authored'))
    def current(key, dataset):
        directory = output / field_data.DIRECT_SUBDIR / 'authored' / key
        def path(extension):
            candidate = directory / f'{key}.{extension}'
            return candidate if dataset == 'current' and candidate.exists() else source / f'{key}.{extension}'
        return path('mrt'), path('rat')
    monkeypatch.setattr(field_data, '_encounter_source_paths', current)
    return tmp_path, source, output


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def edit(kind, **values):
    return dict(type='fieldEncounter', map='one', kind=kind, **values)


@pytest.mark.parametrize('kind,field', [('formation', 'slot'), ('formation', 'value'), ('rate', 'value')])
@pytest.mark.parametrize('value', [False, True, .5, float('inf'), float('nan'), '1.5'])
def test_field_encounter_codec_rejects_nonintegers(kind, field, value):
    if kind == 'rate':
        with pytest.raises(ValueError, match='integer'):
            field_encounters.apply_rat_edit(b'\x01' * 4, value)
    else:
        bad = dict(slot=1, formation=1)
        bad['formation' if field == 'value' else field] = value
        with pytest.raises(ValueError, match='integer'):
            field_encounters.apply_mrt_edits(bytes(8), [dict(slot=0, formation=1), bad])


@pytest.mark.parametrize('kind,field', [('formation', 'slot'), ('formation', 'value'), ('rate', 'value')])
@pytest.mark.parametrize('value', [False, .5, float('inf'), '1.5'])
def test_field_encounter_service_rejects_later_map_without_writes(files, kind, field, value):
    root, _, output = files
    before = snapshot(root)
    bad = edit(kind, **(dict(slot=1, value=1) if kind == 'formation' else dict(value=1)))
    bad.update(map='two', **{field: value})
    with pytest.raises(ValueError, match='integer'):
        field_data.save([edit('formation', slot=0, value=65535), bad])
    assert snapshot(root) == before
    assert not output.exists()


@pytest.mark.parametrize('bad', [
    edit('formation', slot=4, value=1), edit('formation', slot=0, value=-1),
    edit('formation', slot=0, value=65536), edit('formation', slot=0, value=1),
    edit('rate', value=-1), edit('rate', value=256),
])
def test_field_encounter_bounds_and_duplicates_preserve_existing_outputs(files, bad):
    root, _, _ = files
    field_data.save([edit('formation', slot=3, value=65535), edit('rate', value=0)])
    before = snapshot(root)
    with pytest.raises(ValueError):
        field_data.save([edit('formation', slot=0, value=100), bad])
    assert snapshot(root) == before


def assert_reload(source):
    mrt, rat = field_data._encounter_source_paths('one', 'current')
    assert mrt.read_bytes() == struct.pack('<4H', 10, 20, 30, 65535)
    assert rat.read_bytes() == b'\xff' * 4
    assert field_encounters.read_mrt(mrt.read_bytes())['formations'] == [10, 20, 30, 65535]
    assert field_encounters.read_rat(rat.read_bytes()) == dict(rate=255, storedValues=[255] * 4, canonical=True)
    assert (source / 'one.mrt').read_bytes() == struct.pack('<4H', 10, 20, 30, 40)
    assert (source / 'one.rat').read_bytes() == bytes([1, 2, 3, 4])
    assert (source / 'two.mrt').read_bytes() == struct.pack('<4H', 10, 20, 30, 40)
    assert (source / 'two.rat').read_bytes() == bytes([1, 2, 3, 4])


def test_field_encounter_valid_save_preserves_other_slots_and_reloads(files):
    _, source, _ = files
    assert field_data.save([edit('formation', slot=3, value=65535), edit('rate', value=255)]) == dict(saved=2, maps=1)
    assert_reload(source)
    assert field_data.save([edit('formation', slot=3, value=65535), edit('rate', value=255)])['saved'] == 0


def test_field_encounter_http_rejects_rate_after_formation_then_saves_and_reloads(files):
    root, source, _ = files
    server = create_server(0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f'http://127.0.0.1:{server.server_address[1]}/api/field/save'
        def request(batch):
            return Request(url, data=json.dumps({'edits': batch}).encode(), headers={'Content-Type': 'application/json'})
        before = snapshot(root)
        with pytest.raises(HTTPError) as failure:
            urlopen(request([edit('formation', slot=3, value=65535), edit('rate', value=.5)]), timeout=5)
        assert failure.value.code == 400
        failure.value.close()
        assert snapshot(root) == before
        with urlopen(request([edit('formation', slot=3, value=65535), edit('rate', value=255)]), timeout=5) as response:
            assert json.load(response)['saved'] == 2
        assert_reload(source)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
