"""Lexer-only plugin that renders the unthemed shared UI defaults."""

from __future__ import annotations

from pathlib import Path

from core.plugin_api import GamePlugin
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return []


class BlankSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="plugins.blank.server", plugin_id="blank", app_root=ROOT,
                         check=check, extra_env=extra_env)


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"blank": PLUGIN}, "blank")


PLUGIN = GamePlugin(
    **plugin_defaults(__file__),
    check=check,
    launch=launch,
    session_factory=BlankSession,
    cover_art=ROOT / 'ui' / 'assets' / 'blank-game-cover.png',
)
