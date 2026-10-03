"""Dark Souls Remastered detection and isolated item projects."""
from pathlib import Path

from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def check() -> list[str]:
    problems = [f"Missing Dark Souls support file: {name}"
            for name in ("editor.html", "editor.js", "editor.css", "server.py", "data_map.py", "metadata/SOURCE.json", "project-template/.lexeditor-ds1-project")
            if not (PLUGIN_ROOT / name).is_file()]
    if not problems:
        from .formats import TABLES, schema
        try:
            for table in TABLES: schema(table)
        except (ValueError, OSError, KeyError) as error:
            problems.append(f"Invalid DS1 item metadata: {error}")
    return problems


class DS1Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="plugins.ds1.server", plugin_id="ds1",
                         app_root=ROOT, check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"ds1": PLUGIN}, "ds1")


PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                    session_factory=DS1Session, installation=install_spec(__file__),
                    projects=project_spec(__file__, default_root=Path.home() / 'Lexeditor Mods' / 'Dark Souls Remastered'))
