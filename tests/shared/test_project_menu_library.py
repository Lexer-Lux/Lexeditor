"""The mod selector lists the same mods as the Mods tab.

It used to list only mods opened before, so the selector and the Mods tab
showed different mods. Now every mod in the game's library is listed, in
the Mods tab's order, with its real on/off state; a tweak mod, which has no
game data to edit, is listed as one the editor cannot open.
"""
import json
from pathlib import Path

from core.desktop_host import HostApi
from core.project_manager import ProjectManager
from plugins.ds1.plugin import PLUGIN
from plugins.ds1.store import MARKER


def mod(library, folder, order, enabled, data=True, script=False):
    root = library / folder
    root.mkdir(parents=True)
    if data:
        (root / MARKER).write_text("project", encoding="utf-8")
    info = {"name": folder.title(), "order": order, "enabled": enabled}
    if script:
        info["script"] = {"version": 1}
    (root / "mod.json").write_text(json.dumps(info), encoding="utf-8")
    return root


def test_the_selector_lists_every_library_mod_in_the_mods_tab_order(tmp_path):
    library = tmp_path / "library"
    opened = mod(library, "soul safety", 30, False)
    mod(library, "better details", 10, True, data=False, script=True)
    mod(library, "sell at cost", 20, True)
    projects = ProjectManager({PLUGIN.plugin_id: PLUGIN}, tmp_path / "projects.json")
    projects.select(PLUGIN.plugin_id, str(opened))
    host = HostApi.__new__(HostApi)
    host._projects = projects
    host._game_mods = lambda plugin_id: library
    host._managed_project_locked = lambda plugin_id, path: False
    host._plugins = {PLUGIN.plugin_id: PLUGIN}
    # What the selector shows: openable mods and ones it cannot open.
    rows = [row for row in host.mod_projects(PLUGIN.plugin_id)["projects"]
            if not row.get("noMod") and (row["valid"] or row.get("notEditable"))]
    named = [(row["name"], row["enabled"], bool(row.get("notEditable")), row["current"]) for row in rows]
    assert named[:3] == [("Better Details", True, True, False), ("Sell At Cost", True, False, False),
                         ("Soul Safety", False, False, True)], named
    assert "Tweaks tab" in rows[0]["notEditable"]
