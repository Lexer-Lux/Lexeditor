"""Loopback service for the Final Fantasy VII Rebirth plugin.

It serves the page and the shared UI, answers where the game is, and runs
Shader Injector: install, switch on and off, remove, settings, and clearing the
game's shader cache. Every ReShade action goes through the desktop host, which
owns the one copy of ReShade and Lexeditor's effects.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from games.ff7r2 import shader_injector
from plugin_http import PluginRequestHandler


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY_BYTES = 64 * 1024


def game_root() -> Path | None:
    value = os.environ.get("LEXEDITOR_FF7R2_ROOT", "").strip()
    if not value:
        return None
    root = Path(value)
    return root if root.is_dir() else None


def injector_folder() -> Path | None:
    """The folder Shader Injector is declared to live in, if the game has it."""
    root = game_root()
    if root is None:
        return None
    folder = root / shader_injector.INSTALL_FOLDER
    return folder if folder.is_dir() else None


def injector_state() -> dict:
    folder = injector_folder()
    if folder is None:
        return {"available": False,
                "reason": "Locate Final Fantasy VII Rebirth first. Shader Injector goes in its End/Binaries/Win64 folder."}
    return {"available": True, **shader_injector.status(folder)}


class Handler(PluginRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
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
            self.send_json({"apiVersion": 1, "pluginId": "ff7r2",
                            "name": "Final Fantasy VII Rebirth",
                            "hosted": True, "windowHost": "webview2",
                            "capabilities": ["reshade", "shader-injector"]})
        elif path == "/api/game":
            root = game_root()
            binaries = root / "End/Binaries/Win64" if root else None
            self.send_json({
                "root": str(root) if root else "",
                "found": root is not None,
                # Rebirth ships its own d3d12.dll, so dxgi is the loader.
                "renderer": "dxgi",
                "binaries": str(binaries) if binaries else "",
            })
        elif path == "/api/shader-injector":
            try:
                self.send_json(injector_state())
            except (OSError, ValueError) as error:
                self.send_json({"error": str(error)}, 500)
        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        # Reject browser cross-origin writes to this loopback service: these
        # routes change files inside the game folder.
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            self.send_json({"error": "Cross-origin writes are not permitted"}, 403)
            return
        actions = {
            "/api/shader-injector/install", "/api/shader-injector/uninstall",
            "/api/shader-injector/enabled", "/api/shader-injector/settings",
            "/api/shader-injector/clear-cache",
        }
        if path not in actions:
            self.send_json({"error": "Not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0") or 0)
            if size > MAX_BODY_BYTES:
                raise ValueError("Request is too large")
            body = json.loads(self.rfile.read(size) or b"{}") if size else {}
            if not isinstance(body, dict):
                raise ValueError("Request must be a JSON object")
            folder = injector_folder()
            if folder is None:
                raise ValueError("Locate Final Fantasy VII Rebirth before changing Shader Injector.")
            result = {}
            if path.endswith("/install"):
                result = shader_injector.install(folder)
            elif path.endswith("/uninstall"):
                result = shader_injector.uninstall(folder)
            elif path.endswith("/enabled"):
                if not isinstance(body.get("enabled"), bool):
                    raise ValueError("enabled must be true or false")
                shader_injector.set_enabled(folder, body["enabled"])
            elif path.endswith("/settings"):
                shader_injector.write_settings(folder, body.get("changes") or {})
            elif path.endswith("/clear-cache"):
                result = shader_injector.clear_shader_cache()
            self.send_json({"result": result, "status": injector_state()})
        except (OSError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
