"""Assembly/animation saves reject malformed batches before touching files."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.sprite_assembly_data import save_sprite_assembly
from plugins.chrono_trigger.animation_data import save_chip_animations
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['sprite', 'animation'])
def files(tmp_path, request):
    kind = request.param
    if kind == 'sprite':
        path = 'Game/chara/cell/c004.cel'
        original = b'ABC' + struct.pack('<HH', 2, 0xBEEF) + (b'\x01' + struct.pack('<HBBB', 0x18, 2, 3, 0xA1)) * 2 + b'OPAQUE'
        save = save_sprite_assembly
        good = dict(token='4:0:0', values=dict(chipIndex=32767, x=-128, y=127, flipHorizontal=False))
        later_token = '4:1:0'
        expected = original[:8] + struct.pack('<HBBB', 0xFFFF, 128, 127, 0xA0) + original[13:]
        route = 'sprite-assemblies'
    else:
        path = 'Game/field/BGAnime/bganimeinfo_004.dat'
        original = b'\x03' + (b'\x01' + struct.pack('<H', 32) + b'\x1D' + struct.pack('<H', 64)) * 2 + b'\x80OPAQUE'
        save = save_chip_animations
        good = dict(token='4:0', values=dict(destinationChip=2047, durationCode0=128, sourceChip0=0))
        later_token = '4:1'
        expected = original[:2] + struct.pack('<H', 0xFFE0) + b'\x8D\x00\x00' + original[7:]
        route = 'chip-animations'
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    return kind, tmp_path, game, project, store, path, original, save, good, later_token, expected, route


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None])
def test_all_numeric_fields_reject_malformed_later_values(files, bad):
    kind, root, _, project, store, path, original, save, good, token, _, _ = files
    fields = ('chipIndex', 'x', 'y') if kind == 'sprite' else ('destinationChip', 'durationCode0', 'sourceChip0')
    # A fraction near a valid duration code specifically detects int() truncation.
    for field in fields:
        value = 16.5 if field == 'durationCode0' and bad == .5 else bad
        later = dict(token=token, values={field: value})
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, path, digest(original), [good, later])
        assert snapshot(root) == before
    save(store, path, digest(original), [good])
    current = (project / path).read_bytes()
    for field in fields:
        value = 16.5 if field == 'durationCode0' and bad == .5 else bad
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, path, digest(current), [good, dict(token=token, values={field: value})])
        assert snapshot(root) == before


@pytest.mark.parametrize('bad', [None, [], False, dict(token=False), dict(values=None), dict(values=[]), dict(values=False)])
def test_malformed_later_edits_preserve_outputs(files, bad):
    _, root, _, project, store, path, original, save, good, token, _, _ = files
    later = dict(token=token, values={}) | bad if isinstance(bad, dict) else bad
    for existing in (False, True):
        if existing:
            save(store, path, digest(original), [good])
        current = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, path, digest(current), [good, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('value', [None, 0, 1, 'false', [], {}])
@pytest.mark.parametrize('files', ['sprite'], indirect=True)
def test_sprite_flip_requires_boolean(files, value):
    _, root, _, _, store, path, original, save, good, token, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save(store, path, digest(original), [good, dict(token=token, values=dict(flipHorizontal=value))])
    assert snapshot(root) == before


@pytest.mark.parametrize('files', ['animation'], indirect=True)
@pytest.mark.parametrize('code', [16, 32, 64, 128])
def test_documented_duration_choices_preserve_low_bits(files, code):
    _, _, _, project, store, path, original, save, good, _, _, _ = files
    result = save(store, path, digest(original), [good | dict(values=dict(durationCode0=code))])
    assert (project / path).read_bytes() == original[:4] + bytes([code | 13]) + original[5:]
    assert result['rows'][0]['durationCode0'] == code
    assert result['rows'][0]['durationLowBits0'] == 13


def test_bounds_unknown_fields_duplicates_and_protected_metadata(files):
    kind, root, _, _, store, path, original, save, good, token, _, _ = files
    bad_values = [dict(chipIndex=32768), dict(x=-129), dict(y=128), dict(weirdSourceBit=False), dict(unknownFlags=0)] if kind == 'sprite' else [dict(destinationChip=2048), dict(sourceChip0=-1), dict(durationCode0=48), dict(durationLowBits0=0), dict(frameCount=2)]
    for values in bad_values:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, path, digest(original), [good, dict(token=token, values=values)])
        assert snapshot(root) == before
    before = snapshot(root)
    with pytest.raises(ValueError):
        save(store, path, digest(original), [good, good])
    assert snapshot(root) == before


def test_valid_edits_reload_exact_bytes_and_preserve_source(files):
    _, _, game, project, store, path, original, save, good, _, expected, _ = files
    vanilla = snapshot(game)
    result = save(store, path, digest(original), [good])
    assert (project / path).read_bytes() == expected
    for field, value in good['values'].items():
        assert result['rows'][0][field] == value
    assert snapshot(game) == vanilla


def test_http_rejection_and_valid_reload(files):
    kind, _, game, project, _, path, original, _, good, token, expected, route = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/' + route + '/save',
                           data=json.dumps(dict(path=path, sha256=digest(payload), edits=edits)).encode(),
                           headers={'Content-Type': 'application/json'})
        invalid = [dict(values=None), dict(token=False), dict(values=dict(unknownFlags=0))]
        invalid += [dict(values=dict(flipHorizontal='false'))] if kind == 'sprite' else [dict(values=dict(durationCode0=16.5))]
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    assert json.load(response)['rows'][0]['token'] == good['token']
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            for changes in invalid:
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, dict(token=token, values={}) | changes], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
