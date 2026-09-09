"""Palworld service extension for transactional official-package build snapshots."""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

from . import build as package_build
from .package import PackageValidationError
from .server import Handler as EditorHandler, PLUGIN_ROOT, PORT, palschema_catalog_payload, project_root


def _validate_known_payloads() -> None:
    """Block packaging when an integrated payload family is already known invalid."""
    catalog = palschema_catalog_payload()
    broken = [row.get("path", row.get("name", "unknown")) for row in catalog.get("patches", []) if row.get("errors")]
    if broken:
        raise RuntimeError(
            "PalSchema raw patch validation failed; repair these files before building: "
            + ", ".join(str(value) for value in broken)
        )


class Handler(EditorHandler):
    def _same_editor_request(self) -> bool:
        port = self.server.server_address[1]
        host = self.headers.get("Host", "").casefold()
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return host in allowed_hosts and (origin is None or origin.casefold() == f"http://{host}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/build-ui-pre.js":
            self.send_file(PLUGIN_ROOT / "build-ui-pre.js")
            return
        if path == "/build-ui.js":
            self.send_file(PLUGIN_ROOT / "build-ui.js")
            return
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
                    "data-map",
                ],
            })
            return
        if path == "/api/build":
            try:
                _validate_known_payloads()
                payload = package_build.status(project_root())
                payload["ready"] = True
                self.send_json(payload)
            except Exception as error:
                self.send_json({
                    "ready": False,
                    "error": str(error),
                    "projectPath": str(project_root()),
                })
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/build/create", "/api/build/revert"}:
            super().do_POST()
            return
        if not self._same_editor_request():
            self.send_json({"error": "Only this editor may change the Palworld package build"}, 403)
            return
        try:
            payload = self.read_json()
            if payload:
                raise ValueError("Palworld build actions do not accept parameters")
            if path == "/api/build/create":
                _validate_known_payloads()
                result = package_build.build(project_root())
            else:
                result = package_build.revert(project_root())
            result["ready"] = True
            self.send_json(result)
        except (package_build.BuildOwnershipError, package_build.BuildChangedError) as error:
            self.send_json({"error": str(error)}, 409)
        except PackageValidationError as error:
            self.send_json({"error": str(error)}, 400)
        except (OSError, RuntimeError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
