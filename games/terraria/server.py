"""Loopback service for Terraria / tModLoader source projects."""

from __future__ import annotations

from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse

from .build_metadata import BOOLEAN_KEYS, parse_build_text, update_build_text
from .plugin import DEFAULT_PROJECT_ROOT


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY = 64 * 1024


def project_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_TERRARIA_PROJECT", DEFAULT_PROJECT_ROOT)).resolve()


def _build_file() -> Path:
    root = project_root()
    target = (root / "build.txt").resolve()
    if root != target.parent:
        raise ValueError("Invalid build.txt path")
    return target


def _read_build() -> tuple[bytes, str]:
    target = _build_file()
    data = target.read_bytes()
    if len(data) > MAX_BODY:
        raise ValueError("build.txt is too large for structured editing")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("build.txt is not UTF-8 text") from error
    return data, text


def build_state() -> dict:
    data, text = _read_build()
    parsed = parse_build_text(text)
    values: dict[str, object] = dict(parsed.values)
    for key in BOOLEAN_KEYS:
        if key in values:
            values[key] = str(values[key]).casefold() == "true"
    return {
        "path": "build.txt",
        "sha256": sha256(data).hexdigest(),
        "values": values,
        "duplicates": list(parsed.duplicates),
        "editable": not bool(parsed.duplicates),
    }


def save_build(updates: dict[str, object], expected_sha256: str) -> dict:
    target = _build_file()
    data, text = _read_build()
    current_sha = sha256(data).hexdigest()
    if expected_sha256 != current_sha:
        raise ValueError("build.txt changed outside Lexeditor; reload before saving")

    changed = update_build_text(text, updates)
    if changed == text:
        return build_state()

    encoded = changed.encode("utf-8")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".lexeditor-build-", delete=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return build_state()


def data_map() -> dict:
    root = project_root()
    rows: list[dict] = []
    if not root.is_dir():
        return {"root": str(root), "rows": rows}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: str(p).casefold()):
        relative = path.relative_to(root).as_posix()
        suffix = path.suffix.casefold()
        if relative == "build.txt":
            status, family = "structured", "tModLoader metadata"
        elif suffix == ".cs":
            status, family = "recognized", "C# source"
        elif suffix == ".hjson":
            status, family = "recognized", "Localization"
        elif relative.startswith("Content/"):
            status, family = "recognized", "Content asset"
        elif suffix == ".csproj":
            status, family = "recognized", "MSBuild project"
        else:
            status, family = "unknown", "Other"
        rows.append({"path": relative, "family": family, "status": status})
    return {"root": str(root), "rows": rows}


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

    def read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Invalid request size")
        try:
            return json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Invalid JSON") from error

    def do_GET(self):
        path = urlparse(self.path).path
        try:
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
                self.send_json({
                    "apiVersion": 1,
                    "pluginId": "terraria",
                    "name": "Terraria",
                    "hosted": True,
                    "windowHost": "webview2",
                    "capabilities": ["build-metadata", "data-map"],
                })
            elif path == "/api/build-metadata":
                self.send_json(build_state())
            elif path == "/api/data-map":
                self.send_json(data_map())
            else:
                self.send_json({"error": "Not found"}, 404)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path != "/api/build-metadata":
                self.send_json({"error": "Not found"}, 404)
                return
            payload = self.read_json()
            if not isinstance(payload, dict) or set(payload) != {"updates", "expectedSha256"}:
                raise ValueError("Expected updates and expectedSha256 only")
            updates = payload["updates"]
            expected = payload["expectedSha256"]
            if not isinstance(updates, dict) or not isinstance(expected, str):
                raise ValueError("Invalid build metadata request")
            self.send_json(save_build(updates, expected))
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
