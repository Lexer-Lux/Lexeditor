"""Final Palworld loopback service surface, including read-only loader state."""

from __future__ import annotations

import os
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import loader_state
from .build_server import Handler as BuildHandler
from .server import PORT, info_document


class Handler(BuildHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/plugin":
            self.send_json({
                "apiVersion": 1,
                "pluginId": "palworld",
                "name": "Palworld",
                "hosted": True,
                "windowHost": "webview2",
                "capabilities": [
                    "official-package-info",
                    "palschema-raw-patches",
                    "palschema-generated-schemas",
                    "palschema-add-existing-row-fields",
                    "official-package-build",
                    "official-local-workshop-deploy",
                    "official-loader-state-readonly",
                    "data-map",
                ],
            })
            return
        if path == "/api/loader-state":
            try:
                game_value = os.environ.get("LEXEDITOR_PALWORLD_ROOT")
                game_root = Path(game_value).expanduser().resolve() if game_value else None
                package_name = str(info_document().data.get("PackageName", ""))
                payload = loader_state.status(game_root, package_name)
                payload["readOnly"] = True
                self.send_json(payload)
            except (OSError, ValueError) as error:
                self.send_json({
                    "available": False,
                    "readOnly": True,
                    "error": str(error),
                    "active": False,
                    "listed": False,
                })
            return
        super().do_GET()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
