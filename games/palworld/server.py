"""Loopback service for the Palworld official mod-package editor."""

from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from runtime_bootstrap import user_data_dir

from .package import InfoDocument, PackageValidationError, StaleInfoError


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_REQUEST_BYTES = 256 * 1024

DATA_MAP = [
    {
        "filename": "Info.json",
        "controls": "Package metadata, dependencies, tags and InstallRule entries",
        "notes": "Structured/editable. Unknown future JSON keys are preserved; changed writes are stale-guarded, atomic and backed up.",
        "coverage": "structured",
        "status": "integrated",
    },
    {
        "filename": "Paks/**/*.pak",
        "controls": "Official Paks InstallRule payload",
        "notes": "Package shape is recognized; Unreal PAK contents are not parsed or edited yet.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "Scripts/**",
        "controls": "Official Lua / UE4SS package payload",
        "notes": "Recognized by InstallRule only. Lexeditor does not install or replace UE4SS in this slice.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "LogicMods/**",
        "controls": "Official LogicMods package payload",
        "notes": "Recognized by InstallRule; Blueprint/asset editing requires separate format evidence.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "PalSchema/**",
        "controls": "Official PalSchema package payload",
        "notes": "Recognized by InstallRule; structured PalSchema data editing is future research.",
        "coverage": "recognized",
        "status": "partial",
    },
    {
        "filename": "Mods/PalModSettings.ini",
        "controls": "Official loader activation configuration",
        "notes": "Read-only design boundary for now; activation/deactivation is deferred until ownership-aware rollback is implemented.",
        "coverage": "known",
        "status": "not-integrated",
    },
    {
        "filename": "Pal/Content/Paks/**",
        "controls": "Installed game assets",
        "notes": "Read-only source boundary. Lexeditor does not rewrite installed Palworld PAKs as a project save operation.",
        "coverage": "read-only",
        "status": "not-integrated",
    },
]


def project_root() -> Path:
    value = os.environ.get("LEXEDITOR_PALWORLD_PROJECT")
    return Path(value).expanduser().resolve() if value else (user_data_dir() / "projects" / "palworld").resolve()


def info_path() -> Path:
    return project_root() / "Info.json"


def info_payload() -> dict:
    path = info_path()
    document = InfoDocument.load(path)
    return {
        "project": str(project_root()),
        "path": str(path),
        "sourceSha256": document.source_sha256,
        "data": document.data,
        "issues": [asdict(issue) for issue in document.issues()],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status: int = 200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
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

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError(f"Request body must be 1..{MAX_REQUEST_BYTES} bytes")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid JSON request: {error}") from error
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
            return
        if path == "/editor.js":
            self.send_file(PLUGIN_ROOT / "editor.js")
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
                "pluginId": "palworld",
                "name": "Palworld",
                "hosted": True,
                "windowHost": "webview2",
                "capabilities": ["official-package-info", "data-map"],
            })
            return
        if path == "/api/info":
            try:
                self.send_json(info_payload())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error), "project": str(project_root())}, 404)
            return
        if path == "/api/data-map":
            self.send_json({"rows": DATA_MAP})
            return
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/info/save":
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            payload = self.read_json()
            source_sha = payload.get("sourceSha256")
            changes = payload.get("changes")
            if not isinstance(source_sha, str) or len(source_sha) != 64:
                raise ValueError("sourceSha256 must be the 64-character hash returned by /api/info")
            if not isinstance(changes, dict):
                raise ValueError("changes must be a JSON object")
            path = info_path()
            document = InfoDocument.load(path)
            document.update(changes)
            document.save(path, expected_sha256=source_sha)
            self.send_json(info_payload())
        except PackageValidationError as error:
            self.send_json({"error": str(error), "issues": [asdict(issue) for issue in error.issues]}, 400)
        except StaleInfoError as error:
            self.send_json({"error": str(error)}, 409)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
