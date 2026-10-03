"""Malformed edits cannot create or change map, color or world-header files."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.world_data import BANK_PATH, HEADER_OFFSET, save_worlds
from plugins.chrono_trigger.scene_map_data import save_scene_map
from plugins.chrono_trigger.world_map_data import save_world_tiles, save_world_properties, save_world_music, save_world_colors
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['worlds', 'scene-map', 'world-map', 'world-properties', 'world-music', 'world-colors'])
def files(tmp_path, request):
    kind = request.param
    if kind == 'worlds':
        path = BANK_PATH
        original = b'\xA5' * (HEADER_OFFSET + 8 * 23) + b'OPAQUE'
        good, later = dict(token='0', values=dict(paletteIndex=255)), '1'
        expected = original[:HEADER_OFFSET + 10] + b'\xFF' + original[HEADER_OFFSET + 11:]
        def save(store, payload, edits):
            return save_worlds(store, digest(payload), edits)
    elif kind == 'scene-map':
        path = 'Game/field/MapTable/MapTable_004.dat'
        original = b'\x00\x70\x21\x43\x5A\x08' + b'\xA5' * 512 + b'\x80\x20\x10\x00\xEE'
        good, later = dict(token='4:1:0', values=dict(tileIndex=255)), '4:1:1'
        expected = original[:6] + b'\xFF' + original[7:]
        def save(store, payload, edits):
            return save_scene_map(store, path, digest(payload), edits)
    elif kind == 'world-map':
        path = 'Game/world/Map/Map_004.dat'
        original = b'\xA5' * 12288 + b'OPAQUE'
        good, later = dict(token='4:2:0', values=dict(tileIndex=511)), '4:2:1'
        expected = original[:6144] + b'\xFF' + original[6145:]
        def save(store, payload, edits):
            return save_world_tiles(store, path, digest(payload), edits)
    elif kind == 'world-properties':
        path = 'Game/world/Id/Id_004.dat'
        original = b'\xEF\xAB' * 256 + b'OPAQUE'
        good, later = dict(token='4:0', values=dict(topLeft=4)), '4:1'
        expected = b'\x4F' + original[1:]
        def save(store, payload, edits):
            return save_world_properties(store, path, digest(payload), edits)
    elif kind == 'world-music':
        path = 'Game/world/SeId/SeId_004.dat'
        original = b'\xAB' * 3072 + b'OPAQUE'
        good, later = dict(token='4:0', values=dict(leftMusic=15)), '4:1'
        expected = b'\xFB' + original[1:]
        def save(store, payload, edits):
            return save_world_music(store, path, digest(payload), edits)
    else:
        path = 'Game/world/colanim_bin/004_colanim.bin'
        original = struct.pack('<HH', 0xFFFF, 0xFFFF) + b'\xCC'
        good, later = dict(token='0', hex='#FF0000'), '1'
        expected = b'\x1F\x80' + original[2:]
        def save(store, payload, edits):
            return save_world_colors(store, path, digest(payload), edits)
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    return kind, tmp_path, game, project, store, path, original, good, later, expected, save


@pytest.mark.parametrize('bad', [None, [], False, dict(token=False), dict(token=1), dict(values=None), dict(values=[]), dict(values=False), dict(values=dict(unproved=0))])
def test_malformed_later_edits_preserve_new_and_existing_outputs(files, bad):
    kind, root, _, project, store, path, original, good, token, _, save = files
    later = dict(token=token, hex='#00FF00') if kind == 'world-colors' else dict(token=token, values={})
    later = later | bad if isinstance(bad, dict) else bad
    for existing in (False, True):
        if existing:
            save(store, original, [good])
        payload = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, payload, [good, later])
        assert snapshot(root) == before


def test_valid_save_reload_exact_bytes_and_source_preservation(files):
    kind, _, game, project, store, path, original, good, _, expected, save = files
    vanilla = snapshot(game)
    result = save(store, original, [good])
    assert (project / path).read_bytes() == expected
    row = next(row for row in result['rows'] if row['token'] == good['token'])
    if kind == 'world-colors':
        assert row['hex'] == '#FF0000'
        assert row['preservedBit15'] is True
    else:
        for field, value in good['values'].items():
            assert row[field] == value
    assert snapshot(game) == vanilla


def test_scalar_bounds_duplicates_and_identity_rejection(files):
    kind, root, _, _, store, _, original, good, token, _, save = files
    if kind == 'world-colors':
        invalid = [dict(token=token, hex=value) for value in (None, False, 1234567, [], {}, '#GG0000', '#00000')]
    else:
        field = next(iter(good['values']))
        invalid = [dict(token=token, values={field: value}) for value in (False, .5, float('inf'), float('nan'), '1.5', None, -1, 65536)]
    invalid += [good, good | dict(token='missing')]
    for later in invalid:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, original, [good, later])
        assert snapshot(root) == before


def test_http_rejection_and_valid_reload(files):
    kind, _, game, project, _, path, original, good, token, expected, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/' + kind + '/save', data=json.dumps(dict(
                path=path, sha256=digest(payload), edits=edits)).encode(), headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    json.load(response)
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            later = dict(token=token, hex=None) if kind == 'world-colors' else dict(token=token, values=None)
            for edit in (later, good | dict(token=1), None):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, edit], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
