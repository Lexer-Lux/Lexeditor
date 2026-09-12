"""Loopback service for the Final Fantasy VII Rebirth plugin.

It serves the page and the shared UI, and answers where the game is. Every
ReShade action goes through the desktop host, which owns the one copy of
ReShade and the machine's shader repositories, so there is nothing to store
here.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))


def game_root() -> Path | None:
    value = os.environ.get("LEXEDITOR_FF7R2_ROOT", "").strip()
    if not value:
        return None
    root = Path(value)
    return root if root.is_dir() else None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0]
                         or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "ff7r2",
                            "name": "Final Fantasy VII Rebirth",
                            "hosted": True, "windowHost": "webview2",
                            "capabilities": ["reshade"]})
        elif path == "/api/game":
            root = game_root()
            binaries = root / "End/Binaries/Win64" if root else None
            self.send_json({
                "root": str(root) if root else "",
                "found": root is not None,
                # Rebirth ships its own d3d12.dll, so dxgi is the loader.
                "renderer": "dxgi",
                "binaries": str(binaries) if binaries else "",
            })
        else:
            self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
