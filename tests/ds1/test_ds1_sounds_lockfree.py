"""Sound routes answer while the store lock is held.

The sounds list, bank table and stream bytes are pure reads of game
and mod files, so they serve without the store lock: a slow writer
elsewhere can never wedge the sound tab open. The server runs
in-process here (the session helper spawns a subprocess with its own
lock), the store points at fixtures, and each request runs in its
own thread with the lock held by this thread; if any route took the
lock again, its thread would still be waiting.
"""
import sys
import tempfile
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests' / 'ds1'))
from ds1_fixture import make_archive  # noqa: E402
from plugins.ds1.store import MARKER, RELATIVE  # noqa: E402
from plugins.ds1 import server as ds1_server  # noqa: E402


def _get(url, timeout=20):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def test_sound_routes_answer_while_locked():
    with tempfile.TemporaryDirectory(prefix='lexeditor-ds1-sndlock-') as folder:
        temp = Path(folder)
        game, mod = temp / 'game', temp / 'mod'
        (game / RELATIVE).parent.mkdir(parents=True)
        (game / RELATIVE).write_bytes(make_archive())
        mod.mkdir()
        (mod / MARKER).touch()
        store, lock = ds1_server.STORE, ds1_server.LOCK
        saved = (store.game_root, store.project, store.read_only)
        store.game_root, store.project = game.resolve(), mod.resolve()
        server = ThreadingHTTPServer(('127.0.0.1', 0), ds1_server.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            assert _get(base + '/api/sounds?kind=sfx') == 200
            urls = {
                'sounds': base + '/api/sounds?kind=music',
                'bank': base + '/api/sound/bank?file=sound/nope.fsb',
                'stream': base + '/api/sound/stream?file=sound/nope.fsb&stream=x',
            }
            results = {}
            lock.acquire()
            try:
                workers = [threading.Thread(
                    target=lambda name=name, url=url: results.update(
                        {name: _get(url)}),
                    daemon=True) for name, url in urls.items()]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=20)
                stuck = [worker for worker in workers if worker.is_alive()]
                assert not stuck, 'sound route blocked on the store lock'
            finally:
                lock.release()
            assert results['sounds'] == 200, results
            # The bank and stream name no file, so they fail fast
            # instead of hanging: completion is the assertion.
            assert results['bank'] == 400, results
            assert results['stream'] == 400, results
        finally:
            server.shutdown()
            thread.join(timeout=20)
            server.server_close()
            store.game_root, store.project, store.read_only = saved
