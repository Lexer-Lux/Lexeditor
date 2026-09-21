"""Loopback service for the fresh Chrono Trigger Steam editor."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .archive import ResourcesBin
from .animation_data import load_chip_animations, save_chip_animations
from .data_map import build_data_map
from .field_data import load_exits, load_treasure, save_exits, save_treasure
from .palette_data import load_palette, palette_files, save_palette
from .project import OverlayStore
from .scene_data import load_scenes, save_scene
from .text_data import languages, load_messages, save_messages, text_files
from .world_data import load_worlds, save_worlds
from .world_navigation import load_world_navigation, save_world_navigation


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
GAME_ROOT = Path(os.environ["LEXEDITOR_CHRONO_TRIGGER_ROOT"]).resolve()
PROJECT_ROOT = Path(os.environ["LEXEDITOR_CHRONO_TRIGGER_PROJECT"]).resolve()
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY = 4 * 1024 * 1024

ARCHIVE = ResourcesBin(GAME_ROOT / "resources.bin")
STORE = OverlayStore(ARCHIVE, PROJECT_ROOT)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, target: Path):
        payload = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def query(self) -> dict[str, str]:
        values = parse_qs(urlparse(self.path).query)
        return {key: rows[-1] for key, rows in values.items() if rows}

    def read_json(self) -> dict:
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            raise PermissionError("Cross-origin writes are not permitted")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY:
            raise ValueError("Request body is empty or too large")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object")
        return value

    def do_GET(self):
        route = urlparse(self.path).path
        query = self.query()
        try:
            if route == "/":
                return self.send_file(PLUGIN_ROOT / "editor.html")
            if route in {"/editor.js", "/editor.css"}:
                return self.send_file(PLUGIN_ROOT / route.removeprefix("/"))
            if route.startswith("/shared/"):
                shared = (ROOT / "ui").resolve()
                target = (shared / route.removeprefix("/shared/")).resolve()
                if shared in target.parents and target.is_file():
                    return self.send_file(target)
                return self.send_json({"error": "Shared UI asset not found"}, 404)
            if route == "/api/plugin":
                return self.send_json({
                    "apiVersion": 1, "pluginId": "chrono-trigger", "name": "Chrono Trigger",
                    "hosted": True, "windowHost": "webview2",
                    "capabilities": ["data-map", "localization-text", "area-settings", "field-exits", "treasure", "palettes", "world-settings", "world-navigation", "chip-animations", "project-overlay", "ctp-export"],
                })
            if route == "/api/dashboard":
                langs = languages(STORE)
                return self.send_json({
                    "game": {"root": str(GAME_ROOT), "archive": str(ARCHIVE.path), "resourceCount": len(ARCHIVE.entries)},
                    "project": {"root": str(PROJECT_ROOT), "changeCount": len(STORE.changes())},
                    "languages": langs, "defaultLanguage": "en" if "en" in langs else (langs[0] if langs else ""),
                })
            if route == "/api/text-files":
                return self.send_json({"language": query.get("language", "en"), "rows": text_files(STORE, query.get("language", "en"))})
            if route == "/api/messages":
                return self.send_json(load_messages(STORE, query["path"], query.get("source", "mine")))
            if route == "/api/scenes":
                return self.send_json(load_scenes(STORE, query.get("source", "mine"), query.get("language", "en")))
            if route == "/api/palette-files":
                return self.send_json({"rows": palette_files(STORE)})
            if route == "/api/palette":
                return self.send_json(load_palette(STORE, query["path"], query.get("source", "mine")))
            if route == "/api/exits":
                return self.send_json(load_exits(STORE, query.get("source", "mine")))
            if route == "/api/treasure":
                return self.send_json(load_treasure(STORE, query.get("source", "mine"), query.get("language", "en")))
            if route == "/api/worlds":
                return self.send_json(load_worlds(STORE, query.get("source", "mine")))
            if route == "/api/world-navigation":
                return self.send_json(load_world_navigation(STORE, query.get("source", "mine"), query.get("language", "en")))
            if route == "/api/chip-animations":
                return self.send_json(load_chip_animations(STORE, query.get("source", "mine")))
            if route == "/api/datamap":
                return self.send_json(build_data_map(STORE))
            if route == "/api/changes":
                return self.send_json({"rows": STORE.changes()})
            return self.send_json({"error": "Not found"}, 404)
        except (KeyError, ValueError, RuntimeError, OSError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            body = self.read_json()
            if route == "/api/messages/save":
                result = save_messages(STORE, str(body["path"]), str(body["sha256"]), list(body.get("edits") or []))
            elif route == "/api/scenes/save":
                result = save_scene(STORE, int(body["id"]), str(body["sha256"]), dict(body.get("values") or {}), str(body.get("language", "en")))
            elif route == "/api/palette/save":
                result = save_palette(STORE, str(body["path"]), str(body["sha256"]), list(body.get("edits") or []))
            elif route == "/api/exits/save":
                result = save_exits(STORE, str(body["dataSha256"]), str(body["offsetSha256"]), list(body.get("edits") or []))
            elif route == "/api/treasure/save":
                result = save_treasure(STORE, str(body["dataSha256"]), str(body["offsetSha256"]), list(body.get("edits") or []), str(body.get("language", "en")))
            elif route == "/api/worlds/save":
                result = save_worlds(STORE, str(body["sha256"]), list(body.get("edits") or []))
            elif route == "/api/world-navigation/save":
                result = save_world_navigation(STORE, str(body["path"]), str(body["sha256"]), list(body.get("edits") or []), str(body.get("language", "en")))
            elif route == "/api/chip-animations/save":
                result = save_chip_animations(STORE, str(body["path"]), str(body["sha256"]), list(body.get("edits") or []))
            elif route == "/api/export":
                result = STORE.export_ctp()
            elif route == "/api/revert":
                STORE.revert(str(body["path"]))
                result = {"rows": STORE.changes()}
            else:
                return self.send_json({"error": "Not found"}, 404)
            self.send_json(result)
        except PermissionError as error:
            self.send_json({"error": str(error)}, 403)
        except (KeyError, TypeError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
