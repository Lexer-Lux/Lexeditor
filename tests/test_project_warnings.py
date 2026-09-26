"""G6: warning causes stay specific; a never-created project is not damage.

A fresh game whose default project folder was never created used to yellow
with "<root> is missing <marker>" - the same damage-shaped message as a
broken project. The absent root now gets its own guidance, an incomplete
root keeps the per-file lines, and a plugin with failing support checks
shows the actual first problem instead of a generic sentence.
"""
from pathlib import Path

from plugin_api import GamePlugin, ModProjectSpec
from project_manager import ProjectManager


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


def test_absent_default_project_is_vanilla_not_damage(tmp_path):
    # Issue 567: no mod yet opens the game on vanilla, locked, instead of a
    # warning. It must not read as a damaged project either.
    missing = tmp_path / "mods" / "probe" / "My Mod"
    manager = ProjectManager({"probe-game": _plugin(missing)}, tmp_path / "projects.json")
    snapshot = manager.snapshot("probe-game")
    assert snapshot["vanilla"] is True
    assert not any(row["current"] for row in snapshot["projects"]), snapshot["projects"]
    assert not any("marker.json" in problem for row in snapshot["projects"]
                   for problem in row["problems"]), snapshot["projects"]


def test_incomplete_project_keeps_per_file_lines(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    manager = ProjectManager({"probe-game": _plugin(root)}, tmp_path / "projects.json")
    rows = manager.snapshot("probe-game")["projects"]
    current = next(row for row in rows if row["current"])
    assert not current["valid"]
    assert current["problems"] == [f"{root} is missing marker.json"], current["problems"]


def test_support_check_failure_names_its_problem(tmp_path):
    from game_installation import GameInstallationManager

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
