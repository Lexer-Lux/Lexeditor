"""Static and filesystem contracts for Lexeditor issue 27."""

from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.plugin_api import GamePlugin, ModProjectSpec  # noqa: E402
from core.project_manager import ProjectManager  # noqa: E402


framework = (ROOT / "ui" / "framework.js").read_text(encoding="utf-8")
css = (ROOT / "ui" / "framework.css").read_text(encoding="utf-8")
# A plugin's shared-shell options live in whichever file mounts the shell. It
# used to be editor.html for every plugin, so this read that one file and
# silently checked nothing once Blank, FF8, RDR2 and Warband moved their shell
# into editor.js or boot.js. Read the plugin's own page sources instead.
editors = {}
for _name in ("blank", "ff7", "ff8", "ff9", "rdr", "rdr2", "warband"):
    _folder = ROOT / "plugins" / _name
    _sources = [path for path in sorted(_folder.glob("*.js")) + sorted(_folder.glob("*.html"))
                if not path.name.endswith(".test.cjs")]
    editors[_name] = "\n".join(path.read_text(encoding="utf-8") for path in _sources)
ff7_2013_plugin = (ROOT / "plugins" / "ff7_2013" / "plugin.py").read_text(encoding="utf-8")
rdr_server = (ROOT / "plugins" / "rdr" / "server.py").read_text(encoding="utf-8")

for required in ("mapIcon()", 'id: "plugin-info"', "mountProjectControl", "browse_mod_project", "create_mod_project", "rename_mod_project",
                 'class: "lex-project-menu-actions"', '"➕ Add a Mod"', '"🔍 Find a Mod"',
                 'class: "lex-shell-left-actions"', 'class: "lex-shell-center-actions"',
                 'class: "lex-shell-right-actions"', 'class: "lex-brand-slot"'):
    assert required in framework, required
assert ".lex-project-control" in css and ".lex-project-path" in css
assert 'id: "global-game-process"' in framework and 'callWindow("game_process_status"' in framework
assert 'document.createElementNS(namespace, running ? "rect" : "path")' in framework
assert 'class: "lex-shell-left-actions"}, context)' in framework
# The row carries the NO MOD badge beside the save button when the host
# opened a game with no mod, so the reader can see why nothing can be saved.
assert 'class: "lex-shell-center-actions"},' in framework
assert "undo, save, game, noModNote, redo);" in framework
assert 'sessionHasNoMod()' in framework and '"NO MOD"' in framework
# The command row is three cells (start | centre | end); the grid bounds the
# project region, so no script measures and pins its width.
assert 'class: "lex-shell-start"}, brandSlot, leftActions)' in framework
assert "fitProjectRegion" not in framework
assert 'class: "lex-project-source-mode"' in framework
assert 'class:`lex-project-source-status ${row.enabled === false ? "disabled" : "enabled"}`' in framework
assert '}, mode, name, path, status);' in framework
assert 'status.className = `lex-project-source-status ${selectedSource?.enabled === false ? "disabled" : "enabled"}`' in framework
assert '`${selectedSource.readOnly === false ? "📝"' not in framework
assert 'class: "lex-save-count"' in framework and ".lex-save-count" in css
assert re.search(r"--lex-command-row-height:\s*9vh;", css)
assert "height: var(--lex-command-row-height)" in css
assert ".lex-brand-button h1" in css and "margin: 0" in css
assert 'content: "⌄"' not in css
assert ".lex-project-select::after" in css and "border-right:" in css and "rotate(45deg)" in css
assert re.search(r"\.lex-project-menu\s*\{[^}]*width:\s*100%", css, re.DOTALL)
assert 'id:"plugin-status"' not in editors["ff8"]
assert ".lex-project-action" not in framework
assert "grid-template-columns: 12.5%" not in css
assert re.search(r"\.lex-shell-command-row\s*\{[^}]*grid-template-columns:\s*minmax\(min-content, 1fr\) auto minmax\(max-content, 1fr\)", css, re.DOTALL)
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
# A game with no mod still lists the game's own read-only source above the
# actions that create or open a mod, so the list does not read as empty.
assert "menu.replaceChildren(...(vanillaMenuItem?[vanillaMenuItem]:[]), ...sourceRows, ...projects," in framework
assert "const vanillaMenuItem = noMod && !vanillaSource" in framework
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
    plugin = GamePlugin("test", "Test",   "#fff",
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
