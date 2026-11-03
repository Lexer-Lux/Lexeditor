"""Map property/render settings protect booleans, RLE identity and unknown bits."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.scene_map_data import save_scene_properties, save_scene_render_settings
from test_chrono_trigger_replacement import build_archive


PROPERTY_BOOLEANS = ('layer1UpperBank', 'layer2UpperBank', 'doorTrigger', 'priorityTop', 'npcCollisionBattle', 'collisionIgnoreZ', 'collisionInverted', 'zNeutral', 'priorityBottom', 'npcCollision')
RENDER_BOOLEANS = ('layer1Main', 'layer2Main', 'layer3Main', 'spritesMain', 'layer1Sub', 'layer2Sub', 'layer3Sub', 'spritesSub', 'effectLayer1', 'effectLayer2', 'effectLayer3', 'effectSprites', 'effectDefaultColor', 'effectHalfIntensity', 'effectSubtract')
PROPERTY_NUMBERS = ('collisionCode', 'moveDirection', 'moveSpeed', 'zPlane')
RENDER_NUMBERS = ('scrollL2XCode', 'scrollL2YCode', 'scrollL3XCode', 'scrollL3YCode')


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['properties', 'render'])
def files(tmp_path, request):
    kind = request.param
    path = 'Game/field/MapTable/MapTable_004.dat'
    original = bytes([0, 0x70, 0x21, 0x43, 0x5A, 0x08]) + b'\xA5' * 512 + bytes([0x81, 0x20, 0x10, 128, 0x80, 0x20, 0x10, 128, 0xEE])
    if kind == 'properties':
        booleans, numbers = PROPERTY_BOOLEANS, PROPERTY_NUMBERS
        good = dict(collisionCode=30, moveDirection=3, moveSpeed=3, zPlane=3) | dict.fromkeys(booleans, True)
        expected = original[:518] + b'\xFB\xFF\xFF' + original[521:]
        def save(store, checksum, values):
            return save_scene_properties(store, path, checksum, [dict(token='4:prop:0', values=good), dict(token='4:prop:1', values=values)])
    else:
        booleans, numbers = RENDER_BOOLEANS, RENDER_NUMBERS
        good = dict(scrollL2XCode=15, scrollL2YCode=0, scrollL3XCode=0, scrollL3YCode=15) | dict.fromkeys(booleans, True)
        expected = original[:2] + b'\x0F\xF0\xFF\xFF' + original[6:]
        def save(store, checksum, values):
            return save_scene_render_settings(store, path, checksum, values)
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    return kind, tmp_path, game, project, store, path, original, good, expected, save, booleans, numbers


@pytest.mark.parametrize('bad', [None, 0, 1, 'false', [], {}])
def test_every_boolean_rejects_malformed_value(files, bad):
    _, root, _, project, store, path, original, good, _, save, booleans, _ = files
    for existing in (False, True):
        if existing:
            save(store, digest(original), {} if files[0] == 'properties' else good)
        payload = (project / path).read_bytes() if existing else original
        for field in booleans:
            before = snapshot(root)
            with pytest.raises(ValueError):
                save(store, digest(payload), good | {field: bad})
            assert snapshot(root) == before


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None])
def test_every_numeric_field_rejects_malformed_value(files, bad):
    _, root, _, _, store, _, original, good, _, save, _, numbers = files
    for field in numbers:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, digest(original), good | {field: bad})
        assert snapshot(root) == before


@pytest.mark.parametrize('values', [None, [], False, dict(unknownSecondBit5=False), dict(unknownEffectBit3=False), dict(preservedBitsByte=0)])
def test_malformed_values_and_protected_fields_reject(files, values):
    _, root, _, _, store, _, original, _, _, save, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save(store, digest(original), values)
    assert snapshot(root) == before


@pytest.mark.parametrize('files', ['properties'], indirect=True)
@pytest.mark.parametrize('later', [None, [], False, dict(token=False), dict(token='4:prop:0'), dict(token='4:prop:9')])
def test_property_batch_identity_rejects_before_writing(files, later):
    _, root, _, _, store, path, original, good, _, _, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_scene_properties(store, path, digest(original), [dict(token='4:prop:0', values=good), later])
    assert snapshot(root) == before


def test_valid_flags_and_numbers_preserve_exact_bytes(files):
    kind, _, game, project, store, path, original, good, expected, save, booleans, numbers = files
    vanilla = snapshot(game)
    result = save(store, digest(original), {} if kind == 'properties' else good)
    assert (project / path).read_bytes() == expected
    row = result['rows'][0] if kind == 'properties' else result
    for field, value in good.items():
        assert row[field] == value
    assert snapshot(game) == vanilla
    if kind == 'properties':
        result = save_scene_properties(store, path, digest(expected), [dict(token='4:prop:0', values=dict.fromkeys(booleans, False) | dict.fromkeys(numbers, 0))])
        assert (project / path).read_bytes() == original[:518] + b'\x80\x20\x10' + original[521:]
    else:
        result = save(store, digest(expected), dict.fromkeys(booleans, False) | dict.fromkeys(numbers, 0))
        assert (project / path).read_bytes() == original[:2] + b'\x00\x00\x00\x08' + original[6:]


def test_numeric_bounds_reject(files):
    kind, root, _, _, store, _, original, good, _, save, _, numbers = files
    for field in numbers:
        high = 30 if field == 'collisionCode' else 3 if kind == 'properties' else 15
        for value in (-1, high + 1):
            before = snapshot(root)
            with pytest.raises(ValueError):
                save(store, digest(original), good | {field: value})
            assert snapshot(root) == before


@pytest.mark.parametrize('files', ['properties'], indirect=True)
def test_unmodelled_collision_is_preserved_until_explicit_edit(files):
    _, root, _, project, store, path, original, _, _, _, _, _ = files
    payload = original[:518] + b'\xFD' + original[519:]
    target = project / path
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    result = save_scene_properties(store, path, digest(payload), [dict(token='4:prop:0', values=dict(priorityTop=True))])
    expected = payload[:519] + b'\x60' + payload[520:]
    assert target.read_bytes() == expected
    assert result['rows'][0]['collisionCode'] == 31
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_scene_properties(store, path, digest(expected), [dict(token='4:prop:0', values=dict(collisionCode=31))])
    assert snapshot(root) == before


def test_http_rejection_and_valid_reload(files):
    kind, _, game, project, _, path, original, good, expected, _, booleans, numbers = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(values, payload, valid=False):
            body = dict(path=path, sha256=digest(payload))
            if kind == 'properties':
                body['edits'] = [dict(token='4:prop:0', values=good)] + ([] if valid else [dict(token='4:prop:1', values=values)])
                route = 'scene-properties'
            else:
                body['values'] = values
                route = 'scene-render-settings'
            return Request(session.url + 'api/' + route + '/save', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request(good, original, valid=True), timeout=5) as response:
                    json.load(response)
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            for values in (None, [], {booleans[0]: 'false'}, {numbers[0]: .5}, dict(unknownEffectBit3=False)):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request(values, payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
