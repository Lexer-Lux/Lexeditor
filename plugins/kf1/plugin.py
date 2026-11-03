"""King's Field I's existing Verdite1 native port and shared shell."""
from pathlib import Path

from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults
from core.service_session import LocalPluginSession
from .mod_support import Kf1ModAdapter

ROOT = Path(__file__).resolve().parents[2]


def check():
    return []


def session(extra_env=None):
    return LocalPluginSession(module="plugins.kf1.server", plugin_id="kf1", app_root=ROOT, check=check, extra_env=extra_env)


def launch():
    from core.desktop_host import run_host
    return run_host({"kf1": PLUGIN}, "kf1")


PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                    session_factory=session, installation=install_spec(__file__), mod_adapter=Kf1ModAdapter())
