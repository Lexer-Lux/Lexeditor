"""Static and filesystem contracts for Lexeditor issue 27."""

from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin_api import GamePlugin, ModProjectSpec  # noqa: E402
from project_manager import ProjectManager  # noqa: E402


framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
editors = {name: (ROOT / "games" / name / "editor.html").read_text(encoding="utf-8")
           for name in ("blank", "ff7", "ff8", "ff9", "rdr", "rdr2", "warband")}
ff7_2013_plugin = (ROOT / "games" / "ff7_2013" / "plugin.py").read_text(encoding="utf-8")
rdr_server = (ROOT / "games" / "rdr" / "server.py").read_text(encoding="utf-8")

for required in ("mapIcon()", 'id: "plugin-info"', "mountProjectControl", "browse_mod_project", "create_mod_project", "rename_mod_project",
                 'class: "lex-project-menu-actions"', '"New Mod"', '"Find a Mod"',
                 'class: "lex-shell-left-actions"', 'class: "lex-shell-center-actions"',
                 'class: "lex-shell-right-actions"', 'class: "lex-brand-slot"'):
    assert required in framework, required
assert ".lex-project-control" in css and ".lex-project-path" in css
assert 'id: "global-game-process"' in framework and 'callWindow("game_process_status"' in framework
assert 'document.createElementNS(namespace, running ? "rect" : "path")' in framework
assert 'class: "lex-shell-left-actions"}, context)' in framework
assert 'class: "lex-shell-center-actions"}, undo, save, game, redo)' in framework
assert "fitProjectRegion" in framework and "centre - left - 7" in framework
assert 'class: "lex-project-source-mode"' in framework
assert 'class:`lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`' in framework
assert '}, mode, name, path, status);' in framework
assert 'status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`' in framework
assert '`${selectedSource.readOnly === false ? "📝"' not in framework
assert 'class: "lex-save-count"' in framework and ".lex-save-count" in css
assert ":root { --lex-command-row-height: 9vh; }" in css
assert "height: var(--lex-command-row-height)" in css
assert ".lex-brand-button h1" in css and "margin: 0" in css
assert 'content: "⌄"' not in css
assert ".lex-project-select::after" in css and "border-right:" in css and "rotate(45deg)" in css
assert re.search(r"\.lex-project-menu\s*\{[^}]*width:\s*100%", css, re.DOTALL)
assert 'id:"plugin-status"' not in editors["ff8"]
assert ".lex-project-action" not in framework
assert "grid-template-columns: 12.5%" not in css
assert re.search(r"\.lex-shell-command-row\s*\{[^}]*grid-template-columns:\s*clamp\(", css, re.DOTALL)
assert "left: 50%" in css
assert '["dashboard","Setup"]' not in editors["ff8"]
assert '["dashboard","Settings"]' not in editors["warband"]
assert 'id:"project",label:"Project"' not in editors["rdr"]
for name, editor in editors.items():
    for adapter in ("projectSources:", "projectActiveSource:", "selectProjectSource:"):
        assert adapter in editor, (name, adapter)
    assert not re.search(
        r"\.lex-shell-command-row\s*\{[^}]*\b(?:min-)?height\s*:", editor,
        flags=re.IGNORECASE | re.DOTALL), name
for name in ("ff7", "ff8", "ff9", "rdr", "rdr2", "warband"):
    editor = editors[name]
    assert "info:" in editor and 'help:()=>navigate("datamap")' in editor, name
assert "menu.replaceChildren(...sourceRows, ...projects," in framework
assert 'SHARED_PLUGIN_ROOT / "editor.html"' in ff7_2013_plugin
for route in ("items_payload", "shops_payload", "missions_payload"):
    assert f'{route}(query.get("dataset", ["current"])[0] == "vanilla")' in rdr_server, route

with tempfile.TemporaryDirectory(prefix="lexeditor-projects-", ignore_cleanup_errors=True) as temp_name:
    temp = Path(temp_name)
    template = temp / "template"
    (template / "data").mkdir(parents=True)
    (template / "data" / "required.txt").write_text("seed", encoding="utf-8")
    def initialize_project(target: Path) -> None:
        (target / "initialized.txt").write_text("new project only", encoding="utf-8")
    plugin = GamePlugin("test", "Test", "TEST", "Test plugin", "#fff",
                        lambda: [], lambda: None,
                        projects=ModProjectSpec("TEST_PROJECT", template,
                                                ("data/required.txt",), template,
                                                initialize_project))
    manager = ProjectManager({"test": plugin}, temp / "projects.json")
    assert manager.snapshot("test")["current"] == str(template.resolve())
    created = manager.create("test", str(temp), "New Mod")
    target = temp / "New Mod"
    assert created["current"] == str(target.resolve())
    assert (target / "data" / "required.txt").read_text(encoding="utf-8") == "seed"
    assert (target / "initialized.txt").read_text(encoding="utf-8") == "new project only"
    reread = ProjectManager({"test": plugin}, temp / "projects.json").snapshot("test")
    assert reread["current"] == str(target.resolve())
    renamed = manager.rename("test", str(target), "Renamed Mod")
    renamed_target = temp / "Renamed Mod"
    assert renamed["current"] == str(renamed_target.resolve())
    assert not target.exists()
    assert (renamed_target / "data" / "required.txt").read_text(encoding="utf-8") == "seed"

print("Shared Map, Info, and mod-project contracts passed")
