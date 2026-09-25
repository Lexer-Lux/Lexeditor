"""The parts of a plugin's local service every plugin was writing itself.

Each plugin serves its own page over loopback, and each grew its own way to
send a file and a JSON reply - the same twenty lines, eight times over, with a
different name each time. This is that code, once.

Mix it into a BaseHTTPRequestHandler:

    class Handler(PluginRequestHandler):
        def do_GET(self): ...
"""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path

NO_STORE = "no-cache, no-store, must-revalidate"

# A session the host opened read-only - a game with no mod yet, or a managed
# mod copy the player may not edit in place - must not write. The shared UI
# refuses the edit and disables Save; this is the backstop for a plugin whose
# write route is reached anyway, so the rule lives here once instead of in
# every service.
#
# A request is a write when the last segment of its path names the change it
# makes. Read routes such as /api/content/file, /api/dashboard or
# /api/settings are left alone, and so is /api/build, which reports a build -
# /api/build/start is the route that writes.
READ_ONLY_WRITE_ROUTES = frozenset({
    "save", "create", "delete", "remove", "rename", "write", "import",
    "install", "deploy", "revert", "restore", "export", "discard", "apply",
    "activate", "start", "setup", "patch", "commit",
})
READ_ONLY_MESSAGE = ("This game is open without a mod, so nothing can be saved. "
                     "Create a mod, then edit it.")


class PluginRequestHandler(BaseHTTPRequestHandler):
    """A plugin service's replies: JSON, a file, and a quiet log."""

    def refuse_write_when_read_only(self, path: str) -> bool:
        """Refuse a write in a read-only session; True when it was refused.

        Called at the top of a service's POST routes, before the payload is
        read, so a refused write changes nothing and says why.
        """
        if os.environ.get("LEXEDITOR_MOD_READ_ONLY") != "1":
            return False
        if path.rstrip("/").rsplit("/", 1)[-1].lower() not in READ_ONLY_WRITE_ROUTES:
            return False
        self.send_json({"error": READ_ONLY_MESSAGE}, status=403)
        return True

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
