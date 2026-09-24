"""Factorio plugin lifecycle and safe project boundary."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile

from core.plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from core.service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
USER_ROOT = Path(os.environ.get("LOCALAPPDATA", ROOT / "out")) / "Lexeditor"
DEFAULT_PROJECT = USER_ROOT / "projects" / "factorio" / "LexeditorFactorioMod"


def project_root() -> Path:
    return Path(os.environ.get("LEXEDITOR_FACTORIO_PROJECT", DEFAULT_PROJECT)).expanduser().resolve()


def check() -> list[str]:
    # Installation and project descriptors are validated by the shared host.
    # A project is allowed to open before its source dump exists so the Info
    # page can give the exact --dump-data setup instructions.
    return []


class FactorioSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        environment = {"LEXEDITOR_FACTORIO_PROJECT": str(project_root())}
        environment.update(extra_env or {})
        super().__init__(
            module="plugins.factorio.server",
            plugin_id="factorio",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_FACTORIO_PORT",
            extra_env=environment,
        )



def _request_json(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def smoke() -> list[str]:
    """Exercise the packaged service using only a synthetic temporary project."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-factorio-smoke-") as temp_name:
        project = Path(temp_name) / "project"
        source_root = project / "source"
        source_root.mkdir(parents=True)
        (project / "factorio-project.json").write_text(json.dumps({
            "format": 1,
            "mod": {
                "name": "lexeditor-factorio-smoke",
                "version": "0.1.0",
                "title": "Lexeditor Factorio Smoke",
                "dependencies": [],
            },
        }), encoding="utf-8")
        source = source_root / "data-raw-dump.json"
        source.write_text(json.dumps({
            "recipe-category": {
                "crafting": {"type": "recipe-category", "name": "crafting"},
            },
            "item": {
                "iron-plate": {
                    "type": "item", "name": "iron-plate", "stack_size": 100,
                },
            },
            "recipe": {
                "iron-plate": {
                    "type": "recipe", "name": "iron-plate",
                    "enabled": True, "energy_required": 0.5,
                    "maximum_productivity": 3.0, "categories": ["crafting"],
                    "ingredients": [], "results": [
                        {"type": "item", "name": "iron-plate", "amount": 1},
                    ],
                },
            },
            "assembling-machine": {
                "fixture-assembler": {
                    "type": "assembling-machine", "name": "fixture-assembler",
                    "crafting_speed": 1.0, "crafting_categories": ["crafting"],
                    "energy_usage": "1kW",
                },
            },
            "technology": {
                "fixture-tech": {
                    "type": "technology", "name": "fixture-tech",
                    "enabled": True, "prerequisites": [], "effects": [],
                    "unit": {"count": 1, "time": 1, "ingredients": []},
                },
            },
        }), encoding="utf-8")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        with FactorioSession({
            "LEXEDITOR_FACTORIO_PROJECT": str(project),
            "FACTORIO_GAME_ROOT": "",
        }) as session:
            identity = _request_json(session.url + "api/plugin")
            if identity.get("pluginId") != "factorio":
                raise RuntimeError("Factorio smoke service returned the wrong plugin identity")
            recipes = _request_json(session.url + "api/data?kind=recipes")
            if not recipes.get("rows") or recipes["rows"][0].get("name") != "iron-plate":
                raise RuntimeError("Factorio smoke project did not expose its structured recipe")
            edit = _request_json(session.url + "api/edit", {
                "kind": "recipes", "name": "iron-plate",
                "changes": {
                    "enabled": True,
                    "energy_required": 0.75,
                    "maximum_productivity": 3.0,
                },
            })
            if edit.get("row", {}).get("energyRequired") != 0.75:
                raise RuntimeError("Factorio smoke edit did not round-trip through the service")
            _request_json(session.url + "api/save", {})
            exported = _request_json(session.url + "api/export", {})
            candidate = Path(exported["path"])
            if not candidate.is_file():
                raise RuntimeError("Factorio smoke export did not create a candidate")
            with zipfile.ZipFile(candidate) as archive:
                script = archive.read(
                    "lexeditor-factorio-smoke_0.1.0/data-final-fixes.lua"
                ).decode("utf-8")
            if "p.energy_required = 0.75" not in script:
                raise RuntimeError("Factorio smoke candidate did not contain the edited recipe")
        if hashlib.sha256(source.read_bytes()).hexdigest() != before:
            raise RuntimeError("Factorio smoke changed the immutable source dump")
        if not session.process or session.process.poll() is None:
            raise RuntimeError("Factorio child service still runs after host shutdown")
        if not session.wait_closed():
            raise RuntimeError("Factorio child port is still open after host shutdown")
    return [
        "Factorio managed service identity confirmed",
        "synthetic recipe loaded through the structured API",
        "recipe edit saved and exported to a native mod candidate",
        "source prototype dump remained byte-identical",
        "host-owned Factorio child service stopped cleanly",
    ]

def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"factorio": PLUGIN}, "factorio")


PLUGIN = GamePlugin(
    plugin_id="factorio",
    name="Factorio",
    accent="#e69b36",
    check=check,
    launch=launch,
    session_factory=FactorioSession,
    smoke=smoke,
    process_names=("factorio.exe",),
    projects=ModProjectSpec(
        root_env="LEXEDITOR_FACTORIO_PROJECT",
        default_root=DEFAULT_PROJECT,
        required_paths=("factorio-project.json",),
        template_root=PLUGIN_ROOT / "template",
        content_types=(
            ("Project data", (".json",)),
            ("Generated mods", (".zip",)),
        ),
    ),
    installation=GameInstallSpec(
        root_env="FACTORIO_GAME_ROOT",
        required_paths=("bin/x64/factorio.exe", "data/base/info.json", "data/core"),
        steam_app_id="427520",
        install_dir_names=("Factorio",),
        default_roots=(
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Factorio"),
            Path(r"C:\Program Files\Factorio"),
        ),
        launch_path="bin/x64/factorio.exe",
    ),
)
