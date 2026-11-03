"""Shared loopback settings service and Data Map for native source ports."""
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from core.plugin_http import PluginRequestHandler
from core.native_port_settings import NativePortSettings


def loader_details(descriptor: dict, app_root: Path) -> dict:
    loading = json.loads((app_root / "ui/mod-loading.json").read_text(encoding="utf-8"))["plugins"][descriptor["id"]]
    return {"loader": loading["loader"], "output": loading["structure"],
            "order": loading["overriding"],
            "safety": "Lexeditor preserves saves, disc data and external mods. Settings and deployment require the game to be closed.",
            "removal": descriptor["nativePort"]["modLoading"]["removal"]}


def data_map(model: NativePortSettings) -> dict:
    return {"rows": [
        {"filename": "interface.ini", "controls": "Port controls, sensitivity, view distance, distance fade and native mod flags.",
         "notes": "Other preferences and window layout remain unchanged.",
         "status": "partial", "coverage": "structured", "target": "settings", "openable": True},
        {"filename": "mods/<mod>/mod.json and *.cs", "controls": "Native source mods managed through the shared Mods tab.",
         "notes": "The port compiles source mods and attaches their runtime hooks. Hook compatibility is not inferred.",
         "status": "partial", "coverage": "structured", "target": "mods", "openable": True},
        {"filename": "settings.json", "controls": "Keyboard/controller bindings and native runtime configuration.",
         "notes": "Edit bindings in the native Input menu. Source-mod deployment leaves this file unchanged.",
         "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
        {"filename": "carda.sav / cardb.sav", "controls": "Memory-card saves.",
         "notes": "Lexeditor does not edit saves.", "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
        {"filename": "Disc: " + model.native["configIdentity"][0], "controls": "Items, characters, enemies, maps, scripts, models, textures and audio.",
         "notes": "Disc records do not have structured editors here.",
         "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
        {"filename": "Native asset packs", "controls": "Replacement textures, audio and other assets supported by the port.",
         "notes": "Pack editing is not integrated into Lexeditor.",
         "status": "not-integrated", "coverage": "unavailable", "target": None, "openable": False},
    ]}


def handler(model: NativePortSettings, plugin_file: str):
    plugin_root = Path(plugin_file).resolve().parent
    app_root = plugin_root.parents[1]

    class Handler(PluginRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/plugin":
                    self.send_json({"apiVersion": 1, "pluginId": model.descriptor["id"],
                                    "name": model.descriptor["name"], "accent": model.descriptor["accent"],
                                    "portName": model.native["dataDirectory"], "gameIdentity": model.native["gameIdentity"],
                                    "modLoading": loader_details(model.descriptor, app_root),
                                    "hosted": True, "windowHost": "webview2",
                                    "capabilities": ["native-source-mods", "player-settings"]})
                elif path == "/api/state":
                    self.send_json({"game": model.installation(model.game_root()), "preferences": model.preferences(model.data_root())})
                elif path == "/api/datamap":
                    self.send_json(data_map(model))
                elif path == "/":
                    self.send_file(plugin_root / "editor.html")
                elif self.send_page_module(plugin_root, path):
                    return
                elif path.startswith("/shared/"):
                    shared = (app_root / "ui").resolve()
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
            if urlparse(self.path).path != "/api/preferences":
                self.send_json({"error": "Not found"}, 404)
                return
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
                    raise ValueError("Locate a supported game installation before saving preferences")
                self.send_json(model.save_preferences(model.data_root(), payload.get("changes"), payload.get("fingerprint", "")))
            except (OSError, ValueError, TypeError) as error:
                self.send_json({"error": str(error)}, 400)

    return Handler


def serve(model: NativePortSettings, plugin_file: str):
    ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("LEXEDITOR_PORT", "0"))), handler(model, plugin_file)).serve_forever()
