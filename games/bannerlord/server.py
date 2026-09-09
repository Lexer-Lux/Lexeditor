"""Local JSON/UI service for the Bannerlord Lexeditor plugin."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .gauntlet_data import (
    augment_data_map as augment_gauntlet_data_map,
    list_prefabs,
    read_prefab,
    save_prefab,
)
from .module_data import data_map, read_submodule, save_module
from .module_xml_data import (
    augment_data_map as augment_module_xml_data_map,
    list_documents,
    read_document,
    save_document,
)
from .skill_data import (
    read_effect_definitions,
    read_skill_definitions,
    save_effect_definitions,
    save_skill_definitions,
)
from .perk_data import (
    augment_data_map,
    read_perk_definitions,
    read_xp_source_definitions,
    save_perk_definitions,
    save_xp_source_definitions,
)
from .runtime_data import deployment_status
from .runtime_overrides import (
    augment_data_map as augment_runtime_data_map,
    read_runtime_overrides,
    save_runtime_overrides,
)
from .settings_data import read_mcm_defaults, save_mcm_defaults
from .project_data import (
    primary_project_file,
    read_project_file,
    read_source,
    run_build,
    save_project_properties,
    save_source,
)


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PROJECT = Path(os.environ.get("LEXEDITOR_BANNERLORD_PROJECT", r"C:\Bannermod"))
PORT = int(os.environ.get("LEXEDITOR_PORT", "0"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED", "0") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "")


def project_summary() -> dict:
    project_file = primary_project_file(PROJECT)
    return {
        "root": str(PROJECT),
        "projectFile": read_project_file(project_file) if project_file else None,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_file(self, target: Path):
        data = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            mimetypes.guess_type(target.name)[0] or "application/octet-stream",
        )
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            self.send_file(PLUGIN_ROOT / "editor.html")
            return
        if path.startswith("/shared/"):
            shared = (LEXEDITOR_ROOT / "ui").resolve()
            target = (shared / path.removeprefix("/shared/")).resolve()
            if shared in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Shared UI asset not found"}, 404)
            return
        if path.startswith("/bannerlord/"):
            target = (PLUGIN_ROOT / path.removeprefix("/bannerlord/")).resolve()
            if PLUGIN_ROOT in target.parents and target.is_file():
                self.send_file(target)
            else:
                self.send_json({"error": "Bannerlord plugin asset not found"}, 404)
            return

        if path == "/api/plugin":
            self.send_json(
                {
                    "apiVersion": 1,
                    "pluginId": "bannerlord",
                    "name": "Mount & Blade II: Bannerlord",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "editorRoot": str(PLUGIN_ROOT),
                    "projectRoot": str(PROJECT),
                    "capabilities": [
                        "module-metadata",
                        "module-dependencies",
                        "module-submodules",
                        "module-xml-registrations",
                        "msbuild-project",
                        "dotnet-build",
                        "source-only-editor",
                        "custom-skills",
                        "custom-skill-effects",
                        "custom-skill-perks",
                        "custom-skill-xp-sources",
                        "mcm-default-settings",
                        "runtime-overrides",
                        "gauntlet-prefabs",
                        "moduledata-records",
                        "deployment-diagnostics",
                        "data-map",
                    ],
                }
            )
            return
        if path == "/api/module":
            source = PROJECT / "SubModule.xml"
            if not source.is_file():
                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)
                return
            try:
                self.send_json(read_submodule(source))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/project":
            try:
                self.send_json(project_summary())
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/source":
            requested = (query.get("path") or [""])[0]
            if not requested:
                self.send_json({"error": "Missing source path"}, 400)
                return
            try:
                self.send_json(read_source(PROJECT, requested))
            except (ValueError, FileNotFoundError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/skills":
            try:
                self.send_json(read_skill_definitions(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/effects":
            try:
                self.send_json(read_effect_definitions(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/perks":
            try:
                self.send_json(read_perk_definitions(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/xp-sources":
            try:
                self.send_json(read_xp_source_definitions(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/settings-defaults":
            try:
                self.send_json(read_mcm_defaults(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/runtime-overrides":
            try:
                self.send_json(read_runtime_overrides(PROJECT))
            except (ValueError, RuntimeError, FileNotFoundError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/module-data-files":
            try:
                self.send_json({"files": list_documents(PROJECT)})
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/module-data":
            requested = (query.get("path") or [""])[0]
            if not requested:
                self.send_json({"error": "Missing ModuleData XML path"}, 400)
                return
            try:
                self.send_json(read_document(PROJECT, requested))
            except (ValueError, FileNotFoundError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/gauntlet-files":
            try:
                self.send_json({"files": list_prefabs(PROJECT)})
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/gauntlet":
            requested = (query.get("path") or [""])[0]
            if not requested:
                self.send_json({"error": "Missing Gauntlet prefab path"}, 400)
                return
            try:
                self.send_json(read_prefab(PROJECT, requested))
            except (ValueError, FileNotFoundError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/deployment":
            try:
                self.send_json(deployment_status(PROJECT))
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/datamap":
            base = augment_module_xml_data_map(
                PROJECT,
                augment_gauntlet_data_map(augment_data_map(data_map(PROJECT))),
            )
            try:
                self.send_json(augment_runtime_data_map(base, read_runtime_overrides(PROJECT)))
            except Exception:
                self.send_json(base)
            return
        self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/module/save":
            source = PROJECT / "SubModule.xml"
            if not source.is_file():
                self.send_json({"error": f"SubModule.xml not found: {source}"}, 404)
                return
            try:
                self.send_json(save_module(source, self.read_json()))
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/skills/save":
            try:
                self.send_json(save_skill_definitions(PROJECT, self.read_json()))
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/effects/save":
            try:
                payload = self.read_json()
                self.send_json(save_effect_definitions(PROJECT, list(payload.get("edits") or [])))
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/perks/save":
            try:
                payload = self.read_json()
                self.send_json(save_perk_definitions(PROJECT, list(payload.get("edits") or [])))
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/xp-sources/save":
            try:
                payload = self.read_json()
                self.send_json(save_xp_source_definitions(PROJECT, list(payload.get("edits") or [])))
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/settings-defaults/save":
            try:
                payload = self.read_json()
                self.send_json(save_mcm_defaults(PROJECT, list(payload.get("edits") or [])))
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/runtime-overrides/save":
            try:
                self.send_json(save_runtime_overrides(PROJECT, self.read_json()))
            except (
                ValueError,
                TypeError,
                RuntimeError,
                FileNotFoundError,
                json.JSONDecodeError,
            ) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/module-data/save":
            try:
                payload = self.read_json()
                self.send_json(
                    save_document(
                        PROJECT,
                        str(payload.get("path") or ""),
                        list(payload.get("edits") or []),
                    )
                )
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/gauntlet/save":
            try:
                payload = self.read_json()
                self.send_json(
                    save_prefab(
                        PROJECT,
                        str(payload.get("path") or ""),
                        list(payload.get("edits") or []),
                    )
                )
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/project/save":
            project_file = primary_project_file(PROJECT)
            if project_file is None:
                self.send_json({"error": f"No .csproj found in {PROJECT}"}, 404)
                return
            try:
                payload = self.read_json()
                self.send_json(
                    save_project_properties(project_file, dict(payload.get("edits") or {}))
                )
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/source/save":
            try:
                payload = self.read_json()
                self.send_json(
                    save_source(
                        PROJECT,
                        str(payload.get("path") or ""),
                        str(payload.get("text") or ""),
                    )
                )
            except (ValueError, TypeError, FileNotFoundError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        if path == "/api/build":
            try:
                payload = self.read_json()
                self.send_json(
                    run_build(
                        PROJECT,
                        requested=payload.get("project"),
                        configuration=payload.get("configuration", "Debug"),
                    )
                )
            except (ValueError, FileNotFoundError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except RuntimeError as error:
                self.send_json({"error": str(error)}, 503)
            except Exception as error:
                self.send_json({"error": str(error)}, 500)
            return
        self.send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
