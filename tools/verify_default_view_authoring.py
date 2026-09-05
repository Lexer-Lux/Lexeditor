"""Verify owner-only authoring of packaged per-tab view defaults."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import desktop_host
from desktop_host import HostApi
from games.ff8.plugin import PLUGIN


class Settings:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def snapshot(self) -> dict:
        return {"developerMode": self.enabled, "lexerMode": self.enabled}


class GitHub:
    def __init__(self, authorized: bool = True):
        self.authorized = authorized

    def visible_repository(self, repository, refresh=False):
        if not self.authorized:
            return None
        assert repository.full_name == "Lexer-Lux/Lexeditor"
        return {"repository": repository.full_name, "login": "Lexer-Lux"}


class Passive:
    pass


def api(settings: Settings, github: GitHub) -> HostApi:
    return HostApi(
        {"ff8": PLUGIN},
        installation_manager=Passive(),
        enforce_installations=False,
        auto_scan=False,
        github=github,
        cover_art=Passive(),
        settings=settings,
        projects=Passive(),
    )


with tempfile.TemporaryDirectory(prefix="lexeditor-default-view-", ignore_cleanup_errors=True) as temp_name:
    previous = desktop_host.DEFAULT_VIEWS
    desktop_host.DEFAULT_VIEWS = Path(temp_name) / "default_views.json"
    try:
        key = "lexeditor-columns:ff8-items"
        result = api(Settings(), GitHub()).save_default_view(
            "ff8", "items", {key: '["name","buyPrice"]', "unrelated": "ignored"},
        )
        assert result["saved"] and result["preferences"] == 1
        stored = json.loads(desktop_host.DEFAULT_VIEWS.read_text(encoding="utf-8"))
        assert stored == {"ff8": {"items": {key: '["name","buyPrice"]'}}}
        assert api(Settings(), GitHub()).default_views("ff8")["views"] == stored["ff8"]

        for blocked in (api(Settings(False), GitHub()), api(Settings(), GitHub(False))):
            try:
                blocked.save_default_view("ff8", "items", {key: "[]"})
            except PermissionError:
                pass
            else:
                raise AssertionError("Default authoring bypassed its owner/Lexer Mode gate")
    finally:
        desktop_host.DEFAULT_VIEWS = previous

print("Packaged view defaults require Lexer Mode and the authorized Lexeditor owner")
