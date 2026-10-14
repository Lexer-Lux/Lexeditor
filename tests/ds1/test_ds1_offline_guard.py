"""DS1 goes offline whenever a mod changes the game's code.

The loader blocks the network for any installed patch and in debug mode
(test_ds1_runtime_loader.py proves that natively). Here: Play's toast says
so from what is installed, and the Mods tab marks every mod that would do
it, while data and asset mods stay online.
"""
from __future__ import annotations

import json
from pathlib import Path

from plugins.ds1 import tweak_mods
from plugins.ds1.mod_support import Ds1ModAdapter
from plugins.ds1.store import MARKER


def test_play_says_why_the_game_is_offline(tmp_path):
    assert tweak_mods.offline_reason(tmp_path) == ""
    tweak_mods._write_runtime(tmp_path, b"LXD1PAT\0patch", ["Sprint"], None)
    assert tweak_mods.offline_reason(tmp_path) == tweak_mods.OFFLINE_MODS
    # A menu-layout-only tweak installs an empty patch: the game stays online.
    tweak_mods._write_runtime(tmp_path, b"", [], None)
    assert tweak_mods.offline_reason(tmp_path) == ""
    tweak_mods._write_runtime(tmp_path, None, [], None, debug=True)
    assert tweak_mods.offline_reason(tmp_path) == tweak_mods.OFFLINE_DEBUG
    tweak_mods._write_runtime(tmp_path, None, [], None)
    assert tweak_mods.offline_reason(tmp_path) == ""


def tweak(folder: Path, built: dict[str, str]) -> Path:
    folder.mkdir()
    (folder / "mod.json").write_text(json.dumps({"name": folder.name, "script": {"version": 1}}), encoding="utf-8")
    for relative, text in built.items():
        (folder / relative).parent.mkdir(parents=True, exist_ok=True)
        (folder / relative).write_text(text, encoding="utf-8")
    return folder


def test_code_changing_tweaks_are_told_apart_from_layout_only_ones(tmp_path):
    assert tweak_mods.changes_code(tweak(tmp_path / "hooks", {"native/hooks.json": "{}"}))
    assert tweak_mods.changes_code(tweak(tmp_path / "binary", {"bin/helper.dll": "MZ"}))
    assert tweak_mods.changes_code(tweak(tmp_path / "unbuilt", {}))
    assert not tweak_mods.changes_code(tweak(tmp_path / "layout", {"layout/layout.json": "{}"}))


def test_the_mods_tab_marks_mods_that_take_the_game_offline(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    hooks = tweak(tmp_path / "hooks", {"native/hooks.json": "{}"})
    layout = tweak(tmp_path / "layout", {"layout/layout.json": "{}"})
    data = tmp_path / "data"
    data.mkdir()
    (data / MARKER).write_bytes(b"{}")
    adapter = Ds1ModAdapter()
    adapter.attach_context(library_root=tmp_path / "library", game_root=game)
    lines = adapter.alerts([hooks, layout, data], game)
    assert Ds1ModAdapter.ALERT_OFFLINE in lines.get(str(hooks.resolve()), [])
    assert Ds1ModAdapter.ALERT_OFFLINE not in lines.get(str(layout.resolve()), [])
    assert Ds1ModAdapter.ALERT_OFFLINE not in lines.get(str(data.resolve()), [])
