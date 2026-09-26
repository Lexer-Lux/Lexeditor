"""Dark Souls III plugin registration and isolated project boundary."""
from __future__ import annotations

from pathlib import Path

from core.plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession

from .formats import DS3FormatError, TARGET_TABLES, load_schema


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
METADATA_ROOT = PLUGIN_ROOT / "metadata"
PROJECT_TEMPLATE = PLUGIN_ROOT / "project-template"
DEFAULT_PROJECT = Path.home() / "Lexeditor Mods" / "Dark Souls III"


def check() -> list[str]:
    required = [
        PLUGIN_ROOT / "editor.html",
        PLUGIN_ROOT / "editor.js",
        PLUGIN_ROOT / "boot.js",
        PLUGIN_ROOT / "editor.css",
        PLUGIN_ROOT / "project-template" / ".lexeditor-ds3-project",
        METADATA_ROOT / "SOURCE.json",
    ]
    for table in TARGET_TABLES:
        required.extend([
            METADATA_ROOT / "defs" / f"{table}.xml",
            METADATA_ROOT / "meta" / f"{table}.xml",
            METADATA_ROOT / "layouts" / f"{table}.json",
            METADATA_ROOT / "row_names" / f"{table}.json",
        ])
    problems = [
        f"Missing Dark Souls III plugin support file: {path}"
        for path in required if not path.is_file()
    ]
    if problems:
        return problems
    try:
        for table in TARGET_TABLES:
            load_schema(METADATA_ROOT, table)
    except (DS3FormatError, OSError, ValueError) as error:
        problems.append(f"Dark Souls III metadata is incomplete or invalid: {error}")
    return problems


class DS3Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(
            module="plugins.ds3.server",
            plugin_id="ds3",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_DS3_PORT",
            extra_env=extra_env,
        )


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"ds3": PLUGIN}, "ds3")


PLUGIN = GamePlugin(
    **plugin_defaults(__file__),
    check=check,
    launch=launch,
    session_factory=DS3Session,
    projects=project_spec(__file__, default_root=DEFAULT_PROJECT),
    installation=install_spec(__file__),
)
