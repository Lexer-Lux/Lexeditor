"""Field-exit batch validation preserves authored offsets and unknown flags."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.field_data import EXIT_DATA_PATH, EXIT_OFFSET_PATH, save_exits
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def files(tmp_path):
    offsets = struct.pack('<IHH', 2, 0, 2) + b'OPAQUE'
    original = b'HEAD' + struct.pack('<BBBBHBB', 1, 2, 3, 0xAD, 4, 5, 6) * 2
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(EXIT_OFFSET_PATH, offsets), (EXIT_DATA_PATH, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    good = dict(token='0:0', values=dict(xTile=255, yTile=0, lengthTiles=128, orientation='vertical', destinationId=511, facing=3, targetX=0, targetY=255, halfTileLeft=False, halfTileUp=True))
    expected = b'HEAD' + struct.pack('<BBBBHBB', 255, 0, 255, 0xAB, 511, 0, 255) + original[12:]
    return tmp_path, game, project, store, offsets, original, good, expected


BAD = [dict(values={field: value}) for field in ('xTile', 'yTile', 'lengthTiles', 'destinationId', 'facing', 'targetX', 'targetY')
       for value in (False, .5, float('inf'), float('nan'), '1.5', None)] + [
    dict(values={field: value}) for field in ('halfTileLeft', 'halfTileUp') for value in (None, 0, 1, 'false', [], {})] + [
    dict(token=False), dict(values=None), dict(values=[]), dict(values=False),
    dict(values=dict(unknownFacingBits=0)), dict(values=dict(byteOffset=0)),
    dict(values=dict(destinationKind='world')), dict(values=dict(sceneId=1)),
    dict(values=dict(orientation=None)), dict(values=dict(orientation=[])),
    dict(values=dict(lengthTiles=0)), dict(values=dict(lengthTiles=129)),
    dict(values=dict(destinationId=512)), dict(values=dict(facing=4))]


@pytest.mark.parametrize('changes', BAD)
def test_invalid_later_exit_preserves_new_and_existing_outputs(files, changes):
    root, _, project, store, offsets, original, good, _ = files
    later = dict(token='0:1', values={}) | changes
    for existing in (False, True):
        if existing:
            save_exits(store, digest(original), digest(offsets), [good])
        payload = (project / EXIT_DATA_PATH).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_exits(store, digest(payload), digest(offsets), [good, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('later', [None, [], False, dict(token='0:0'), dict(token='1:0')])
def test_malformed_duplicate_or_missing_exit_rejects(files, later):
    root, _, _, store, offsets, original, good, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_exits(store, digest(original), digest(offsets), [good, later])
    assert snapshot(root) == before


def test_valid_save_exact_bytes_and_reload(files):
    _, game, project, store, offsets, original, good, expected = files
    vanilla = snapshot(game)
    result = save_exits(store, digest(original), digest(offsets), [good])
    assert (project / EXIT_DATA_PATH).read_bytes() == expected
    assert not (project / EXIT_OFFSET_PATH).exists()
    for field, value in good['values'].items():
        assert result['rows'][0][field] == value
    assert result['rows'][0]['unknownFacingBits'] == 0xA0
    assert snapshot(game) == vanilla


def test_http_rejection_and_valid_reload(files):
    _, game, project, _, offsets, original, good, expected = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits, payload):
            return Request(session.url + 'api/exits/save', data=json.dumps(dict(
                dataSha256=digest(payload), offsetSha256=digest(offsets), edits=edits)).encode(),
                headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request([good], original), timeout=5) as response:
                    assert json.load(response)['rows'][0]['destinationId'] == 511
                assert (project / EXIT_DATA_PATH).read_bytes() == expected
            payload = expected if existing else original
            for values in (None, dict(halfTileLeft='false'), dict(destinationId=.5), dict(unknownFacingBits=0)):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request([good, dict(token='0:1', values=values)], payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
