"""Sprite descriptor validation preserves runtime references and unknown data."""
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.sprite_data import save_sprite_header
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=[False, True])
def files(tmp_path, request):
    enemy = request.param
    original = bytes([11, 22, 33, 0xFC, 44, 0xA5])
    if enemy:
        original += bytes([5, 6, 0xA1, 0xA2, 0xA3]) + b'OPAQUE'
    path = 'Game/chara/dat/c004.dat'
    game = tmp_path / 'game'
    game.mkdir()
    build_archive(game / 'resources.bin', [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    good = dict(sizeGroupCode=3, primaryEnemy=False, animationIndex=255)
    if enemy:
        good.update(handX=-128, handY=127)
    expected = original[:3] + bytes([0xF7, 255]) + original[5:]
    if enemy:
        expected = expected[:6] + bytes([128, 127]) + expected[8:]
    return enemy, tmp_path, game, project, store, path, original, good, expected


@pytest.mark.parametrize('bad', [None, 0, 1, 'false', [], {}])
def test_primary_enemy_requires_boolean(files, bad):
    _, root, _, project, store, path, original, good, _ = files
    for existing in (False, True):
        if existing:
            save_sprite_header(store, path, digest(original), good)
        payload = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_sprite_header(store, path, digest(payload), good | dict(primaryEnemy=bad))
        assert snapshot(root) == before


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None])
def test_every_numeric_field_rejects_malformed_values(files, bad):
    enemy, root, _, _, store, path, original, good, _ = files
    fields = ('sizeGroupCode', 'animationIndex', 'handX', 'handY') if enemy else ('sizeGroupCode', 'animationIndex')
    for field in fields:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_sprite_header(store, path, digest(original), good | {field: bad})
        assert snapshot(root) == before


@pytest.mark.parametrize('values', [None, [], False, dict(storedBitmapIndex=1), dict(unknownFlags=0), dict(enemyUnknown1=0)])
def test_malformed_or_protected_fields_reject(files, values):
    _, root, _, _, store, path, original, _, _ = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_sprite_header(store, path, digest(original), values)
    assert snapshot(root) == before


def test_bounds_and_non_enemy_hand_fields_reject(files):
    enemy, root, _, _, store, path, original, good, _ = files
    bad = [dict(sizeGroupCode=4), dict(animationIndex=256), dict(handX=-129), dict(handY=128)]
    if not enemy:
        bad += [dict(handX=0), dict(handY=0)]
    for values in bad:
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_sprite_header(store, path, digest(original), good | values)
        assert snapshot(root) == before


def test_http_rejection_valid_reload_and_source_preservation(files):
    _, _, game, project, _, path, original, good, expected = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(values, payload):
            return Request(session.url + 'api/sprite-headers/save',
                           data=json.dumps(dict(path=path, sha256=digest(payload), values=values)).encode(),
                           headers={'Content-Type': 'application/json'})
        for existing in (False, True):
            if existing:
                with urlopen(request(good, original), timeout=5) as response:
                    row = json.load(response)
                    for field, value in good.items():
                        assert row[field] == value
                assert (project / path).read_bytes() == expected
            payload = expected if existing else original
            for values in (None, [], False, dict(primaryEnemy='false'), dict(animationIndex=.5), dict(storedPaletteIndex=0)):
                before = snapshot(project)
                with pytest.raises(HTTPError) as failure:
                    urlopen(request(values, payload), timeout=5)
                assert failure.value.code == 400
                failure.value.close()
                assert snapshot(project) == before
                assert snapshot(game) == vanilla
    assert session.wait_closed()
