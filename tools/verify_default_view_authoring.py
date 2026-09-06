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
    def snapshot(self) -> dict:
        # Developer Mode is intentionally not persisted here. It is derived
        # from the active authenticated GitHub account by HostApi.
        return {}


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


def api(github: GitHub) -> HostApi:
    return HostApi(
        {"ff8": PLUGIN},
        installation_manager=Passive(),
        enforce_installations=False,
        auto_scan=False,
        github=github,
        cover_art=Passive(),
        settings=Settings(),
        projects=Passive(),
    )


with tempfile.TemporaryDirectory(prefix="lexeditor-default-view-", ignore_cleanup_errors=True) as temp_name:
    previous = desktop_host.DEFAULT_VIEWS
    desktop_host.DEFAULT_VIEWS = Path(temp_name) / "default_views.json"
    try:
        key = "lexeditor-columns:ff8-items"
        result = api(GitHub()).save_default_view(
            "ff8", "items", {key: '["name","buyPrice"]', "unrelated": "ignored"},
        )
        assert result["saved"] and result["preferences"] == 1
        stored = json.loads(desktop_host.DEFAULT_VIEWS.read_text(encoding="utf-8"))
        assert stored == {"ff8": {"items": {key: '["name","buyPrice"]'}}}
        assert api(GitHub()).default_views("ff8")["views"] == stored["ff8"]

        blocked = api(GitHub(False))
        try:
            blocked.save_default_view("ff8", "items", {key: "[]"})
        except PermissionError:
            pass
        else:
            raise AssertionError("Default authoring bypassed its Developer Mode owner gate")
    finally:
        desktop_host.DEFAULT_VIEWS = previous

print("Packaged view defaults require the authorized Lexeditor developer")
