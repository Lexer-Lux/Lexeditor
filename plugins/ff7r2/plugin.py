"""Final Fantasy VII Rebirth plugin lifecycle.

Gameplay editing is deliberately bounded to proved IoStore-state DataObject
fields staged inside an editable project; the installed game stays source-only.
Presentation support remains ReShade plus the pinned Shader Injector helper.

Rebirth loads through DXGI. Its Win64 folder already contains a d3d12.dll of
its own - the Agility SDK's - and Lexeditor refuses to overwrite a DLL that is
not ReShade, so choosing that renderer would fail rather than break the game.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from core.plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from plugins.ff7r2 import shader_injector
from core.service_session import LocalPluginSession, request_json


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
PROJECT_TEMPLATE = PLUGIN_ROOT / "project_template"
DEFAULT_PROJECT = (
    Path(os.environ.get("LOCALAPPDATA", str(ROOT / "out")))
    / "Lexeditor" / "Mods" / "FF7R2"
)

# The loader Rebirth wants. Named here rather than left to the page, because
# picking d3d12 is the one choice that cannot work in this game.
RENDERER = "dxgi"
EXECUTABLE = "End/Binaries/Win64/ff7rebirth_.exe"


def check() -> list[str]:
    return []


class Ff7r2Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="plugins.ff7r2.server", plugin_id="ff7r2", app_root=ROOT,
                         check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"ff7r2": PLUGIN}, "ff7r2")


def smoke() -> list[str]:
    """Exercise the managed Rebirth service without game or proprietary data."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-ff7r2-smoke-") as temp_name:
        project = Path(temp_name) / "project"
        project.mkdir()
        (project / "lexeditor-project.json").write_text(
            '{"format":1,"game":"ff7r2"}\n', encoding="utf-8")
        session = Ff7r2Session({"LEXEDITOR_FF7R2_PROJECT": str(project)})
        with session:
            identity = request_json(session.url + "api/plugin")
            required = {"data-map", "player-parameter", "fixed-width-edit", "project-staging", "package-candidate"}
            if identity.get("pluginId") != "ff7r2" or not required.issubset(identity.get("capabilities", [])):
                raise RuntimeError("FF7R2 service returned the wrong managed identity/capabilities")
            mapped = request_json(session.url + "api/datamap")
            player = next((row for row in mapped.get("rows", [])
                           if row.get("target") == "characters"), None)
            if not player or player.get("coverage") != "structured" or player.get("status") != "partial":
                raise RuntimeError("FF7R2 Data Map did not report bounded PlayerParameter coverage")
            workspace = request_json(session.url + "api/workspace")
            if workspace.get("playerParameter", {}).get("sourcePresent") is not False:
                raise RuntimeError("FF7R2 smoke unexpectedly found proprietary source data")
        if not session.wait_closed():
            raise RuntimeError("FF7R2 child service port is still open after smoke shutdown")
    return [
        "managed FF7R2 service identity and bounded capabilities confirmed",
        "Data Map exposes PlayerParameter as partial structured coverage",
        "empty project reports no proprietary source data",
        "host-owned child service stopped cleanly",
    ]


PLUGIN = GamePlugin(
    **plugin_defaults(__file__),
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=Ff7r2Session,
    projects=project_spec(__file__, default_root=DEFAULT_PROJECT),
    helper_name='Shader Injector',
    helper_pinned=shader_injector.VERSION,
    helper_status_for_root=shader_injector.helper_status,
    helper_install_for_root=shader_injector.helper_install,
    helper_upstream=shader_injector.upstream_release,
    helper_actions={'clear_shader_cache': shader_injector.clear_cache_action},
    installation=install_spec(__file__),
)
