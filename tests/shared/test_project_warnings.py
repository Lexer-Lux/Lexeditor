"""G6: warning causes stay specific; a never-created project is not damage.

A fresh game whose default project folder was never created used to yellow
with "<root> is missing <marker>" - the same damage-shaped message as a
broken project. The absent root now gets its own guidance, an incomplete
root keeps the per-file lines, and a plugin with failing support checks
shows the actual first problem instead of a generic sentence.
"""
from pathlib import Path

from core.plugin_api import GamePlugin, ModProjectSpec
from core.project_manager import ProjectManager


def _plugin(default_root: Path) -> GamePlugin:
    return GamePlugin(
        plugin_id="probe-game",
        name="Probe Game",
        accent="#000000",
        check=lambda: [],
        launch=lambda: 0,
        projects=ModProjectSpec(
            root_env="LEXEDITOR_PROBE_PROJECT",
            default_root=default_root,
            required_paths=("marker.json",),
            template_root=default_root,
        ),
    )


def test_absent_default_project_gets_creation_guidance(tmp_path):
    missing = tmp_path / "mods" / "probe" / "My Mod"
    manager = ProjectManager({"probe-game": _plugin(missing)})
    rows = manager.snapshot("probe-game")["projects"]
    current = next(row for row in rows if row["current"])
    assert not current["valid"]
    assert len(current["problems"]) == 1, current["problems"]
    assert "marker.json" not in current["problems"][0], current["problems"]
    assert "No Probe Game project yet" in current["problems"][0], current["problems"]
    assert str(missing) in current["problems"][0], current["problems"]


def test_incomplete_project_keeps_per_file_lines(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    manager = ProjectManager({"probe-game": _plugin(root)})
    rows = manager.snapshot("probe-game")["projects"]
    current = next(row for row in rows if row["current"])
    assert not current["valid"]
    assert current["problems"] == [f"{root} is missing marker.json"], current["problems"]


def test_support_check_failure_names_its_problem(tmp_path):
    from core.game_installation import GameInstallationManager

    plugin = GamePlugin(
        plugin_id="probe-broken",
        name="Probe Broken",
        accent="#000000",
        check=lambda: ["Probe Broken plugin file is missing: editor.js"],
        launch=lambda: 0,
    )
    manager = GameInstallationManager(
        {"probe-broken": plugin},
        config_path=tmp_path / "installations.json",
        auto_scan=False,
    )
    state = manager.snapshot("probe-broken")
    assert state["status"] == "warning"
    assert state["problems"] == ["Probe Broken plugin file is missing: editor.js"]
    assert state["statusText"] == "Probe Broken plugin file is missing: editor.js"
