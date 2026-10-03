"""Tile assembly batches validate before writing either layer format."""
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.tileset_data import save_tile_assembly
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture(params=['layer12', 'layer3'])
def files(tmp_path, request):
    kind = request.param
    filename, count = ('ChipTable_0004.dat', 512) if kind == 'layer12' else ('ChipTableBg3_0004.dat', 256)
    path = 'Game/field/ChipTable/' + filename
    original = struct.pack('<HB', 0x552C, 0xA1) * (count * 4) + b'OPAQUE'
    game = tmp_path / 'game'
    game.mkdir()
    archive = game / 'resources.bin'
    build_archive(archive, [(path, original)])
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(archive), project)
    good = dict(token=f'{kind}:4:0:0', values=dict(chipIndex=1023, paletteIndex=15, flipHorizontal=False, flipVertical=True, priority=False))
    return tmp_path, game, project, store, path, original, good


INVALID = [dict(values={field: value}) for field in ('chipIndex', 'paletteIndex')
           for value in (False, .5, float('inf'), float('nan'), '1.5', None)] + [
    dict(values={field: value}) for field in ('flipHorizontal', 'flipVertical', 'priority')
    for value in (None, 0, 1, 'false', [], {})] + [
    dict(values=None), dict(values=[]), dict(values=False), dict(token=False),
    dict(values=dict(unknownPriorityBits=0)), dict(values=dict(chipIndex=1024)),
    dict(values=dict(paletteIndex=16))]


@pytest.mark.parametrize('changes', INVALID)
def test_tile_invalid_later_record_preserves_new_and_existing_outputs(files, changes):
    root, _, project, store, path, original, good = files
    later = good | dict(token=good['token'][:-1] + '1') | changes
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_tile_assembly(store, path, digest(original), [good, later])
    assert snapshot(root) == before
    assert not (project / path).exists()
    save_tile_assembly(store, path, digest(original), [good])
    current = (project / path).read_bytes()
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_tile_assembly(store, path, digest(current), [good, later])
    assert snapshot(root) == before


def test_tile_valid_bounds_and_booleans_preserve_unknown_bits_and_other_corners(files):
    _, game, project, store, path, original, good = files
    vanilla = snapshot(game)
    result = save_tile_assembly(store, path, digest(original), [good])
    expected = struct.pack('<HB', 0xFBFF, 0xA0) + original[3:]
    assert (project / path).read_bytes() == expected
    row = result['rows'][0]
    assert (row['chipIndex'], row['paletteIndex'], row['flipHorizontal'], row['flipVertical'], row['priority']) == (1023, 15, False, True, False)
    assert row['unknownPriorityBits'] == 0xA0
    assert snapshot(game) == vanilla


def test_tile_http_invalid_scalar_boolean_and_shape_preserve_output(files):
    _, game, project, _, path, original, good = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(edits):
            return Request(session.url + 'api/tile-assemblies/save',
                           data=json.dumps(dict(path=path, sha256=digest(original), edits=edits)).encode(),
                           headers={'Content-Type': 'application/json'})
        for values in (dict(chipIndex=.5), dict(paletteIndex=float('inf')), dict(priority='false'), None):
            before = snapshot(project)
            with pytest.raises(HTTPError) as failure:
                urlopen(request([good, dict(token=good['token'][:-1] + '1', values=values)]), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(project) == before
            assert snapshot(game) == vanilla
        with urlopen(request([good]), timeout=5) as response:
            assert json.load(response)['rows'][0]['chipIndex'] == 1023
        assert (project / path).read_bytes() == struct.pack('<HB', 0xFBFF, 0xA0) + original[3:]
        assert snapshot(game) == vanilla
    assert session.wait_closed()
