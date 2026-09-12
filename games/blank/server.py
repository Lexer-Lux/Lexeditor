"""Loopback service for the Lexer-only blank plugin."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
PROJECTS_PATH = Path(os.environ.get("LEXEDITOR_BLANK_PROJECTS", str(
    Path(os.environ.get("LOCALAPPDATA", ROOT / "out")) / "Lexeditor" / "blank-projects.json")))
PROJECTS_LOCK = threading.Lock()
MAX_PROJECT_BYTES = 2 * 1024 * 1024


def validate_projects(value):
    if not isinstance(value, dict) or not isinstance(value.get("projects"), dict):
        raise ValueError("Invalid Blank projects")
    projects = value["projects"]
    if len(projects) > 100:
        raise ValueError("At most 100 Blank samples can be saved")
    for name, sample in projects.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise ValueError("Invalid Blank sample name")
        if not isinstance(sample, dict) or not isinstance(sample.get("rows"), list) or not isinstance(sample.get("demo"), dict):
            raise ValueError("Invalid Blank sample data")
    if value.get("current") is not None and value["current"] not in projects:
        raise ValueError("The current Blank sample is missing")
    return value



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
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/projects":
            try:
                with PROJECTS_LOCK:
                    value = json.loads(PROJECTS_PATH.read_text(encoding="utf-8")) if PROJECTS_PATH.exists() else {"current": None, "projects": {}}
                self.send_json(validate_projects(value))
            except (ValueError, OSError) as error:
                self.send_json({"error": str(error)}, 500)
        elif path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
        elif path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "blank", "name": "Blank Game",
                            "hosted": True, "windowHost": "webview2",
                            "capabilities": ["shared-ui-inspection"]})
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/projects":
            self.send_json({"error": "Not found"}, 404)
            return
        # Reject browser cross-origin writes to this loopback data store.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        temporary = None
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_PROJECT_BYTES:
                raise ValueError("Blank samples exceed the 2 MB storage limit")
            value = validate_projects(json.loads(self.rfile.read(size)))
            with PROJECTS_LOCK:
                PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=PROJECTS_PATH.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(value, handle, ensure_ascii=False)
                os.replace(temporary, PROJECTS_PATH)
            self.send_json({"saved": True})
        except (ValueError, OSError) as error:
            self.send_json({"error": str(error)}, 400)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
