"""Graphics save boundaries reject malformed identities, colors and objects."""
import base64
import io
import json
import struct
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from PIL import Image

from plugins.chrono_trigger.archive import ResourcesBin
from plugins.chrono_trigger.project import OverlayStore, digest
from plugins.chrono_trigger.plugin import ChronoTriggerSession
from plugins.chrono_trigger.palette_data import save_palette
from plugins.chrono_trigger.world_map_data import save_world_colors
from plugins.chrono_trigger.tileset_data import save_graphics_set
from plugins.chrono_trigger.sprite_graphics import save_sprite_image
from test_chrono_trigger_replacement import build_archive


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def encoded_image(color, format):
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2), color).save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture
def files(tmp_path):
    game = tmp_path / 'game'
    game.mkdir()
    palette = b'AB' + struct.pack('<H', 0xFFFF) * 256 + b'OPAQUE'
    paths = {
        'field': 'Game/field/palette_bin/plt004.bin',
        'world': 'Game/world/plt_bin/plt004.bin',
        'colors': 'Game/world/colanim_bin/004_colanim.bin',
        'sets': 'Game/field/BGSetTable/bgsettable_004.dat',
        'image': 'Game/chara/bmp/c004_1.bmp',
    }
    data = dict(field=palette, world=palette, colors=struct.pack('<HH', 0xFFFF, 0xFFFF) + b'\xCC',
                sets=bytes(range(8)) + b'OPAQUE', image=encoded_image('blue', 'BMP'))
    resources = [(paths[key], value) for key, value in data.items()]
    resources.append(('Game/chara/bmp/c004_0.bmp', data['image']))
    build_archive(game / 'resources.bin', resources)
    project = tmp_path / 'mod'
    store = OverlayStore(ResourcesBin(game / 'resources.bin'), project)
    return tmp_path, game, project, store, paths, data


BAD_COLORS = [None, [], False, dict(token=False), dict(token=1), dict(hex=None), dict(hex=False), dict(hex=1234567), dict(hex=[]), dict(hex={}), dict(hex='#+F0000'), dict(hex='# F0000'), dict(hex='#FF+F00'), dict(hex='#FF F00'), dict(hex='#GG0000'), dict(preservedBit15=False), dict(index=0), dict(token='0'), dict(token='256')]


@pytest.mark.parametrize('kind', ['field', 'world', 'colors'])
@pytest.mark.parametrize('bad', BAD_COLORS)
def test_invalid_later_color_preserves_new_and_existing_outputs(files, kind, bad):
    root, _, project, store, paths, data = files
    path, original = paths[kind], data[kind]
    save = save_world_colors if kind == 'colors' else save_palette
    good = dict(token='0', hex='#FF0000')
    later = dict(token='1', hex='#00FF00') | bad if isinstance(bad, dict) else bad
    for existing in (False, True):
        if existing:
            save(store, path, digest(original), [good])
        payload = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save(store, path, digest(payload), [good, later])
        assert snapshot(root) == before


@pytest.mark.parametrize('kind', ['field', 'world', 'colors'])
def test_valid_colors_preserve_bit15_prefix_and_tail(files, kind):
    _, game, project, store, paths, data = files
    path, original = paths[kind], data[kind]
    offset = 0 if kind == 'colors' else 2
    save = save_world_colors if kind == 'colors' else save_palette
    vanilla = snapshot(game)
    result = save(store, path, digest(original), [dict(token='0', hex=' #ff0000 ')])
    assert (project / path).read_bytes() == original[:offset] + b'\x1F\x80' + original[offset + 2:]
    assert result['rows'][0]['hex'] == '#FF0000'
    assert result['rows'][0]['preservedBit15'] is True
    assert snapshot(game) == vanilla


@pytest.mark.parametrize('bad', [None, [], False, dict(trailingBytes=0), dict(graphicsSet8=0)])
def test_graphics_set_malformed_and_protected_values(files, bad):
    root, _, project, store, paths, data = files
    path, original = paths['sets'], data['sets']
    for existing in (False, True):
        if existing:
            save_graphics_set(store, path, digest(original), dict(graphicsSet0=255))
        payload = (project / path).read_bytes() if existing else original
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_graphics_set(store, path, digest(payload), bad)
        assert snapshot(root) == before


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None, -1, 256])
def test_every_graphics_set_slot_rejects_bad_numbers(files, bad):
    root, _, _, store, paths, data = files
    for slot in range(8):
        before = snapshot(root)
        with pytest.raises(ValueError):
            save_graphics_set(store, paths['sets'], digest(data['sets']), {f'graphicsSet{slot}': bad})
        assert snapshot(root) == before


@pytest.mark.parametrize('bad', [False, .5, float('inf'), float('nan'), '1.5', None, -1])
def test_sprite_identity_and_upload_shape_rejection(files, bad):
    root, _, project, store, paths, data = files
    uploaded = base64.b64encode(encoded_image('red', 'PNG')).decode()
    for existing in (False, True):
        if existing:
            save_sprite_image(store, 4, 1, digest(data['image']), uploaded)
        current = (project / paths['image']).read_bytes() if existing else data['image']
        for sprite, bitmap in ((bad, 1), (4, bad)):
            before = snapshot(root)
            with pytest.raises(ValueError):
                save_sprite_image(store, sprite, bitmap, digest(current), uploaded)
            assert snapshot(root) == before


@pytest.mark.parametrize('bad', [None, False, 1234, [], {}, '', '!notbase64', base64.b64encode(b'not an image').decode()])
def test_sprite_upload_rejection(files, bad):
    root, _, _, store, _, data = files
    before = snapshot(root)
    with pytest.raises(ValueError):
        save_sprite_image(store, 4, 1, digest(data['image']), bad)
    assert snapshot(root) == before


def test_valid_sprite_pixels_mode_dimensions_and_other_frame_preserved(files):
    _, game, project, store, paths, data = files
    vanilla = snapshot(game)
    result = save_sprite_image(store, 4.0, 1.0, digest(data['image']), base64.b64encode(encoded_image('red', 'PNG')).decode())
    with Image.open(project / paths['image']) as image:
        assert image.format == 'BMP'
        assert image.mode == 'RGB'
        assert image.size == (2, 2)
        assert [image.getpixel((x, y)) for y in range(2) for x in range(2)] == [(255, 0, 0)] * 4
    assert result['frames'] == [0, 1]
    assert not (project / 'Game/chara/bmp/c004_0.bmp').exists()
    assert snapshot(game) == vanilla


def test_all_graphics_slots_save_exact_bytes_and_reload(files):
    _, game, project, store, paths, data = files
    vanilla = snapshot(game)
    values = {f'graphicsSet{slot}': 255 if slot % 2 else 0 for slot in range(8)}
    result = save_graphics_set(store, paths['sets'], digest(data['sets']), values)
    assert (project / paths['sets']).read_bytes() == bytes([0, 255] * 4) + b'OPAQUE'
    for field, value in values.items():
        assert result[field] == value
    assert snapshot(game) == vanilla


def test_actual_http_routes_reject_malformed_graphics_values(files):
    _, game, project, _, paths, data = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    image = base64.b64encode(encoded_image('red', 'PNG')).decode()
    bodies = [('palette', dict(path=paths['field'], sha256=digest(data['field']), edits=[dict(token='0', hex='#+F0000')])),
              ('graphics-sets', dict(path=paths['sets'], sha256=digest(data['sets']), values=None))]
    for field in ('index', 'bitmap'):
        for bad in (False, .5, float('inf'), None):
            bodies.append(('sprite-image', dict(index=4, bitmap=1, sha256=digest(data['image']), imageBase64=image) | {field: bad}))
    bodies.append(('sprite-image', dict(index=4, bitmap=1, sha256=digest(data['image']), imageBase64=None)))
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        for route, body in bodies:
            before = snapshot(project)
            request = Request(session.url + 'api/' + route + '/save', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            with pytest.raises(HTTPError) as failure:
                urlopen(request, timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(project) == before
            assert snapshot(game) == vanilla
    assert session.wait_closed()


def test_actual_http_valid_saves_and_existing_output_protection(files):
    _, game, project, _, paths, data = files
    (game / 'Chrono Trigger.exe').write_bytes(b'authored executable marker')
    vanilla = snapshot(game)
    image = base64.b64encode(encoded_image('red', 'PNG')).decode()
    cases = [('palette', 'field', dict(path=paths['field'], edits=[dict(token='0', hex='#FF0000')]), dict(edits=[dict(token='0', hex='#FF0000'), dict(token='1', hex='#+F0000')])),
             ('graphics-sets', 'sets', dict(path=paths['sets'], values=dict(graphicsSet0=255)), dict(values=None)),
             ('sprite-image', 'image', dict(index=4.0, bitmap=1.0, imageBase64=image), dict(index=.5))]
    with ChronoTriggerSession({'LEXEDITOR_CHRONO_TRIGGER_ROOT': str(game),
                               'LEXEDITOR_CHRONO_TRIGGER_PROJECT': str(project)}) as session:
        def request(route, body):
            return Request(session.url + 'api/' + route + '/save', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        for route, key, body, invalid in cases:
            with urlopen(request(route, body | dict(sha256=digest(data[key]))), timeout=5) as response:
                result = json.load(response)
            current = (project / paths[key]).read_bytes()
            assert result['sha256'] == digest(current)
            if key == 'field':
                assert current == data[key][:2] + b'\x1F\x80' + data[key][4:]
                assert result['rows'][0]['hex'] == '#FF0000'
            elif key == 'sets':
                assert current == b'\xFF' + data[key][1:]
                assert result['graphicsSet0'] == 255
            else:
                with Image.open(io.BytesIO(current)) as saved:
                    assert saved.getpixel((0, 0)) == (255, 0, 0)
                assert result['frames'] == [0, 1]
            before = snapshot(project)
            with pytest.raises(HTTPError) as failure:
                urlopen(request(route, body | dict(sha256=digest(current)) | invalid), timeout=5)
            assert failure.value.code == 400
            failure.value.close()
            assert snapshot(project) == before
            assert snapshot(game) == vanilla
    assert session.wait_closed()
