"""Loopback service for the supported King's Field I source port."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_http import PluginRequestHandler
from . import settings

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent

DATA_MAP = [
    {"filename": "interface.ini", "controls": "Native display and control settings", "status": "partial", "coverage": "view", "target": "settings",
     "notes": "View distance, smooth distance fade and hold to run are editable. Other native settings remain in the port's F1 menu."},
    {"filename": "settings.json", "controls": "Keyboard and controller bindings", "status": "partial", "coverage": "view", "target": "settings",
     "notes": "Control setup offers Classic Controls, Modern Controls or keeping your bindings. Individual bindings remain editable in the port's Input settings."},
    {"filename": "mods/*/mod.json and C# sources", "controls": "Native runtime mods", "status": "partial", "coverage": "view", "target": "mods",
     "notes": "The shared Mods tab imports and enables native source mods. Hook compatibility needs testing for each mod."},
    {"filename": "KF/B1 through KF/B5", "controls": "Floors, models, encounters and scripts", "status": "not-integrated",
     "notes": "The port reads these areas from your disc. Structured data editing is not implemented in Lexeditor yet."},
    {"filename": "KF/COM and disc overlays", "controls": "Shared textures, text, items, magic and game logic", "status": "not-integrated",
     "notes": "These remain read-only disc data. Format-specific editors are not implemented yet."},
    {"filename": "carda.sav and cardb.sav", "controls": "PlayStation memory-card saves", "status": "not-integrated",
     "notes": "The game owns these saves. This integration does not edit or replace memory cards."},
]


class Handler(PluginRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/plugin":
            self.send_json({"apiVersion": 1, "pluginId": "kf1", "name": "King's Field I", "hosted": True,
                            "windowHost": "webview2", "capabilities": ["native-port-settings", "data-map"]})
        elif path == "/api/settings":
            try:
                self.send_json(settings.payload())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 400)
        elif path == "/api/data-map":
            self.send_json({"rows": DATA_MAP})
        elif path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
        elif self.send_page_module(PLUGIN_ROOT, path):
            return
        elif path.startswith("/shared/"):
            shared = (ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/settings", "/api/settings/controls"}:
            self.send_json({"error": "Not found"}, 404)
            return
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("Invalid settings request size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Settings request must be an object")
            if path == "/api/settings/controls":
                self.send_json(settings.setup_controls(body))
            else:
                self.send_json(settings.save(body))
        except (OSError, ValueError, TypeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), Handler).serve_forever()
