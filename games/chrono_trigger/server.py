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
from .changes import list_changes, revert_change
from .coverage import augment_data_map, resource_override
from .ctp import default_target, export_ctp
from .data import (
    OverlayStore,
    classify_resource,
    data_map,
    load_message_table,
    load_scenes,
    save_message_table,
    save_scene,
)
from .deployment import deploy_audited_project, deployment_status
from .events import event_entries, get_event, load_events
from .field_editors import decorate_event_editors, save_event_fields
from .labels import (
    decorate_scene_exits,
    decorate_scenes,
    decorate_treasure,
    decorate_world_table,
    decorate_worlds,
    label_bundle,
)
from .resource_view import read_resource, resource_info
from .resources import ResourceArchiveError
from .scene_maps import load_scene_map
from .scene_tables import load_exits, load_treasure, save_exit, save_treasure
from .worlds import load_worlds, save_world
from .world_scripts import load_world_script
from .world_tables import (
    load_world_table,
    save_world_exit,
    save_world_script_address,
    save_world_trigger,
)


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_CHRONO_TRIGGER_PORT", os.environ.get("LEXEDITOR_PORT", "0")))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 2 * 1024 * 1024
POST_ROUTES = {
    "/api/save/message", "/api/save/scene", "/api/save/exit", "/api/save/treasure",
    "/api/save/event-fields", "/api/save/world", "/api/save/world-exit", "/api/save/world-trigger",
    "/api/save/world-script-address", "/api/deployment/deploy",
    "/api/changes/revert", "/api/export/ctp",
}


@lru_cache(maxsize=1)
def _store() -> OverlayStore:
    return OverlayStore(paths.RESOURCE_PATH, paths.PROJECT_ROOT, template_root=paths.PROJECT_TEMPLATE_ROOT)


def _source(params: dict[str, list[str]]) -> str:
    value = params.get("source", ["mine"])[0]
    if value not in {"mine", "vanilla"}:
        raise ValueError("source must be mine or vanilla")
    return value


def _labels(source: str) -> dict:
    return label_bundle(_store(), source)


def _archive_payload(query: str = "", offset: int = 0, limit: int = 250) -> dict:
    archive = _store().archive
    matches = archive.matching(query)
    offset = max(0, min(offset, len(matches)))
    limit = max(1, min(limit, 1000))
    entries = []
    for entry in matches[offset:offset + limit]:
        classification = resource_override(entry.path) or classify_resource(entry.path)
        entries.append({
            "path": entry.path,
            "offset": entry.offset,
            "storedSize": entry.stored_size,
            "source": "project" if _store().overlay_exists(entry.path) else "archive",
            **classification,
        })
    return {
        "archive": str(archive.path), "fileSize": archive.file_size,
        "declaredSize": archive.declared_size, "indexOffset": archive.index_offset,
        "indexStoredSize": archive.index_stored_size, "entryCount": len(archive.entries),
        "matchCount": len(matches), "offset": offset, "limit": limit, "entries": entries,
    }


def dashboard() -> dict:
    store = _store()
    deployment = deployment_status(store, paths.GAME_ROOT)
    return {
        "game": {
            "root": str(paths.GAME_ROOT), "archive": str(paths.RESOURCE_PATH),
            "steamAppId": "613830", "ready": not paths.game_problems(),
        },
        "project": {
            "root": str(paths.PROJECT_ROOT), "writable": store.writable,
            "template": str(paths.PROJECT_TEMPLATE_ROOT),
            "overlayResources": sum(store.overlay_exists(entry.path) for entry in store.archive.entries),
        },
        "datasets": {
            "resources": len(store.archive.entries),
            "localizationFiles": len(store.localization_files()),
            "sceneHeaders": len(store.scene_entries()),
            "fieldEvents": len(event_entries(store)),
            "worldHeaders": 8 if store.exists("Game/common/bankc6.bin") else 0,
        },
        "deployment": deployment,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorChronoTrigger/13"

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
        self.send_bytes(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    def send_bytes(self, data: bytes, content_type: str, *, attachment: bool = False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        if attachment:
            self.send_header("Content-Disposition", "attachment")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path, params = parsed.path, parse_qs(parsed.query)
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
                    "apiVersion": 1, "pluginId": "chrono-trigger", "name": "Chrono Trigger",
                    "edition": "Steam / resources.bin / CTExt loose-file projects",
                    "hosted": HOSTED, "windowHost": WINDOW_HOST, "projectRoot": str(paths.PROJECT_ROOT),
                    "capabilities": [
                        "data-map", "resource-index", "resource-preview", "localization-text",
                        "localized-labels", "scene-headers", "scene-exits", "scene-treasure",
                        "scene-map-layout", "field-events", "field-event-disassembly",
                        "field-event-fixed-edit", "world-headers", "world-exits", "world-triggers",
                        "world-script-addresses", "world-script-disassembly", "project-overlay",
                        "project-changes", "ctext-deploy", "ctp-export", "read", "save",
                    ],
                })
            elif path == "/api/dashboard":
                self.send_json(dashboard())
            elif path == "/api/deployment":
                self.send_json(deployment_status(_store(), paths.GAME_ROOT))
            elif path == "/api/changes":
                self.send_json(list_changes(_store()))
            elif path == "/api/labels":
                self.send_json(_labels(_source(params)))
            elif path == "/api/datamap":
                self.send_json(augment_data_map(_store(), data_map(_store())))
            elif path == "/api/archive":
                self.send_json(_archive_payload(
                    params.get("q", [""])[0], int(params.get("offset", ["0"])[0]),
                    int(params.get("limit", ["250"])[0]),
                ))
            elif path == "/api/resource":
                self.send_json(resource_info(_store(), params.get("path", [""])[0], _source(params)))
            elif path == "/api/resource/raw":
                source = _source(params)
                virtual = params.get("path", [""])[0]
                info = resource_info(_store(), virtual, source)
                data, _origin, _virtual = read_resource(_store(), virtual, source)
                is_image = info["previewKind"] == "image"
                self.send_bytes(
                    data,
                    info["contentType"] if is_image else "application/octet-stream",
                    attachment=not is_image,
                )
            elif path == "/api/scenes":
                source = _source(params)
                payload = load_scenes(
                    _store(), source, params.get("q", [""])[0],
                    int(params.get("offset", ["0"])[0]), int(params.get("limit", ["100"])[0]),
                )
                self.send_json(decorate_scenes(payload, _labels(source)))
            elif path == "/api/scene-map":
                self.send_json(load_scene_map(
                    _store(), int(params.get("scene", ["-1"])[0]), _source(params)
                ))
            elif path == "/api/exits":
                source = _source(params)
                payload = load_exits(_store(), int(params.get("scene", ["-1"])[0]), source)
                self.send_json(decorate_scene_exits(payload, _labels(source)))
            elif path == "/api/treasure":
                source = _source(params)
                payload = load_treasure(_store(), int(params.get("scene", ["-1"])[0]), source)
                self.send_json(decorate_treasure(payload, _labels(source)))
            elif path == "/api/events":
                if "id" in params:
                    payload = get_event(_store(), int(params["id"][0]), _source(params))
                    self.send_json(decorate_event_editors(payload))
                else:
                    self.send_json(load_events(
                        _store(), _source(params), params.get("q", [""])[0],
                        int(params.get("offset", ["0"])[0]), int(params.get("limit", ["100"])[0]),
                    ))
            elif path == "/api/worlds":
                source = _source(params)
                self.send_json(decorate_worlds(load_worlds(_store(), source), _labels(source)))
            elif path == "/api/world-table":
                source = _source(params)
                payload = load_world_table(_store(), int(params.get("world", ["-1"])[0]), source)
                self.send_json(decorate_world_table(payload, _labels(source)))
            elif path == "/api/world-script":
                self.send_json(load_world_script(_store(), int(params.get("world", ["-1"])[0]), _source(params)))
            elif path == "/api/messages/catalog":
                self.send_json({"files": _store().localization_files()})
            elif path == "/api/messages":
                self.send_json(load_message_table(_store(), params.get("path", [""])[0], _source(params)))
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
            if path == "/api/deployment/deploy":
                result = deploy_audited_project(_store(), paths.GAME_ROOT)
            elif path == "/api/changes/revert":
                result = revert_change(_store(), str(payload.get("path", "")), str(payload.get("sha256", "")))
            elif path == "/api/export/ctp":
                result = export_ctp(paths.PROJECT_ROOT, default_target(paths.PROJECT_ROOT))
            elif path == "/api/save/message":
                result = save_message_table(_store(), str(payload.get("path", "")), str(payload.get("sha256", "")), payload.get("changes", []))
            elif path == "/api/save/scene":
                result = save_scene(_store(), int(payload.get("id", -1)), str(payload.get("sha256", "")), payload.get("values", {}))
            elif path == "/api/save/exit":
                result = save_exit(_store(), int(payload.get("sceneId", -1)), int(payload.get("index", -1)), str(payload.get("offsetSha256", "")), str(payload.get("dataSha256", "")), payload.get("values", {}))
            elif path == "/api/save/treasure":
                result = save_treasure(_store(), int(payload.get("sceneId", -1)), int(payload.get("index", -1)), str(payload.get("offsetSha256", "")), str(payload.get("dataSha256", "")), payload.get("values", {}))
            elif path == "/api/save/event-fields":
                result = save_event_fields(
                    _store(), int(payload.get("eventId", -1)), int(payload.get("objectId", -1)),
                    int(payload.get("functionId", -1)), int(payload.get("commandIndex", -1)),
                    str(payload.get("sha256", "")), payload.get("values", {}),
                )
                result = decorate_event_editors(result)
            elif path == "/api/save/world":
                result = save_world(_store(), int(payload.get("id", -1)), str(payload.get("sha256", "")), payload.get("values", {}))
            elif path == "/api/save/world-exit":
                result = save_world_exit(_store(), int(payload.get("worldId", -1)), int(payload.get("index", -1)), str(payload.get("sha256", "")), payload.get("values", {}))
            elif path == "/api/save/world-trigger":
                result = save_world_trigger(_store(), int(payload.get("worldId", -1)), int(payload.get("index", -1)), str(payload.get("sha256", "")), payload.get("values", {}))
            else:
                result = save_world_script_address(_store(), int(payload.get("worldId", -1)), int(payload.get("index", -1)), str(payload.get("sha256", "")), payload.get("values", {}))
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
