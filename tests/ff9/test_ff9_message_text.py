"""Synthetic resource references resolve text by path ID, never object order."""
import struct

import pytest

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


def test_installed_resource_lookup_and_record_identity(tmp_path):
    folder = tmp_path / 'x64/FF9_Data'
    folder.mkdir(parents=True)
    refs, objects = [], []
    for index, (key, suffix) in enumerate(text.TABLES.items()):
        path_id = 100 + index * 13
        refs.append((f'EmbeddedAsset/Text/US/{suffix}', 2, path_id))
        objects.insert(0, (path_id, 49, asset(f'First {key}[ENDN][A85038]Second {key}[HSHD][ENDN]')))
    (folder / 'mainData').write_bytes(archive([(1, 147, resources(refs))], ['other.assets', 'resources.assets']))
    (folder / 'resources.assets').write_bytes(archive(objects))
    payload = {'key': 'items', 'rows': [{'id': '1'}, {'id': 0}, {'id': 900}]}
    text.add_descriptions(payload, tmp_path)
    assert payload['rows'] == [{'id': '1', 'vanillaDescription': 'Second items'},
                               {'id': 0, 'vanillaDescription': 'First items'}, {'id': 900}]
    assert payload['descriptionLanguage'] == 'US'
    assert text.messages(tmp_path)['abilities'][0] == 'First abilities'


def test_message_boundaries_and_unrecognised_markup():
    assert text.split_messages('\ufeff[ENDN]One\nline[ENDN][ENDN]') == ['', 'One\nline', '']
    assert text.readable_message('[FFFFFF]Keep [ICON=1][HSHD]') == 'Keep [ICON=1]'


def test_bad_resource_reference_is_explicit():
    with pytest.raises(ValueError, match='invalid'):
        text.resource_references(struct.pack('<II', 1, 200))
    path = 'embeddedasset/text/us/item/itm_help.mes'
    with pytest.raises(ValueError, match='Duplicate'):
        text.resource_references(resources([(path, 1, 2), (path, 1, 3)]))


def test_missing_installation_does_not_invent_descriptions(tmp_path):
    payload = text.add_descriptions({'key': 'items', 'rows': [{'id': 0}]}, tmp_path)
    assert 'descriptionError' in payload
    assert payload['rows'] == [{'id': 0}]
