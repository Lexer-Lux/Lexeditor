"""Coupled project files commit together or retain a retryable original state."""
import hashlib

import pytest

from core import plugin_files


def sha(data):
    return hashlib.sha256(data).hexdigest()


def outputs(tmp_path):
    first, second, third = [tmp_path/name for name in ('header.bin','data.bin','records.bin')]
    first.write_bytes(b'old header')
    second.write_bytes(b'old data')
    return {first:b'new header',second:b'new data',third:b'new records'}, {
        first:sha(b'old header'),second:sha(b'old data'),third:None}


def assert_original(changes):
    first, second, third = changes
    assert first.read_bytes() == b'old header'
    assert second.read_bytes() == b'old data'
    assert not third.exists()


def test_group_commit_writes_existing_and_new_files(tmp_path):
    changes, expected = outputs(tmp_path)
    plugin_files.atomic_write_group(changes, expected)
    assert {path:path.read_bytes() for path in changes} == changes


@pytest.mark.parametrize('fail_at', [1,2,3])
@pytest.mark.parametrize('after_write', [False,True])
def test_failed_group_restores_all_outputs_and_can_retry(tmp_path,monkeypatch,fail_at,after_write):
    changes, expected = outputs(tmp_path)
    original = plugin_files.atomic_write
    calls = 0

    def failing(path,data):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            if after_write:
                original(path,data)
            raise OSError('injected write failure')
        original(path,data)

    monkeypatch.setattr(plugin_files,'atomic_write',failing)
    with pytest.raises(OSError,match='injected'):
        plugin_files.atomic_write_group(changes,expected)
    assert_original(changes)
    monkeypatch.setattr(plugin_files,'atomic_write',original)
    plugin_files.atomic_write_group(changes,expected)
    assert {path:path.read_bytes() for path in changes} == changes


def test_stale_output_refuses_whole_group_before_writing(tmp_path):
    changes, expected = outputs(tmp_path)
    second = list(changes)[1]
    second.write_bytes(b'external data')
    with pytest.raises(ValueError,match='changed outside'):
        plugin_files.atomic_write_group(changes,expected)
    assert list(changes)[0].read_bytes() == b'old header'
    assert second.read_bytes() == b'external data'
    assert not list(changes)[2].exists()


def test_external_write_during_failure_is_kept_and_reported(tmp_path,monkeypatch):
    changes, expected = outputs(tmp_path)
    first, second, _ = changes
    original = plugin_files.atomic_write

    def failing(path,data):
        if path == second:
            first.write_bytes(b'new external header')
            raise OSError('injected failure')
        original(path,data)

    monkeypatch.setattr(plugin_files,'atomic_write',failing)
    with pytest.raises(RuntimeError,match='external bytes were kept'):
        plugin_files.atomic_write_group(changes,expected)
    assert first.read_bytes() == b'new external header'
    assert second.read_bytes() == b'old data'


def test_group_bounds_snapshots_and_new_data_before_writing(tmp_path):
    changes, expected = outputs(tmp_path)
    with pytest.raises(ValueError,match='memory limit'):
        plugin_files.atomic_write_group(changes,expected,limit=30)
    assert_original(changes)
