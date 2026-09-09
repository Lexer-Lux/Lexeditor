"""Loopback HTTP service for the FFX/X-2 HD Remaster collection editor."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import deployment, paths
from .vbf import VBFError, VBFIndex, extract_to, read_index


LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 256 * 1024
POST_ROUTES = {"/api/project/extract", "/api/deployment/deploy", "/api/deployment/revert"}
_INDEX_CACHE: dict[str, tuple[tuple[int, int], VBFIndex]] = {}


def _game_key(value: str) -> str:
    key = str(value).casefold()
    if key not in paths.ARCHIVES:
        raise ValueError("game must be 'x' or 'x2'")
    return key


def _index(game: str) -> VBFIndex:
    key = _game_key(game)
    target = paths.ARCHIVES[key]
    stat = target.stat()
    signature = (stat.st_size, stat.st_mtime_ns)
    cached = _INDEX_CACHE.get(key)
    if cached is not None and cached[0] == signature and cached[1].path == target:
        return cached[1]
    parsed = read_index(target)
    _INDEX_CACHE[key] = (signature, parsed)
    return parsed


def _project_target(game: str, archive_path: str) -> Path:
    key = _game_key(game)
    root = paths.PROJECT_ROOT.resolve()
    target = (root / "efl" / key / Path(*archive_path.split("/"))).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Project target escaped the selected project root")
    return target


def _archive_status(game: str) -> dict:
    key = _game_key(game)
    target = paths.ARCHIVES[key]
    if not target.is_file():
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": False, "error": "Archive is missing", "fileCount": 0}
    try:
        index = _index(key)
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": True, "headerMd5": index.header_md5,
                "headerBytes": index.header_length, "fileCount": index.file_count,
                "bytes": target.stat().st_size}
    except (OSError, VBFError) as error:
        return {"game": key, "label": paths.GAME_LABELS[key], "path": str(target),
                "ready": False, "error": str(error), "fileCount": 0}


def data_map() -> dict:
    rows: list[dict] = []
    for key, filename in (("x", "data/FFX_Data.vbf"), ("x2", "data/FFX2_Data.vbf")):
        state = _archive_status(key)
        rows.append({
            "filename": filename,
            "controls": "Validated VBF archive index, search, read-only extraction to project overlay",
            "notes": (
                f"{paths.GAME_LABELS[key]} archive. Installed bytes are read-only. "
                "Extract creates a Fahrenheit EFL project copy; it is not a structured field editor."
            ),
            "status": "integrated" if state["ready"] else "partial",
            "coverage": "archive-index-and-extract",
            "openable": state["ready"],
            "target": "archives",
            "game": key,
        })
    rows.extend([
        {
            "filename": "FFX_Data/ffx_ps2/ffx/**/battle/kernel/*",
            "controls": "Recognized gameplay/kernel family",
            "notes": "Files can be located and staged through the VBF browser. Structured record editing is not integrated yet.",
            "status": "not-integrated", "coverage": "recognized", "openable": False,
        },
        {
            "filename": "FFX2_Data/ffx_ps2/ffx2/**",
            "controls": "Recognized FFX-2 game-data families",
            "notes": "Files can be located and staged through the VBF browser. FFX-2 format-specific editors remain to be implemented.",
            "status": "not-integrated", "coverage": "recognized", "openable": False,
        },
        {
            "filename": "fahrenheit/mods/lexeditor-ffx-x2/efl/{x,x2}/**",
            "controls": "Reversible file-only Fahrenheit deployment",
            "notes": "Deploy copies only the selected Lexeditor project into its owned Fahrenheit mod folder and preserves unrelated loadorder entries.",
            "status": "integrated" if deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT)["fahrenheitReady"] else "partial",
            "coverage": "deployment", "openable": True, "target": "deployment",
        },
    ])
    return {"contract": "Lexeditor.data-map", "rows": rows}


def dashboard() -> dict:
    archives = [_archive_status("x"), _archive_status("x2")]
    deploy = deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT)
    return {
        "game": {
            "root": str(paths.GAME_ROOT),
            "ready": not paths.game_problems(),
            "steamAppId": "359870",
            "launcher": str(paths.GAME_ROOT / "FFX&X-2_LAUNCHER.exe"),
            "executables": [str(paths.GAME_ROOT / "FFX.exe"), str(paths.GAME_ROOT / "FFX-2.exe")],
        },
        "archives": archives,
        "project": {"root": str(paths.PROJECT_ROOT), "fileCount": deploy["projectFileCount"]},
        "deployment": deploy,
        "problems": paths.game_problems(),
    }


def archive_catalog(game: str, query: str, offset: int, limit: int) -> dict:
    key = _game_key(game)
    index = _index(key)
    needle = query.casefold().strip()
    rows = [entry for entry in index.entries if not needle or needle in entry.path.casefold()]
    offset = max(0, offset)
    limit = min(250, max(1, limit))
    page = rows[offset:offset + limit]
    project_root = paths.PROJECT_ROOT.resolve()
    return {
        "game": key,
        "headerMd5": index.header_md5,
        "total": len(rows), "offset": offset, "limit": limit,
        "entries": [{
            "path": entry.path,
            "bytes": entry.size,
            "blocks": entry.block_count,
            "staged": _project_target(key, entry.path).is_file(),
        } for entry in page],
        "projectRoot": str(project_root),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorFFXX2/1"

    def log_message(self, _format, *_args):
        return

    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def file_response(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            if route == "/":
                self.file_response(PLUGIN_ROOT / "editor.html")
            elif route.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared / route.removeprefix("/shared/")).resolve()
                if shared not in target.parents or not target.is_file():
                    self.json_response({"error": "Shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif route == "/api/plugin":
                self.json_response({
                    "apiVersion": 1, "pluginId": "ffx-x2", "name": "Final Fantasy X/X-2 HD Remaster",
                    "edition": "Steam collection / VBF / Fahrenheit EFL",
                    "hosted": HOSTED, "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT), "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": ["data-map", "vbf-index", "vbf-extract", "project-overlay", "fahrenheit-deploy"],
                })
            elif route == "/api/dashboard":
                self.json_response(dashboard())
            elif route == "/api/datamap":
                self.json_response(data_map())
            elif route == "/api/archive":
                query = parse_qs(parsed.query)
                self.json_response(archive_catalog(
                    query.get("game", ["x"])[0],
                    query.get("q", [""])[0],
                    int(query.get("offset", ["0"])[0]),
                    int(query.get("limit", ["100"])[0]),
                ))
            elif route == "/api/deployment":
                self.json_response(deployment.status(paths.GAME_ROOT, paths.PROJECT_ROOT))
            else:
                self.json_response({"error": "Not found"}, 404)
        except FileNotFoundError as error:
            self.json_response({"error": str(error)}, 404)
        except (OSError, VBFError, ValueError, RuntimeError) as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            if route not in POST_ROUTES:
                self.json_response({"error": "Not found"}, 404); return
            port = self.server.server_address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            host = self.headers.get("Host", "").casefold()
            origin = self.headers.get("Origin")
            if host not in allowed_hosts or (origin is not None and origin not in {f"http://{host}"}):
                self.json_response({"error": "Only this editor may change FFX/X-2 project data"}, 403); return
            if self.headers.get_content_type() != "application/json":
                self.json_response({"error": "An application/json request is required"}, 415); return
            if self.headers.get("Transfer-Encoding"):
                self.json_response({"error": "Chunked requests are not supported"}, 400); return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self.json_response({"error": "Invalid or oversized request body"}, 413); return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("The request must be a JSON object")
            if route == "/api/project/extract":
                key = _game_key(str(payload.get("game", "")))
                index = _index(key)
                expected = str(payload.get("headerMd5", ""))
                if expected != index.header_md5:
                    raise RuntimeError("The VBF index changed; refresh the archive browser before extracting")
                entry = index.find(str(payload.get("path", "")))
                paths.ensure_project()
                result = extract_to(index, entry, _project_target(key, entry.path))
                result.update({"game": key, "archivePath": entry.path, "headerMd5": index.header_md5})
            elif route == "/api/deployment/deploy":
                result = deployment.deploy(paths.GAME_ROOT, paths.PROJECT_ROOT)
            else:
                result = deployment.revert(paths.GAME_ROOT, paths.PROJECT_ROOT)
            self.json_response(result)
        except FileExistsError as error:
            self.json_response({"error": str(error)}, 409)
        except FileNotFoundError as error:
            self.json_response({"error": str(error)}, 409)
        except RuntimeError as error:
            self.json_response({"error": str(error)}, 409)
        except (OSError, VBFError, ValueError, json.JSONDecodeError) as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
