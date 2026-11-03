"""World-navigation batches retain sentinels, unknown blocks and flag bits."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.world_navigation import save_world_navigation
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['destination', 'scripted', 'trigger'])
def files(tmp_path, request):
    kind = request.param
    normal = struct.pack('<BBBHBBB', 0x85, 0xC6, 7, 8, 0xE9, 9, 10)
    scripted = struct.pack('<BBBHBBB', 0x85, 0xC6, 7, 0x1FF, 0xE9, 9, 10)
    original = b'\x04' + normal * 2 + scripted * 2 + b'\x03\x85\x06\x01\x85\x06\x01\x00\x00\x00\x01\xAA\xBB\xCC\x04' + struct.pack('<4H', 0x1111, 0x2222, 0x3333, 0x4444) + b'OPAQUE'
    path = 'Game/world/EventTable/EventTable_004.dat'
    good = dict(xTile=127, enabled=False, yTile=63, nameIndex=255, halfTileLeft=False, halfTileUp=True, targetX=0, targetY=255)
    if kind == 'destination':
        token, later, offset = '4:exit:0', '4:exit:1', 1
        good.update(destinationScene=65535, facing=3)
        replacement = struct.pack('<BBBHBBB', 127, 255, 255, 65535, 0xF7, 0, 255)
        numbers = ('xTile', 'yTile', 'nameIndex', 'destinationScene', 'facing', 'targetX', 'targetY')
        booleans = ('enabled', 'halfTileLeft', 'halfTileUp')
    elif kind == 'scripted':
        token, later, offset = '4:exit:2', '4:exit:3', 17
        good.update(scriptAddressIndex=3)
        replacement = struct.pack('<BBBHBBB', 127, 255, 255, 511, 0xF7, 0, 255)
        numbers = ('xTile', 'yTile', 'nameIndex', 'scriptAddressIndex', 'targetX', 'targetY')
        booleans = ('enabled', 'halfTileLeft', 'halfTileUp')
    else:
        token, later, offset = '4:trigger:0', '4:trigger:1', 34
        good = dict(xTile=127, enabled=False, yTile=255, scriptAddressIndex=3)
        replacement = b'\x7F\xFF\x03'
        numbers = ('xTile', 'yTile', 'scriptAddressIndex')
        booleans = ('enabled',)
    expected = original[:offset] + replacement + original[offset + len(replacement):]
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    good_edit = dict(token=token, values=good)
    return kind, tmp_path, game, project, store, path, original, good_edit, later, expected, numbers, booleans


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None])
def test_every_numeric_field_rejects_malformed_later_value(files, bad):
    _, root, _, project, store, path, original, good, token, _, numbers, _ = files
    for existing in (False, True):
        if existing:
            save_world_navigation(store, path, digest(original), [good])
        payload = (project / path).read_bytes() if existing else original
        for field in numbers:
            before = snapshot(root)
            with pytest.raises(ValueError):
                save_world_navigation(store, path, digest(payload), [good, dict(token=token, values={field: bad})])
            assert snapshot(root) == before


@pytest.mark.parametrize('bad', [None, 0, 1, 'false', [], {}])
def test_every_boolean_rejects_malformed_later_value(files, bad):
    _, root, _, project, store, path, original, good, token, _, _, booleans = files
    for existing in (False, True):
        if existing:
            save_world_navigation(store, path, digest(original), [good])
        payload = (project / path).read_bytes() if existing else original
        for field in booleans:
            before = snapshot(root)
            with pytest.raises(ValueError):
                save_world_navigation(store, path, digest(payload), [good, dict(token=token, values={field: bad})])
            assert snapshot(root) == before


@pytest.mark.parametrize('bad', [None, [], False, dict(token=False), dict(values=None), dict(values=[]), dict(values=False), dict(values=dict(byteOffset=0)), dict(values=dict(unknownYBits=0)), dict(values=dict(unknownFacingBits=0))])
def test_malformed_or_protected_later_edits_reject(files, bad):
    _, root, _, _, store, path, original, good, token, _, _, _ = files
    later = dict(token=token, values={}) | bad if isinstance(bad, dict) else bad
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_world_navigation(store, path, digest(original), [good, later])
    assert snapshot(root) == before


def test_bounds_duplicate_sentinel_and_variant_fields_reject(files):
    kind, root, _, _, store, path, original, good, token, _, _, _ = files
    bad = [dict(xTile=128), dict(xTile=-1), dict(scriptAddressIndex=4)]
    if kind == 'destination':
        bad += [dict(destinationScene=511), dict(destinationScene=65536), dict(facing=4), dict(yTile=64)]
    elif kind == 'scripted':
        bad += [dict(destinationScene=1), dict(facing=0), dict(yTile=64)]
    else:
        bad += [dict(xTile=0, enabled=False, yTile=0, scriptAddressIndex=0), dict(yTile=256), dict(halfTileLeft=False)]
    for values in bad:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_world_navigation(store, path, digest(original), [good, dict(token=token, values=values)])
        assert snapshot(root) == before
    for later in (good, dict(token='4:trigger:2', values={})):
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_world_navigation(store, path, digest(original), [good, later])
        assert snapshot(root) == before


def test_valid_edits_reload_exact_bytes_and_preserve_source(files):
    kind, _, game, project, store, path, original, good, _, expected, _, _ = files
    vanilla = snapshot(game)
    result = save_world_navigation(store, path, digest(original), [good])
    assert (project / path).read_bytes() == expected
    row = next(row for row in result['rows'] if row['token'] == good['token'])
    for field, value in good['values'].items():
        assert row[field] == value
    assert result['exitCount'] == 4
    assert result['storedTriggerCount'] == 3
    assert result['triggerCount'] == 2
    assert result['unknownCount'] == 1
    assert result['scriptAddressCount'] == 4
    assert result['trailingBytes'] == 6
    if kind != 'trigger':
        assert row['unknownYBits'] == 0xC0
        assert row['unknownFacingBits'] == 0xE1
    assert snapshot(game) == vanilla


def test_http_rejection_and_valid_reload(files):
    _, _, game, project, _, path, original, good, token, expected, numbers, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/world-navigation/save', data=json.dumps(dict(
                path=path, sha256=digest(payload), edits=edits)).encode(), headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    assert json.load(response)['exitCount'] == 4
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            for values in (None, {numbers[0]: .5}, dict(enabled='false'), dict(unknownYBits=0)):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, dict(token=token, values=values)], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
