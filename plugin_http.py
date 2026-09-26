"""The parts of a plugin's local service every plugin was writing itself.

Each plugin serves its own page over loopback, and each grew its own way to
send a file and a JSON reply - the same twenty lines, eight times over, with a
different name each time. This is that code, once.

Mix it into a BaseHTTPRequestHandler:

    class Handler(PluginRequestHandler):
        def do_GET(self): ...
"""
from __future__ import annotations

import functools
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

NO_STORE = "no-cache, no-store, must-revalidate"
WRITE_METHODS = ("do_POST", "do_PUT", "do_PATCH", "do_DELETE")


def vanilla_session() -> bool:
    """True when the host opened this game with no mod: vanilla, locked."""
    return os.environ.get("LEXEDITOR_VANILLA") == "1"


VANILLA_REFUSAL = ("This is the unmodded game, locked read-only. Choose Add a "
                   "Mod or Find a Mod in the mod menu to make changes.")


def read_only_refusal(handler: BaseHTTPRequestHandler, safe_routes=()) -> bool:
    """Refuse one write request in a vanilla session. True when refused.

    A game opened with no mod shows its unmodded data, and nothing may change
    it however the request arrives, so the service refuses it as well as the
    page. SAFE_ROUTES are requests that only read or preview, matched exactly
    or, when they end in "/", by prefix.

    A mod that updates itself (LEXEDITOR_MOD_READ_ONLY without VANILLA) keeps
    its plugin's own narrower lock: it still deploys, it only refuses edits.
    """
    if not vanilla_session():
        return False
    path = urlparse(handler.path).path
    if any(path == route or (route.endswith("/") and path.startswith(route))
           for route in safe_routes):
        return False
    data = json.dumps({"error": VANILLA_REFUSAL, "readOnly": True}).encode("utf-8")
    try:
        handler.send_response(403)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
    except ConnectionError:
        pass
    return True


class PluginRequestHandler(BaseHTTPRequestHandler):
    """A plugin service's replies: JSON, a file, and a quiet log."""

    # Write-method requests that only read or preview, so a vanilla session
    # still answers them. Everything else a vanilla session refuses.
    READ_ONLY_SAFE_ROUTES: tuple[str, ...] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Every plugin's own write handler is guarded here, once, so no
        # plugin can forget to honour the lock.
        for name in WRITE_METHODS:
            method = cls.__dict__.get(name)
            if method is None or getattr(method, "_lex_read_only_guard", False):
                continue

            def guarded(self, _method=method):
                if read_only_refusal(self, type(self).READ_ONLY_SAFE_ROUTES):
                    return None
                return _method(self)

            functools.update_wrapper(guarded, method)
            guarded._lex_read_only_guard = True
            setattr(cls, name, guarded)

    def log_message(self, _format, *_args):
        # A plugin service writes into a pipe the desktop host drains. Logging
        # every request there buys nothing and fills it.
        return

    def send_json(self, payload, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        # A slow render outlives its page whenever the window closes or a
        # check tears down mid-reply. The client is gone; there is nothing
        # to report to, so a dead connection ends the reply quietly.
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except ConnectionError:
            pass

    def send_file(self, target: Path, status: int = 200) -> None:
        data = Path(target).read_bytes()
        self.send_bytes(data, mimetypes.guess_type(Path(target).name)[0]
                        or "application/octet-stream", status)

    def send_bytes(self, data: bytes, content_type: str, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", NO_STORE)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except ConnectionError:
            pass

    def send_page_module(self, root: Path, path: str) -> bool:
        """Serve /<name>.js or /<name>.css from the plugin's own folder.

        A plugin page is a page: its script and its stylesheet live in modules
        beside it. Every plugin serves them the same way, so this is that route,
        once. Returns False when the path is not one of them, so a caller can
        carry on matching its own routes.
        """
        name = path.strip("/")
        if "/" in name or not name.endswith((".js", ".css")):
            return False
        module = (Path(root) / name).resolve()
        if module.parent != Path(root).resolve() or not module.is_file():
            return False
        self.send_file(module)
        return True

    # The names plugins already used, kept so a page's own routes still read
    # the way that plugin writes them.
    json_response = send_json
    file_response = send_file
