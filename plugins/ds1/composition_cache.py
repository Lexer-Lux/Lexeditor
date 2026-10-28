"""Disposable, bounded archive outputs reused across editor restarts."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import sqlite3
import time

LIMIT = 128 * 1024 * 1024
ENTRIES = 64


@contextmanager
def _database(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / 'composed.sqlite3', timeout=0.1)
    try:
        connection.execute('PRAGMA auto_vacuum = FULL')
        connection.execute('CREATE TABLE IF NOT EXISTS outputs '
                           '(key BLOB PRIMARY KEY, data BLOB, checksum BLOB, touched INTEGER)')
        with connection:
            yield connection
    finally:
        connection.close()


def load(root, key):
    try:
        with _database(root) as database:
            row = database.execute('SELECT data, checksum FROM outputs WHERE key = ?', (key,)).fetchone()
            if row is None:
                return None
            data, checksum = row
            if len(data) > LIMIT or sha256(data).digest() != checksum:
                database.execute('DELETE FROM outputs WHERE key = ?', (key,))
                return None
            database.execute('UPDATE outputs SET touched = ? WHERE key = ?', (time.time_ns(), key))
            return data
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return None


def store(root, key, data):
    try:
        if not isinstance(data, bytes) or len(data) > LIMIT:
            return
        with _database(root) as database:
            # Serialize eviction and insertion across host/plugin processes.
            database.execute('BEGIN IMMEDIATE')
            database.execute('DELETE FROM outputs WHERE key = ?', (key,))
            while True:
                count, size = database.execute('SELECT count(*), coalesce(sum(length(data)), 0) FROM outputs').fetchone()
                if count < ENTRIES and size + len(data) <= LIMIT:
                    break
                database.execute('DELETE FROM outputs WHERE key = '
                                 '(SELECT key FROM outputs ORDER BY touched LIMIT 1)')
            database.execute('INSERT INTO outputs VALUES (?, ?, ?, ?)',
                             (key, data, sha256(data).digest(), time.time_ns()))
    except (OSError, sqlite3.Error, TypeError, ValueError):
        pass  # A cache failure never fails a build or deployment.
