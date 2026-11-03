"""The Files panel's limits bound discovery, including directory-only trees."""
from contextlib import contextmanager
from pathlib import Path

import pytest

from core import mods_service


@pytest.fixture(autouse=True)
def supported_pathlib(monkeypatch):
    monkeypatch.delattr(Path,'is_junction',raising=False)


def test_file_limit_stops_discovery_instead_of_collecting_the_whole_tree(tmp_path,monkeypatch):
    for index in range(30):
        (tmp_path/f'{index}.bin').write_bytes(b'x')
    monkeypatch.setattr(mods_service,'MAX_LISTED_FILES',5)
    original = mods_service.os.scandir
    seen = []
    @contextmanager
    def scan(path):
        with original(path) as entries:
            def stream():
                for entry in entries:
                    seen.append(entry.name)
                    assert len(seen) <= 6, 'The result limit did not stop filesystem traversal'
                    yield entry
            yield stream()
    monkeypatch.setattr(mods_service.os,'scandir',scan)
    result = mods_service.mod_files(tmp_path)
    assert result['truncated'] and len(result['files']) == 5
    assert len(seen) == 6


def test_node_budget_bounds_empty_directory_trees(tmp_path,monkeypatch):
    for index in range(30):
        (tmp_path/str(index)).mkdir()
    monkeypatch.setattr(mods_service,'MAX_FILE_NODES',5)
    assert mods_service.mod_files(tmp_path) == {'files':[],'truncated':True}


def test_exact_file_limit_is_not_reported_as_truncated(tmp_path,monkeypatch):
    monkeypatch.setattr(mods_service,'MAX_LISTED_FILES',2)
    (tmp_path/'b.txt').write_text('b')
    (tmp_path/'a.txt').write_text('a')
    result = mods_service.mod_files(tmp_path)
    assert not result['truncated']
    assert [row['relative'] for row in result['files']] == ['a.txt','b.txt']
    assert all(row['loaded'] is False for row in result['files'])


def test_directory_links_are_never_scanned(tmp_path):
    mod,outside = tmp_path/'mod',tmp_path/'outside'
    mod.mkdir();outside.mkdir()
    (outside/'private.txt').write_text('outside')
    try:
        (mod/'linked').symlink_to(outside,target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlinks are unavailable')
    assert mods_service.mod_files(mod) == {'files':[],'truncated':False}


def test_one_unreadable_subfolder_does_not_hide_healthy_files(tmp_path,monkeypatch):
    (tmp_path/'healthy.txt').write_text('healthy')
    bad = tmp_path/'bad';bad.mkdir()
    original = mods_service.os.scandir
    def scan(path):
        if Path(path) == bad:
            raise PermissionError('Unavailable folder')
        return original(path)
    monkeypatch.setattr(mods_service.os,'scandir',scan)
    result = mods_service.mod_files(tmp_path)
    assert not result['truncated']
    assert [row['relative'] for row in result['files']] == ['healthy.txt']
