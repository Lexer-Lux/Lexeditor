"""Loopback service for the Chrono Trigger Steam plugin."""

from __future__ import annotations

from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import paths
from .data import (
    OverlayStore,
    classify_resource,
    data_map,
    load_message_table,
    load_scenes,
    save_message_table,
    save_scene,
)
from .resources import ResourceArchiveError


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_PORT", os.environ.get("LEXEDITOR_PORT", "0")))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 2 * 1024 * 1024
POST_ROUTES = {"/api/save/message", "/api/save/scene"}


@lru_cache(maxsize=1)
def _store() -> OverlayStore:
    return OverlayStore(
        paths.RESOURCE_PATH,
        paths.PROJECT_ROOT,
        template_root=paths.PROJECT_TEMPLATE_ROOT,
    )


def _source(params: dict[str, list[str]]) -> str:
    value = params.get("source", ["mine"])[0]
    if value not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return value


def _archive_payload(query: str = "", offset: int = 0, limit: int = 250) -> dict:
    archive = _store().archive
    matches = archive.matching(query)
    offset = max(0, min(offset, len(matches)))
    limit = max(1, min(limit, 1000))
    page = matches[offset:offset + limit]
    entries = []
    for entry in page:
        entries.append({
            "path": entry.path,
            "offset": entry.offset,
            "storedSize": entry.stored_size,
            "source": "project" if _store().overlay_exists(entry.path) else "archive",
            **classify_resource(entry.path),
        })
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
        "entries": entries,
    }


def dashboard() -> dict:
    store = _store()
    messages = store.localization_files()
    scenes = store.scene_entries()
    return {
        "game": {
            "root": str(paths.GAME_ROOT),
            "archive": str(paths.RESOURCE_PATH),
            "steamAppId": "613830",
            "ready": not paths.game_problems(),
        },
        "project": {
            "root": str(paths.PROJECT_ROOT),
            "writable": store.writable,
            "template": str(paths.PROJECT_TEMPLATE_ROOT),
            "overlayResources": sum(store.overlay_exists(entry.path) for entry in store.archive.entries),
        },
        "datasets": {
            "resources": len(store.archive.entries),
            "localizationFiles": len(messages),
            "sceneHeaders": len(scenes),
        },
        "deployment": {
            "format": "ctext-loose-files",
            "automated": False,
            "message": "Project paths match CTExt loose-file resource overrides; CTExt installation/load-order setup is not automated yet.",
        },
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorChronoTrigger/2"

    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
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
                    "pluginId": "chrono-trigger",
                    "name": "Chrono Trigger",
                    "edition": "Steam / resources.bin / CTExt loose-file projects",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "projectRoot": str(paths.PROJECT_ROOT),
                    "capabilities": [
                        "data-map", "resource-index", "localization-text",
                        "scene-headers", "project-overlay", "read", "save",
                    ],
                })
            elif path == "/api/dashboard":
                self.send_json(dashboard())
            elif path == "/api/datamap":
                self.send_json(data_map(_store()))
            elif path == "/api/archive":
                self.send_json(_archive_payload(
                    params.get("q", [""])[0],
                    int(params.get("offset", ["0"])[0]),
                    int(params.get("limit", ["250"])[0]),
                ))
            elif path == "/api/scenes":
                self.send_json(load_scenes(
                    _store(), _source(params), params.get("q", [""])[0],
                    int(params.get("offset", ["0"])[0]),
                    int(params.get("limit", ["100"])[0]),
                ))
            elif path == "/api/messages/catalog":
                self.send_json({"files": _store().localization_files()})
            elif path == "/api/messages":
                virtual = params.get("path", [""])[0]
                self.send_json(load_message_table(_store(), virtual, _source(params)))
            else:
                self.send_json({"error": "Not found"}, 404)
        except KeyError as error:
            self.send_json({"error": str(error)}, 404)
        except (OSError, ValueError, ResourceArchiveError) as error:
            self.send_json({"error": str(error)}, 400)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)

    def _request_json(self) -> dict:
        port = self.server.server_address[1]
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "").casefold()
        origin = self.headers.get("Origin")
        if host not in allowed_hosts or (origin is not None and origin not in {f"http://{host}"}):
            raise PermissionError("Only this editor may change Chrono Trigger project data")
        if self.headers.get_content_type() != "application/json":
            raise TypeError("An application/json request is required")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked requests are not supported")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise OverflowError("Invalid or oversized request body")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("The request must be a JSON object")
        return payload

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in POST_ROUTES:
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            payload = self._request_json()
            if path == "/api/save/message":
                result = save_message_table(
                    _store(), str(payload.get("path", "")), str(payload.get("sha256", "")),
                    payload.get("changes", []),
                )
            else:
                result = save_scene(
                    _store(), int(payload.get("id", -1)), str(payload.get("sha256", "")),
                    payload.get("values", {}),
                )
            self.send_json(result)
        except PermissionError as error:
            self.send_json({"error": str(error)}, 403)
        except TypeError as error:
            self.send_json({"error": str(error)}, 415)
        except OverflowError as error:
            self.send_json({"error": str(error)}, 413)
        except RuntimeError as error:
            self.send_json({"error": str(error)}, 409)
        except (OSError, ValueError, KeyError, ResourceArchiveError) as error:
            self.send_json({"error": str(error)}, 400)
        except Exception as error:
            self.send_json({"error": str(error)}, 500)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
