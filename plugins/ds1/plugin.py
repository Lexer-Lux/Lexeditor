"""Dark Souls Remastered detection and isolated item projects."""
from pathlib import Path

from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession
from core.bundled_mods import BundledTweak
from . import ammunition_controls, ammunition_tweak

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent


def check() -> list[str]:
    problems = [f"Missing Dark Souls support file: {name}"
            for name in ("editor.html", "editor.js", "editor.css", "server.py", "metadata/SOURCE.json",
                         "project-template/.lexeditor-ds1-project", "ammunition_native.c",
                         "ammunition_bridge.S", "ammunition_payload.json")
            if not (PLUGIN_ROOT / name).is_file()]
    if not problems:
        from .formats import TABLES, schema
        try:
            for table in TABLES: schema(table)
        except (ValueError, OSError, KeyError) as error:
            problems.append(f"Invalid DS1 item metadata: {error}")
        try:
            ammunition_controls._payload()
        except (ValueError, OSError, KeyError, TypeError) as error:
            problems.append(f"Invalid DS1 ammunition payload: {error}")
    return problems


class DS1Session(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="plugins.ds1.server", plugin_id="ds1",
                         app_root=ROOT, check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"ds1": PLUGIN}, "ds1")


def ammunition_enabled(game_root: Path) -> bool:
    """The shared bundle mechanism reads actual persisted game state."""
    data = ammunition_tweak.read_executable(Path(game_root) / ammunition_controls.EXECUTABLE)
    return ammunition_controls.identify(data) == "enabled"


PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                    session_factory=DS1Session, installation=install_spec(__file__),
                    bundled_tweaks={ammunition_controls.TWEAK_ID: BundledTweak(
                        name=ammunition_controls.LABEL, read=ammunition_enabled,
                        write=ammunition_tweak.deploy)},
                    projects=project_spec(__file__, default_root=Path.home() / 'Lexeditor Mods' / 'Dark Souls Remastered'))
