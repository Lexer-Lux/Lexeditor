"""Disposable, bounded archive outputs reused across editor restarts."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import sqlite3
import time

LIMIT = 512 * 1024 * 1024
ENTRIES = 512
_DATABASE_OVERHEAD = 16 * 1024 * 1024
_COLUMNS = [('key','BLOB'),('data','BLOB'),('checksum','BLOB'),('touched','INTEGER')]


class _BadCache(ValueError):
    pass


def user_root():
    from core.runtime_bootstrap import user_data_dir
    return user_data_dir()/'cache/ds1'


def _files(root):
    path = root/'composed.sqlite3'
    return [path,*(root/(path.name+suffix) for suffix in ('-journal','-wal','-shm'))]


def _reset(root):
    from .tweak_mods import checked
    for path in _files(root):
        checked(path)
        if path.exists():
            if not path.is_file() or path.resolve().parent != root.resolve():
                raise OSError('The disposable cache path is not a regular file in its cache folder')
            path.unlink()


def _open(root):
    connection = sqlite3.connect(root/'composed.sqlite3',timeout=0.1)
    try:
        connection.execute('PRAGMA auto_vacuum = FULL')
        objects = connection.execute("SELECT type,name FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' LIMIT 2").fetchall()
        if any(row != ('table','outputs') for row in objects):
            raise _BadCache('The disposable cache contains an unexpected schema object')
        connection.execute('CREATE TABLE IF NOT EXISTS outputs '
                           '(key BLOB PRIMARY KEY, data BLOB, checksum BLOB, touched INTEGER)')
        if [(row[1],row[2]) for row in connection.execute('PRAGMA table_info(outputs)')] != _COLUMNS:
            raise _BadCache('The disposable cache schema is invalid')
        return connection
    except Exception:
        connection.close()
        raise


def _corrupt(error):
    code = getattr(error,'sqlite_errorcode',0) & 0xff
    return isinstance(error,_BadCache) or code in (sqlite3.SQLITE_CORRUPT,sqlite3.SQLITE_NOTADB)


@contextmanager
def _database(root):
    from .tweak_mods import checked
    root = Path(root)
    checked(root)
    for path in _files(root):
        checked(path)
    if any(path.is_file() and path.stat().st_size>LIMIT+_DATABASE_OVERHEAD for path in _files(root)):
        _reset(root)
    root.mkdir(parents=True, exist_ok=True)
    try:
        connection = _open(root)
    except (sqlite3.DatabaseError,_BadCache) as error:
        if not _corrupt(error):
            raise
        _reset(root)
        connection = _open(root)
    try:
        with connection:
            yield connection
    except (sqlite3.DatabaseError,_BadCache) as error:
        connection.close()
        if _corrupt(error):
            _reset(root)
        raise
    finally:
        connection.close()


def load(root, key):
    try:
        with _database(root) as database:
            size = database.execute('SELECT length(data) FROM outputs WHERE key = ?', (key,)).fetchone()
            if size is not None and (type(size[0]) is not int or size[0]>LIMIT):
                raise _BadCache('The cached archive exceeds its size limit')
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
