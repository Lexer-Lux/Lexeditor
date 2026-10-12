"""A mod switch the game's loader refuses leaves the mod as it was.

The switch used to save first and activate second. When activation failed
(DS1's Backstab Attempts refuses to build until its trigger is verified),
the box flipped back but mod.json kept the new state: the unbuildable mod
stayed on unseen and every later switch of any mod failed on it.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.desktop_host import HostApi


def library(tmp_path: Path) -> Path:
    root = tmp_path / "library"
    for name in ("Broken", "Fine"):
        (root / name).mkdir(parents=True)
        (root / name / "mod.json").write_text(json.dumps({"name": name, "enabled": False}), "utf-8")
    return root


def host(root: Path, refuse: bool):
    def activate(_plugin, paths):
        if refuse and any(Path(path).name == "Broken" for path in paths):
            raise ValueError("Broken: refuses to build")
    return SimpleNamespace(_game_mods=lambda _plugin: root, _mod_adapter=lambda _plugin: object(),
                           mod_library_status=lambda _plugin: {"canManage": True},
                           _activate_mods=activate)


def enabled(root: Path, name: str) -> bool:
    return json.loads((root / name / "mod.json").read_text("utf-8"))["enabled"]


def test_a_refused_switch_on_leaves_the_mod_off_and_others_still_switch(tmp_path):
    root = library(tmp_path)
    fake = host(root, refuse=True)
    with pytest.raises(ValueError, match="refuses"):
        HostApi.set_mod_enabled(fake, "game", str(root / "Broken"), True)
    assert enabled(root, "Broken") is False
    assert HostApi.set_mod_enabled(fake, "game", str(root / "Fine"), True)["enabled"] is True
    assert enabled(root, "Fine") is True


def test_an_accepted_switch_is_saved(tmp_path):
    root = library(tmp_path)
    assert HostApi.set_mod_enabled(host(root, refuse=False), "game", str(root / "Broken"), True)["enabled"] is True
    assert enabled(root, "Broken") is True
