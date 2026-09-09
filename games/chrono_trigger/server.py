"""Loopback service for the Chrono Trigger Steam plugin."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import paths
from .resources import ResourceArchive, ResourceArchiveError


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_PORT", os.environ.get("LEXEDITOR_PORT", "0")))


def _archive_payload(query: str = "", offset: int = 0, limit: int = 250) -> dict:
    archive = ResourceArchive(paths.RESOURCE_PATH)
    matches = archive.matching(query)
    offset = max(0, min(offset, len(matches)))
    limit = max(1, min(limit, 1000))
    page = matches[offset:offset + limit]
    return {
        "archive": str(archive.path),
        "fileSize": archive.file_size,
        "declaredSize": archive.declared_size,
        "indexOffset": archive.index_offset,
        "indexStoredSize": archive.index_stored_size,
        "entryCount": len(archive.entries),
        "matchCount": len(matches),
        "offset": offset,
        "limit": limit,
        "entries": [
            {"path": entry.path, "offset": entry.offset, "storedSize": entry.stored_size}
            for entry in page
        ],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
            return
        if path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
            return
        if path == "/api/plugin":
            self.send_json({
                "apiVersion": 1,
                "pluginId": "chrono-trigger",
                "name": "Chrono Trigger",
                "hosted": True,
                "windowHost": "webview2",
                "capabilities": ["resource-index", "read"],
            })
            return
        if path == "/api/archive":
            try:
                query = params.get("q", [""])[0]
                offset = int(params.get("offset", ["0"])[0])
                limit = int(params.get("limit", ["250"])[0])
                self.send_json(_archive_payload(query, offset, limit))
            except (OSError, ValueError, ResourceArchiveError) as error:
                self.send_json({"error": str(error)}, 422)
            return
        self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
