"""Loopback Project Zomboid editor service."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

from . import core, craftrecipe, datamap, evolvedrecipe, fluid, model, sound, vehicle, zedscript

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
MAX_BODY = 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
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

    def read_json(self):
        raw_length = self.headers.get("Content-Length", "")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise core.ProjectZomboidError("Invalid request length") from error
        if length < 0 or length > MAX_BODY:
            raise core.ProjectZomboidError("Request body is too large")
        data = self.rfile.read(length)
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise core.ProjectZomboidError("Request body must be JSON") from error
        if not isinstance(payload, dict):
            raise core.ProjectZomboidError("Request body must be a JSON object")
        return payload

    def project(self) -> Path:
        return core.project_root()

    def do_GET(self):
        try:
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
                self.send_json({
                    "apiVersion": 1,
                    "pluginId": "project-zomboid",
                    "name": "Project Zomboid",
                    "hosted": True,
                    "windowHost": "webview2",
                    "capabilities": [
                        "mod-info", "build42-items", "build42-evolvedrecipes",
                        "build42-craftrecipes", "build42-fluids", "build42-vehicles",
                        "build42-sounds", "build42-models", "build42-zedscript-inventory",
                        "data-map", "local-deploy",
                    ],
                    "editorRoot": str(PLUGIN_ROOT),
                })
            elif path == "/api/mod-info":
                self.send_json(core.read_mod_info(self.project()))
            elif path == "/api/items":
                self.send_json(core.read_items(self.project()))
            elif path == "/api/evolvedrecipes":
                self.send_json(evolvedrecipe.read(self.project()))
            elif path == "/api/craftrecipes":
                self.send_json(craftrecipe.read(self.project()))
            elif path == "/api/fluids":
                self.send_json(fluid.read(self.project()))
            elif path == "/api/vehicles":
                self.send_json(vehicle.read(self.project()))
            elif path == "/api/sounds":
                self.send_json(sound.read(self.project()))
            elif path == "/api/models":
                self.send_json(model.read(self.project()))
            elif path == "/api/zedscript":
                self.send_json(zedscript.inventory(self.project()))
            elif path == "/api/datamap":
                self.send_json(datamap.read(self.project()))
            elif path == "/api/deployment":
                self.send_json(core.deployment_state(self.project()))
            else:
                self.send_json({"error": "Not found"}, 404)
        except (core.ProjectZomboidError, OSError) as error:
            self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            payload = self.read_json()
            root = self.project()
            identity = {"path", "module", "id", "sha256", "edits"}
            if path == "/api/mod-info/save":
                if set(payload) != {"sha256", "edits"}:
                    raise core.ProjectZomboidError("mod.info save requires sha256 and edits")
                result = core.save_mod_info(root, payload["sha256"], payload["edits"])
            elif path == "/api/items/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Item save requires path, module, id, sha256 and edits")
                result = core.save_item(root, str(payload["path"]), str(payload["module"]),
                                        str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/evolvedrecipes/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Evolved recipe save requires path, module, id, sha256 and edits")
                result = evolvedrecipe.save(root, str(payload["path"]), str(payload["module"]),
                                             str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/craftrecipes/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Craft recipe save requires path, module, id, sha256 and edits")
                result = craftrecipe.save(root, str(payload["path"]), str(payload["module"]),
                                           str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/fluids/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Fluid save requires path, module, id, sha256 and edits")
                result = fluid.save(root, str(payload["path"]), str(payload["module"]),
                                    str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/vehicles/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Vehicle save requires path, module, id, sha256 and edits")
                result = vehicle.save(root, str(payload["path"]), str(payload["module"]),
                                      str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/sounds/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Sound save requires path, module, id, sha256 and edits")
                result = sound.save(root, str(payload["path"]), str(payload["module"]),
                                    str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/models/save":
                if set(payload) != identity:
                    raise core.ProjectZomboidError("Model save requires path, module, id, sha256 and edits")
                result = model.save(root, str(payload["path"]), str(payload["module"]),
                                    str(payload["id"]), str(payload["sha256"]), payload["edits"])
            elif path == "/api/deploy":
                if payload:
                    raise core.ProjectZomboidError("Deploy does not accept arguments")
                result = core.deploy(root)
            elif path == "/api/undeploy":
                if payload:
                    raise core.ProjectZomboidError("Undeploy does not accept arguments")
                result = core.undeploy(root)
            else:
                self.send_json({"error": "Not found"}, 404)
                return
            self.send_json(result)
        except (core.ProjectZomboidError, OSError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
