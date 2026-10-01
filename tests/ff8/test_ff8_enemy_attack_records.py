"""Enemy attack names and field edits use their linked kernel records."""
import os
from unittest.mock import patch

import pytest

from plugins.ff8 import formats, kernel_text


def kernel_fixture(name):
    payloads = []
    for section_id in range(1, 57):
        section = formats.SECTIONS[section_id]
        if section.get('type') == 'text':
            payload = kernel_text.encode(name if section_id == 35 else 'Fixture') + b'\x00\x00'
        else:
            payload = bytearray(section.get('number_sub_section', 0) * section.get('sub_section_size', 0))
        payloads.append(payload)
    for text_id in range(32, 57):
        data_id = formats.SECTIONS[text_id]['section_id_data_linked']
        section = formats.SECTIONS[data_id]
        text = bytearray()
        for record in range(section['number_sub_section']):
            for slot in range(section['sub_section_nb_text_offset']):
                offset = record * section['sub_section_size'] + slot * 2
                payloads[data_id - 1][offset:offset + 2] = len(text).to_bytes(2, 'little')
                text.extend(kernel_text.encode(name if text_id == 35 else 'Fixture') + b'\x00')
        payloads[text_id - 1] = bytes(text) + bytes(-len(text) % 4)
    cursor = 57 * 4
    header = bytearray((56).to_bytes(4, 'little'))
    for payload in payloads:
        header.extend(cursor.to_bytes(4, 'little'))
        cursor += len(payload)
    return bytes(header) + b''.join(payloads)


def test_enemy_attack_name_and_edit_round_trip(tmp_path):
    path = tmp_path / 'kernel.bin'
    original = kernel_fixture('Enemy attack')
    path.write_bytes(original)
    with patch.object(formats, 'source_path', return_value=path), patch.object(formats, 'output_path', return_value=path):
        rows = formats.kernel_rows(4)['rows']
        assert len(rows) == 384
        assert rows[17]['name'] == 'Enemy attack'
        assert rows[17]['nameRef'] == {'source': 'kernel', 'sectionId': 35, 'recordId': 17, 'slot': 0}
        assert 'abilityId' not in rows[17]
        formats.save_kernel(4, [{'id': 17, 'field': 'attack_power', 'value': 73}])
        expected = bytearray(original)
        start = int.from_bytes(original[16:20], 'little')
        expected[start + 17 * 20 + 7] = 73
        assert path.read_bytes() == bytes(expected)
        fields = formats.kernel_rows(4)['rows'][17]['fields']
        assert next(f['value'] for f in fields if f['field'] == 'attack_power') == 73
        with pytest.raises(ValueError):
            formats.save_kernel(4, [{'id': 17, 'field': 'attack_power', 'value': 256}])
        assert path.read_bytes() == bytes(expected)


def test_names_do_not_leak_between_same_size_project_files(tmp_path):
    first = tmp_path / 'first.bin'
    second = tmp_path / 'second.bin'
    first.write_bytes(kernel_fixture('Attack A'))
    second.write_bytes(kernel_fixture('Attack B'))
    stamp = first.stat().st_mtime_ns
    os.utime(second, ns=(stamp, stamp))
    for path, name in ((first, 'Attack A'), (second, 'Attack B')):
        with patch.object(formats, 'source_path', return_value=path):
            assert formats.kernel_rows(4)['rows'][0]['name'] == name
