"""Concurrent startup requests share one archive decode, with safe invalidation."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from plugins.ff7 import server


def test_parallel_requests_share_load_and_reload_changed_sources(monkeypatch):
    monkeypatch.setattr(server, '_DATA_CACHE', {'key':None,'value':None})
    monkeypatch.setattr(server, '_DATA_CACHE_LOCK', threading.Lock())
    signature = [1]
    loads = []
    monkeypatch.setattr(server, '_signature', lambda: signature[0])

    def load():
        assert server._DATA_CACHE_LOCK.locked(), 'Archive load must be protected from duplicate requests'
        value = {'generation':len(loads)}
        loads.append(value)
        return value

    monkeypatch.setattr(server, 'editor_data', load)
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _:server.cached_editor_data(), range(8)))
    assert len(loads) == 1 and all(value is loads[0] for value in results)
    signature[0] = 2
    assert server.cached_editor_data() is loads[1]
    server.drop_data_cache()
    assert server.cached_editor_data() is loads[2]


def test_failed_load_releases_lock_and_does_not_cache_partial_data(monkeypatch):
    monkeypatch.setattr(server, '_DATA_CACHE', {'key':None,'value':None})
    monkeypatch.setattr(server, '_DATA_CACHE_LOCK', threading.Lock())
    monkeypatch.setattr(server, '_signature', lambda: 1)
    def fail():
        raise ValueError('Unreadable archive')
    monkeypatch.setattr(server, 'editor_data', fail)
    with pytest.raises(ValueError, match='Unreadable archive'):
        server.cached_editor_data()
    assert not server._DATA_CACHE_LOCK.locked()
    assert server._DATA_CACHE['value'] is None
    monkeypatch.setattr(server, 'editor_data', lambda: {'ready':True})
    assert server.cached_editor_data() == {'ready':True}
