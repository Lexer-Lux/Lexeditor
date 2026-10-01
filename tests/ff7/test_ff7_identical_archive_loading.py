"""Unmodified archives decode once without sharing editable record objects."""
from unittest.mock import patch

import pytest

from plugins.ff7 import extended


@pytest.mark.parametrize('project_bytes', [None, b'vanilla', b'changed'])
def test_load_decodes_only_distinct_archives(tmp_path, project_bytes):
    source = tmp_path / 'source.bin'
    target = tmp_path / 'project.bin'
    source.write_bytes(b'vanilla')
    if project_bytes is not None:
        target.write_bytes(project_bytes)
    families = {'scene': {'categories': {'enemies': {'fields': []}}, 'note': '', 'source': 'source.bin'}}
    calls = []

    class Model:
        def __init__(self, family, data, original):
            calls.append(data)
            self.data = data

        def records(self, key):
            return [{'id': 1, 'values': {'nested': [self.data.decode()]}}]

    with patch.object(extended, 'FAMILIES', families), patch.object(extended, 'resolve_source', return_value=(source, source.relative_to(tmp_path))), patch.object(extended, '_target', return_value=target), patch.object(extended, 'model', Model):
        result = extended.load_extended(tmp_path, tmp_path)
    assert not result['errors']
    assert calls == ([b'vanilla', b'changed'] if project_bytes == b'changed' else [b'vanilla'])
    assert result['families']['scene']['usingProject'] == (project_bytes is not None)
    assert result['records']['enemies'][0]['values']['nested'] == [(project_bytes or b'vanilla').decode()]
    result['records']['enemies'][0]['values']['nested'][0] = 'edited'
    assert result['vanilla']['enemies'][0]['values']['nested'] == ['vanilla']
