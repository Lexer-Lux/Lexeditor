"""Scene identity, boolean and protected-field rejection precedes writes."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.scene_data import FIELD_NAMES, save_scene
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from test_chrono_trigger_replacement import build_archive

PATH = 'Game/field/Mapinfo/mapinfo_1.dat'
ORIGINAL = struct.pack('<10H4B', *range(9), 0xBEEF, 0, 1, 14, 15) + b'OPAQUE'


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def files(tmp_path):
    game = tmp_path / 'game'
    game.mkdir()
    archive = game / 'resources.bin'
    build_archive(archive, [(PATH, ORIGINAL), ('Game/field/Mapinfo/mapinfo_0.dat', ORIGINAL)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(archive), project)
    return tmp_path, game, project, store


@pytest.mark.parametrize('identifier', [False, True, 1.5, float('inf'), float('nan'), '1.5', None])
def test_scene_invalid_identity_rejects_before_output(files, identifier):
    root, _, _, store = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        save_scene(store, identifier, digest(ORIGINAL), dict(musicIndex=42))
    assert snapshot(root) == before


@pytest.mark.parametrize('values', [dict(cameraUnbounded=v) for v in (None, 0, 1, 'false', [], {})] +
                         [dict(unknownWord=0), dict(trailingBytes=0), dict(unproved=0), None, [], False])
def test_scene_bool_shape_and_protected_fields_preserve_existing(files, values):
    root, _, project, store = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_scene(store, 1, digest(ORIGINAL), values)
    assert snapshot(root) == before
    save_scene(store, 1, digest(ORIGINAL), dict(musicIndex=42))
    current = (project / PATH).read_bytes()
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_scene(store, 1, digest(current), values)
    assert snapshot(root) == before


@pytest.mark.parametrize('field', [*FIELD_NAMES, 'scrollLeft', 'scrollTop', 'scrollRight', 'scrollBottom'])
@pytest.mark.parametrize('value', [False, .5, float('inf'), float('nan')])
def test_scene_existing_numeric_fields_reject_malformed_values(files, field, value):
    root, _, _, store = files
    before = snapshot(root)
    with pytest.raises(ValueError, match='integer'):
        save_scene(store, 1, digest(ORIGINAL), dict(musicIndex=42) | {field: value})
    assert snapshot(root) == before


def test_scene_valid_reload_and_camera_switch_preserve_unknown_word_and_tail(files):
    _, game, project, store = files
    vanilla = snapshot(game)
    result = save_scene(store, 1.0, digest(ORIGINAL), dict(musicIndex=65535, cameraUnbounded=True, scrollTop=255))
    expected = bytearray(ORIGINAL)
    expected[:2] = b'\xff\xff'
    expected[20:22] = b'\x80\xff'
    assert (project / PATH).read_bytes() == expected
    assert result['cameraUnbounded'] is True
    result = save_scene(store, 1, digest(expected), dict(cameraUnbounded=False))
    expected[20] = 0
    assert (project / PATH).read_bytes() == expected
    assert result['cameraUnbounded'] is False
    assert result['unknownWord'] == 0xBEEF
    assert snapshot(game) == vanilla


def test_scene_http_does_not_coerce_id_boolean_or_values_shape(files):
    _, game, project, _ = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(identifier, values):
            return Request(session.url + 'api/scenes/save',
                           data=json.dumps(dict(id=identifier, sha256=digest(ORIGINAL), values=values)).encode(),
                           headers={'Content-Type': 'application/json'})
        for identifier, values in [(1.5, dict(musicIndex=42)), (True, dict(musicIndex=42)),
                                   (1, dict(cameraUnbounded='false')), (1, dict(unknownWord=0)), (1, [])]:
            before = snapshot(project)
            with pytest.raises(HTTPError) as failure:
                urlopen(request(identifier, values), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(project) == before
            assert snapshot(game) == vanilla
        with urlopen(request(1, dict(cameraUnbounded=True)), timeout=5) as response:
            assert json.load(response)['cameraUnbounded'] is True
        expected = bytearray(ORIGINAL)
        expected[20] = 0x80
        assert (project / PATH).read_bytes() == expected
        assert snapshot(game) == vanilla
    assert session.wait_closed()
