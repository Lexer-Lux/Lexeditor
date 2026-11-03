"""Loopback service for existing Verdite2 settings and source-mod metadata."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_http import PluginRequestHandler
from . import model

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def data_map() -> dict:
    rows = [
        {"filename": "interface.ini", "controls": "Mouse and stick sensitivity, mouse look inversion.",
         "notes": "Other Verdite2 preferences and ImGui layout remain unchanged.",
         "status": "partial", "coverage": "structured", "target": "settings", "openable": True},
        {"filename": "mods/<mod>/mod.json and *.cs", "controls": "Verdite2 source mods managed through the shared Mods tab.",
         "notes": "The existing native loader compiles and runs source mods. Installed-game acceptance is in progress.",
         "status": "partial", "coverage": "structured", "target": "mods", "openable": True},
        {"filename": "settings.json", "controls": "Native active-mod ids and controller/keyboard bindings.",
         "notes": "The adapter updates its own active ids and preserves the other fields. Separate run/interact controls are under investigation.",
         "status": "partial", "coverage": "structured", "target": "settings", "openable": True},
        {"filename": "carda.sav / cardb.sav", "controls": "The game's memory-card saves.",
         "notes": "The editor does not modify memory-card saves.", "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
        {"filename": "Disc: SLUS-00158", "controls": "Items, characters, enemies, maps, scripts, models, textures and audio.",
         "notes": "Initial scope is Mods and Settings. Disc records are not exposed as editable data.",
         "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
        {"filename": "Remaster packs", "controls": "Verdite2's material, lighting, atmosphere and scene authoring.",
         "notes": "Use the native Remaster Editor. Pack editing has not been integrated into Lexeditor.",
         "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
    ]
    return {"rows": rows}


class Handler(PluginRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/plugin":
                self.send_json({"apiVersion": 1, "pluginId": "kings-field2", "name": "King's Field II",
                                "hosted": True, "windowHost": "webview2", "capabilities": ["native-source-mods", "player-settings"]})
            elif path == "/api/state":
                self.send_json({"game": model.installation(model.game_root()), "preferences": model.preferences(model.data_root())})
            elif path == "/api/datamap":
                self.send_json(data_map())
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
                    self.send_json({"error": "Shared UI asset not found"}, 404)
            else:
                self.send_json({"error": "Not found"}, 404)
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/preferences":
            self.send_json({"error": "Not found"}, 404)
            return
        # Player preferences are not editable game records or a mod project.
        # No mod is created to change sensitivity. The game must be closed.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                raise ValueError("Preferences request exceeds the 64 KiB limit")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Preferences must be an object")
            if not model.installation(model.game_root())["supported"]:
                raise ValueError("Locate a supported Verdite2 installation before saving preferences")
            self.send_json(model.save_preferences(model.data_root(), payload.get("changes"), payload.get("fingerprint", "")))
        except (OSError, ValueError, TypeError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), Handler).serve_forever()
