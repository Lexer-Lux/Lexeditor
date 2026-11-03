"""King's Field II / Verdite2 native-mod and player-settings integration."""
from pathlib import Path

from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults
from core.service_session import LocalPluginSession
from .mod_support import VerditeModAdapter

ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return []


class KingsField2Session(LocalPluginSession):
    def __init__(self, extra_env=None):
        super().__init__(module="plugins.kings_field2.server", plugin_id="kings-field2",
                         app_root=ROOT, check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"kings-field2": PLUGIN}, "kings-field2")


PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                    installation=install_spec(__file__), session_factory=KingsField2Session,
                    mod_adapter=VerditeModAdapter())
