"""Failed extraction must preserve an existing extracted mod file."""
from types import SimpleNamespace

import pytest

from core import plugin_files
from plugins.ff8 import archive_index


def test_failed_archive_replace_preserves_previous_extraction(tmp_path, monkeypatch):
    entry = SimpleNamespace(index=0, basename='entry.bin', name='entry.bin')
    archive = SimpleNamespace(entries=[entry], extract=lambda _: b'new')
    monkeypatch.setattr(archive_index, 'FsArchive', lambda _: archive)
    # No game here: point the installed-archive check at a stand-in index file.
    prefix = tmp_path / 'game' / 'main'
    prefix.parent.mkdir()
    prefix.with_suffix('.fi').write_bytes(b'')
    monkeypatch.setattr(archive_index, '_prefix', lambda _: prefix)
    target = tmp_path / archive_index.EXTRACTED_ROOT / 'main' / 'entry.bin'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'previous edit')

    def fail_replace(*args):
        raise OSError('simulated replacement failure')

    with monkeypatch.context() as patch:
        patch.setattr(plugin_files.os, 'replace', fail_replace)
        with pytest.raises(OSError, match='replacement failure'):
            archive_index.extract('main', 0, tmp_path)
    assert target.read_bytes() == b'previous edit'
    assert list(target.parent.iterdir()) == [target]
    archive_index.extract('main', 0, tmp_path)
    assert target.read_bytes() == b'new'
    assert list(target.parent.iterdir()) == [target]
