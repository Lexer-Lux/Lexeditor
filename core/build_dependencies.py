"""Repository inputs actually imported or read by a disposable build worker.

Import edges are observed before the build context loads, so a helper already
imported by the worker retains its transitive inputs. Only imports/reads from
mod scripts become roots; context API reads have their own observed hashes.
"""
from __future__ import annotations

import builtins
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
import threading
import types

ROOT = Path(__file__).resolve().parents[1]
MAX_INPUTS = 512
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
_observer = None
_audit_installed = False


def fingerprint(relative, root=ROOT):
    """A bounded repository-file hash; cache records cannot select other paths."""
    from core.mod_library import relative_path
    path = (root / relative_path(relative)).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('Build dependency exceeds its size limit')
    with path.open('rb') as stream:
        data = stream.read(MAX_INPUT_BYTES+1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError('Build dependency grew beyond its size limit')
    return hashlib.sha256(data).hexdigest()


def _audit(event, args):
    observer = _observer
    if observer is not None and event == 'open' and isinstance(args[0], (str, bytes)):
        observer.opened(args[0])


class BuildDependencies:
    def __init__(self, script_roots, *, root=ROOT):
        self.root = Path(root).resolve()
        self.scripts = tuple(Path(path).resolve() for path in script_roots)
        self.edges, self.roots, self.sources = {}, set(), {}
        self.complete, self.bytes = True, 0
        self.lock = threading.RLock()
        self.local = threading.local()

    def _path(self, name):
        if not isinstance(name, str) or not name or name.startswith('<'):
            return None
        path = Path(name)
        if path.suffix == '.pyc':
            return None
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except (OSError, ValueError, RuntimeError):
            return None

    def _script(self, name):
        try:
            path = Path(name).resolve()
            return any(path.is_relative_to(root) for root in self.scripts)
        except (OSError, ValueError, TypeError, RuntimeError):
            return False

    def _edge(self, owner, dependency):
        if getattr(self.local, 'reading', False):
            return
        relative = self._path(dependency)
        if relative is None:
            return
        self.local.reading = True
        try:
            with self.lock:
                if relative not in self.sources:
                    if len(self.sources) >= MAX_INPUTS:
                        self.complete = False
                        return
                    try:
                        path = self.root/relative
                        size = path.stat().st_size if path.is_file() else 0
                        if self.bytes+size > MAX_TOTAL_BYTES:
                            self.complete = False
                            return
                        self.sources[relative] = fingerprint(relative,self.root)
                        self.bytes += size
                    except (OSError,ValueError,RuntimeError):
                        self.complete = False
                        return
                if self._script(owner):
                    self.roots.add(relative)
                else:
                    origin = self._path(owner)
                    if origin is not None:
                        self.edges.setdefault(origin,set()).add(relative)
        finally:
            self.local.reading = False

    def _modules(self, owner, modules):
        for module in modules:
            if isinstance(module, types.ModuleType):
                self._edge(owner,vars(module).get('__file__'))

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        module = self.previous_import(name,globals,locals,fromlist,level)
        owner = (globals or {}).get('__file__')
        try:
            absolute = importlib.util.resolve_name('.'*level+name,(globals or {}).get('__package__')) if level else name
            target = sys.modules.get(absolute)
        except (ImportError,TypeError,ValueError):
            # Python can infer a package from other globals. Observation may
            # decline reuse, but must preserve a successful ordinary import.
            self.complete = False
            target = module
        namespace = vars(target) if isinstance(target,types.ModuleType) else {}
        self._modules(owner,[module,target,*[namespace.get(key) for key in (fromlist or ()) if key != '*']])
        return module

    def _import_module(self, name, package=None):
        module = self.previous_import_module(name,package)
        owner = sys._getframe(1).f_code.co_filename
        self._modules(owner,[module])
        return module

    def opened(self, name):
        if isinstance(name,bytes):
            return
        if getattr(self.local,'reading',False) or self._path(name) is None:
            return
        frame = sys._getframe(2)
        while frame is not None:
            owner = frame.f_code.co_filename
            if self._path(owner) is not None or self._script(owner):
                self._edge(owner,name)
                return
            frame = frame.f_back

    def inputs(self):
        if _observer is self and (builtins.__import__ != self._import or importlib.import_module != self._import_module):
            self.complete = False
        pending, found = list(self.roots), set()
        while pending:
            name = pending.pop()
            if name in found:
                continue
            found.add(name)
            pending.extend(self.edges.get(name,()))
        return {name:self.sources[name] for name in sorted(found)}

    def __enter__(self):
        global _observer, _audit_installed
        if _observer is not None:
            raise RuntimeError('A build dependency observer is already active')
        self.previous_import = builtins.__import__
        self.previous_import_module = importlib.import_module
        if not _audit_installed:
            sys.addaudithook(_audit)
            _audit_installed = True
        _observer = self
        builtins.__import__ = self._import
        importlib.import_module = self._import_module
        return self

    def __exit__(self, *_):
        global _observer
        if builtins.__import__ != self._import or importlib.import_module != self._import_module:
            self.complete = False
        builtins.__import__ = self.previous_import
        importlib.import_module = self.previous_import_module
        _observer = None
