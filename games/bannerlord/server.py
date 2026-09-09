"""Local JSON/UI service for the Bannerlord Lexeditor plugin."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from .module_data import data_map, read_submodule, save_module_metadata


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PROJECT = Path(os.environ.get("LEXEDITOR_BANNERLORD_PROJECT", r"C:\Bannermod"))
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED", "0") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "")


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

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_file(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
            return
        if path.startswith("/shared/"):
            shared = (LEXEDITOR_ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
            return
        if path == "/api/plugin":
            self.send_json(
                {
                    "apiVersion": 1,
                    "pluginId": "bannerlord",
                    "name": "Mount & Blade II: Bannerlord",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "editorRoot": str(PLUGIN_ROOT),
                    "projectRoot": str(PROJECT),
                    "capabilities": ["module-metadata", "data-map"],
                }
            )
            return
        if path == "/api/module":
            source = PROJECT / "SubModule.xml"
            if not source.is_file():
                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)
                return
            try:
                self.send_json(read_submodule(source))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/datamap":
            self.send_json(data_map(PROJECT))
            return
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/module/save":
            source = PROJECT / "SubModule.xml"
            if not source.is_file():
                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)
                return
            try:
                payload = self.read_json()
                edits = dict(payload.get("edits") or {})
                self.send_json(save_module_metadata(source, edits))
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
