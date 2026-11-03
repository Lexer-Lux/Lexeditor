"""Project FF9_Data text overlays win over installed vanilla descriptions."""
import struct
from pathlib import Path

import pytest

from plugins.ff9 import features as ff9_features
from plugins.ff9 import message_text as text


def resources(entries):
    blob = bytearray(struct.pack('<I', len(entries)))
    for path, file_id, path_id in entries:
        raw = path.encode()
        blob += struct.pack('<I', len(raw)) + raw
        blob += b'\0' * (-len(blob) % 4)
        blob += struct.pack('<iq', file_id, path_id)
    return bytes(blob)


def archive(objects, external=()):
    header = bytearray(struct.pack('>IIIII', 0, 0, 15, 0, 0))
    header += b'5.6.7f1\0' + struct.pack('<IBII', 0, 0, 0, len(objects))
    header += b'\0' * (-len(header) % 4)
    data = bytearray()
    for path_id, kind, payload in objects:
        header += b'\0' * (-len(header) % 4)
        header += struct.pack('<qIIiHHB', path_id, len(data), len(payload), kind, kind, 0, 0)
        data += payload
    header += struct.pack('<II', 0, len(external))
    for path in external:
        header += b'\0' + bytes(20) + path.encode() + b'\0'
    struct.pack_into('>I', header, 12, len(header))
    return bytes(header + data)


def asset(value):
    return struct.pack('<II', 0, len(value.encode())) + value.encode()


@pytest.fixture
def game_root(tmp_path):
    folder = tmp_path / 'game' / 'x64/FF9_Data'
    folder.mkdir(parents=True)
    refs, objects = [], []
    for index, (key, suffix) in enumerate(text.TABLES.items()):
        path_id = 100 + index * 13
        refs.append((f'EmbeddedAsset/Text/US/{suffix}', 2, path_id))
        objects.insert(0, (path_id, 49, asset(f'First {key}[ENDN][A85038]Second {key}[HSHD][ENDN]')))
    (folder / 'mainData').write_bytes(archive([(1, 147, resources(refs))], ['other.assets', 'resources.assets']))
    (folder / 'resources.assets').write_bytes(archive(objects))
    return tmp_path / 'game'


@pytest.fixture
def project_root(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    return project


def test_join_split_round_trip_with_trailing_endn():
    entries = ['First', '[A85038]Second[HSHD]', '', 'line one\nline two']
    framed = text.join_messages(entries)
    assert framed.endswith('[ENDN]')
    assert framed.count('[ENDN]') == len(entries)
    assert text.split_messages(framed) == entries
    assert text.join_messages(text.split_messages(framed)) == framed


def test_overlay_relative_path_mapping():
    for key, suffix in text.TABLES.items():
        assert text.overlay_relative_path(key) == Path('FF9_Data/EmbeddedAsset/Text/US') / suffix


def test_overlay_preferred_over_vanilla(game_root, project_root):
    payload = {'key': 'items', 'rows': [{'id': 0}, {'id': 1}]}
    text.add_descriptions(payload, game_root, project_root)
    assert payload['textSource'] == 'vanilla'
    assert payload['rows'][0]['description'] == 'First items'
    assert payload['rows'][1]['description'] == '[A85038]Second items[HSHD]'
    assert payload['rows'][1]['vanillaText'] == '[A85038]Second items[HSHD]'
    assert payload['rows'][1]['vanillaDescription'] == 'Second items'

    sha = payload['textSha256']
    text.save_descriptions(game_root, project_root, 'items', sha, {1: '[FF0000]Edited'})
    overlay = project_root / 'FF9_Data/EmbeddedAsset/Text/US/item/itm_help.mes'
    assert overlay.read_bytes() == 'First items[ENDN][FF0000]Edited[ENDN]'.encode('utf-8')

    payload = {'key': 'items', 'rows': [{'id': 0}, {'id': 1}]}
    text.add_descriptions(payload, game_root, project_root)
    assert payload['textSource'] == 'project'
    assert payload['rows'][0]['description'] == 'First items'
    assert payload['rows'][1]['description'] == '[FF0000]Edited'
    assert payload['rows'][1]['vanillaText'] == '[A85038]Second items[HSHD]'
    assert payload['rows'][1]['vanillaDescription'] == 'Second items'


def test_save_rejects_endn_nul_bad_index_and_unknown_table(game_root, project_root):
    sha = text.text_sha256(text.messages(game_root)['items'])
    overlay = text.overlay_path(project_root, 'items')
    with pytest.raises(ValueError, match='ENDN'):
        text.save_descriptions(game_root, project_root, 'items', sha, {0: 'a[ENDN]b'})
    with pytest.raises(ValueError, match='NUL'):
        text.save_descriptions(game_root, project_root, 'items', sha, {0: 'a\0b'})
    with pytest.raises(ValueError, match='out of range'):
        text.save_descriptions(game_root, project_root, 'items', sha, {2: 'third'})
    with pytest.raises(ValueError, match='out of range'):
        text.save_descriptions(game_root, project_root, 'items', sha, {-1: 'negative'})
    with pytest.raises(ValueError, match='Invalid FF9 description index'):
        text.save_descriptions(game_root, project_root, 'items', sha, {'abc': 'bad'})
    with pytest.raises(ValueError, match='Unknown FF9 description table'):
        text.save_descriptions(game_root, project_root, 'shops', sha, {0: 'bad'})
    with pytest.raises(ValueError, match='must be an object'):
        text.save_descriptions(game_root, project_root, 'items', sha, ['not', 'a', 'dict'])
    assert not overlay.exists()


def test_save_rejects_stale_sha(game_root, project_root):
    overlay = text.overlay_path(project_root, 'items')
    with pytest.raises(RuntimeError, match='changed outside Lexeditor'):
        text.save_descriptions(game_root, project_root, 'items', 'deadbeef', {0: 'Edited'})
    assert not overlay.exists()


def test_deploy_file_walk_includes_ff9_data(tmp_path):
    project = tmp_path / 'project'
    csv = project / 'StreamingAssets/Data/Battle/Actions.csv'
    csv.parent.mkdir(parents=True)
    csv.write_text('actions', encoding='utf-8')
    mes = project / 'FF9_Data/EmbeddedAsset/Text/US/item/itm_help.mes'
    mes.parent.mkdir(parents=True)
    mes.write_text('Potion[ENDN]', encoding='utf-8')
    found = {relative.as_posix() for _source, relative in ff9_features._iter_project_files(project)}
    assert found == {'StreamingAssets/Data/Battle/Actions.csv',
                     'FF9_Data/EmbeddedAsset/Text/US/item/itm_help.mes'}
