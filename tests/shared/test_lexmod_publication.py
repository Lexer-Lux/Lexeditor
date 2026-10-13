"""Only installable modules count as a published Lexmod; README failures stay strict."""
from unittest import mock
import json
import pytest
from core import lexmods
from tests.shared import verify_lexmod_readmes


@pytest.mark.parametrize('metadata', [None, b'[]', b'not JSON'])
def test_empty_or_invalid_catalog_is_unavailable(metadata):
    tree = [{'type': 'blob', 'path': 'README.md'}, {'type': 'blob', 'path': 'mod.json'}]
    if metadata is not None:
        tree.append({'type': 'blob', 'path': 'Module/mod.json'})
    def raw(repository, ref, path):
        assert ref == 'candidate'
        return b'# Development placeholder\nNo modules published yet.' if path == 'README.md' else metadata
    with mock.patch.object(lexmods, 'latest', return_value={'ref': 'candidate', 'version': 'candidate'}), \
         mock.patch.object(lexmods, '_json', return_value={'tree': tree}), \
         mock.patch.object(lexmods, '_raw', side_effect=raw):
        with pytest.raises(lexmods.LexmodError, match='no published modules'):
            lexmods.catalog('Fixture/Mod')


def test_published_module_keeps_missing_features_problem():
    def raw(repository, ref, path):
        assert ref == 'candidate'
        return b'# Missing Features' if path == 'README.md' else json.dumps({'name': 'Module'}).encode()
    with mock.patch.object(lexmods, 'latest', return_value={'ref': 'candidate', 'version': 'candidate'}), \
         mock.patch.object(lexmods, '_json', return_value={'tree': [{'type': 'blob', 'path': 'Module/mod.json'}]}), \
         mock.patch.object(lexmods, '_raw', side_effect=raw):
        catalog = lexmods.catalog('Fixture/Mod')
    assert catalog['modules'][0]['folder'] == 'Module'
    assert catalog['readmeProblems'] == ["README.md needs a '## Features' section with a bullet list"]


def test_verifier_skips_unpublished_but_fails_published_readme(capsys):
    problem = "README.md needs a '## Features' section with a bullet list"
    with mock.patch.object(verify_lexmod_readmes, 'declared', return_value={
            'empty': 'Fixture/Empty', 'published': 'Fixture/Published'}), \
         mock.patch.object(lexmods, 'catalog', side_effect=[
             lexmods.LexmodError("Lexer's mod has no published modules yet"),
             {'readmeProblems': [problem]}]) as catalog:
        assert verify_lexmod_readmes.main() == 1
    assert catalog.call_args_list == [mock.call('Fixture/Empty'), mock.call('Fixture/Published')]
    output = capsys.readouterr().out
    assert 'empty: Fixture/Empty: not checked' in output
    assert f'Fixture/Published: {problem}' in output
