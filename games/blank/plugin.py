"""Lexer-only plugin that renders the unthemed shared UI defaults."""

from __future__ import annotations

from pathlib import Path

from plugin_api import GamePlugin
from service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]


def check() -> list[str]:
    return []


class BlankSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(module="games.blank.server", plugin_id="blank", app_root=ROOT,
                         check=check, extra_env=extra_env)


def launch() -> int:
    from desktop_host import run_host
    return run_host({"blank": PLUGIN}, "blank")


PLUGIN = GamePlugin(
    plugin_id="blank",
    name="Blank Game",
    subtitle="Default UI",
    description="Unthemed shared controls for Lexer Mode UI inspection.",
    accent="#68717e",
    check=check,
    launch=launch,
    session_factory=BlankSession,
    cover_art=ROOT / "ui" / "assets" / "blank-game-cover.png",
)
