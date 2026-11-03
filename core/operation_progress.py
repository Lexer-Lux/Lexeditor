"""Bounded, in-memory activity labels; operation results remain authoritative."""
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import re
import threading

_current = ContextVar('lexeditor_operation', default=None)
_lock = threading.Lock()
_reports = OrderedDict()
LIMIT = 16


def _valid(token):
    return isinstance(token, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', token) is not None


@contextmanager
def operation(token, label='Preparing changes'):
    if not _valid(token):
        yield
        return
    with _lock:
        _reports[token] = {'running': True, 'label': str(label)[:180]}
        _reports.move_to_end(token)
        while len(_reports) > LIMIT:
            _reports.popitem(last=False)
    previous = _current.set(token)
    try:
        yield
    finally:
        _current.reset(previous)
        with _lock:
            if token in _reports:
                _reports[token]['running'] = False


def report(label):
    token = _current.get()
    if token is None:
        return
    with _lock:
        if token in _reports and _reports[token]['running']:
            _reports[token]['label'] = str(label)[:180]


def snapshot(token):
    with _lock:
        return dict(_reports.get(token, {})) if _valid(token) else {}
