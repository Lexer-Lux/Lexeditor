"""Loopback HTTP service for the Stardew Valley Content Patcher editor."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .acceptance import acceptance_status, begin_acceptance
from .content_pack import ContentPackStore, deploy, deployment_status, loader_status, revert
from .source_data import load_base_objects

LEXEDITOR_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "browser")
MAX_REQUEST_BYTES = 1024 * 1024
POST_ROUTES = {
    "/api/objects/save",
    "/api/deployment/deploy",
    "/api/deployment/revert",
    "/api/acceptance/begin",
}


def objects_dataset() -> dict:
    """Combine read-only vanilla values, when available, with project-owned overrides."""
    payload = ContentPackStore(paths.PROJECT_ROOT).objects()
    base_rows, source = load_base_objects(paths.GAME_ROOT)
    patched = {row["id"]: row for row in payload["rows"]}
    rows = []
    for object_id in sorted(set(base_rows) | set(patched), key=str.casefold):
        base = base_rows.get(object_id)
        patch = patched.get(object_id, {})
        rows.append({
            "id": object_id,
            "name": base["name"] if base else object_id,
            "internalName": base["internalName"] if base else object_id,
            "description": base["description"] if base else "",
            "baseFields": dict(base["baseFields"]) if base else {},
            "sourcePresent": base is not None,
            "fields": dict(patch.get("fields", {})),
            "present": list(patch.get("present", [])),
            "unsupportedFieldCount": int(patch.get("unsupportedFieldCount", 0)),
        })
    payload["rows"] = rows
    payload["baseSource"] = source
    payload["source"] = "vanilla-unpacked+project-patches" if source.get("available") else "project-patches"
    return payload


def data_map() -> dict:
    project_ready = (paths.PROJECT_ROOT / "manifest.json").is_file() and (paths.PROJECT_ROOT / "content.json").is_file()
    _base, source = load_base_objects(paths.GAME_ROOT)
    if source.get("available"):
        notes = (
            "Lexeditor reads vanilla Data/Objects values from the read-only StardewXnbHack JSON export and writes only "
            "field-level Content Patcher overrides into the selected project. Coverage is partial because only Price, "
            "Edibility, and IsDrink are editable so far."
        )
    else:
        notes = (
            "Lexeditor edits field-level Content Patcher overrides in the selected project. Vanilla values become visible "
            "when StardewXnbHack's Content (unpacked)/Data/Objects.json export is present; Lexeditor does not modify the XNB."
        )
    rows = [{
        "filename": "Content/Data/Objects.xnb",
        "controls": "Content Patcher Data/Objects fields: Price, Edibility, IsDrink",
        "notes": notes,
        "status": "partial", "coverage": "structured", "openable": project_ready,
        "sourceAvailable": bool(source.get("available")), "target": "objects", "dataset": "objects", "datasetKey": "objects",
    }]
    for target, label in (
        ("Data/BigCraftables", "Big craftables"), ("Data/Crops", "Crops"),
        ("Data/Machines", "Machines"), ("Data/Weapons", "Weapons"),
        ("Data/Shops", "Shops"),
    ):
        rows.append({
            "filename": target,
            "controls": label,
            "notes": "Stardew Valley 1.6 exposes this as structured data, but Lexeditor has not integrated a schema/editor for it yet.",
            "status": "not-integrated", "coverage": "unavailable", "openable": False,
        })
    return {"contract": "Lexeditor.data-map", "rows": rows}


def dashboard() -> dict:
    _base, source = load_base_objects(paths.GAME_ROOT)
    return {
        "game": {"root": str(paths.GAME_ROOT), "ready": not paths.game_problems()},
        "project": {"root": str(paths.PROJECT_ROOT)},
        "loader": loader_status(paths.GAME_ROOT),
        "source": source,
        "deployment": deployment_status(paths.GAME_ROOT, paths.PROJECT_ROOT),
        "acceptance": acceptance_status(paths.GAME_ROOT, paths.PROJECT_ROOT),
        "problems": paths.game_problems(),
        "scaffold": False,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorStardew/1"

    def log_message(self, _format, *_args): return

    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def file_response(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/": self.file_response(PLUGIN_ROOT / "editor.html")
            elif path.startswith("/shared/"):
                shared = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared / path.removeprefix("/shared/")).resolve()
                if shared not in target.parents or not target.is_file():
                    self.json_response({"error": "Shared UI asset not found"}, 404)
                else: self.file_response(target)
            elif path == "/api/plugin":
                self.json_response({
                    "apiVersion": 1, "pluginId": "stardew-valley", "name": "Stardew Valley",
                    "edition": "PC 1.6 / SMAPI + Content Patcher", "hosted": HOSTED,
                    "windowHost": WINDOW_HOST, "projectRoot": str(paths.PROJECT_ROOT),
                    "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": [
                        "data-map", "content-patcher", "objects", "deploy", "read", "save", "installed-acceptance",
                    ],
                })
            elif path == "/api/dashboard": self.json_response(dashboard())
            elif path == "/api/datamap": self.json_response(data_map())
            elif path == "/api/objects": self.json_response(objects_dataset())
            elif path == "/api/deployment": self.json_response(deployment_status(paths.GAME_ROOT, paths.PROJECT_ROOT))
            elif path == "/api/acceptance": self.json_response(acceptance_status(paths.GAME_ROOT, paths.PROJECT_ROOT))
            else: self.json_response({"error": "Not found"}, 404)
        except FileNotFoundError as error: self.json_response({"error": str(error)}, 409)
        except RuntimeError as error: self.json_response({"error": str(error)}, 409)
        except Exception as error: self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path not in POST_ROUTES:
                self.json_response({"error": "Not found"}, 404); return
            port = self.server.server_address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            host = self.headers.get("Host", "").casefold(); origin = self.headers.get("Origin")
            if host not in allowed_hosts or (origin is not None and origin != f"http://{host}"):
                self.json_response({"error": "Only this editor may change Stardew Valley projects"}, 403); return
            if self.headers.get_content_type() != "application/json":
                self.json_response({"error": "An application/json request is required"}, 415); return
            if self.headers.get("Transfer-Encoding"):
                self.json_response({"error": "Chunked requests are not supported"}, 400); return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self.json_response({"error": "Invalid or oversized request body"}, 413); return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict): raise ValueError("The request must be a JSON object")
            if path == "/api/objects/save":
                ContentPackStore(paths.PROJECT_ROOT).save_objects(
                    str(payload.get("sha256", "")), payload.get("edits", []))
                result = objects_dataset()
            elif path == "/api/deployment/deploy": result = deploy(paths.GAME_ROOT, paths.PROJECT_ROOT)
            elif path == "/api/deployment/revert": result = revert(paths.GAME_ROOT, paths.PROJECT_ROOT)
            else: result = begin_acceptance(paths.GAME_ROOT, paths.PROJECT_ROOT)
            self.json_response(result)
        except FileNotFoundError as error: self.json_response({"error": str(error)}, 409)
        except RuntimeError as error: self.json_response({"error": str(error)}, 409)
        except Exception as error: self.json_response({"error": str(error)}, 400)


def create_server(port=PORT): return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__": create_server().serve_forever()
