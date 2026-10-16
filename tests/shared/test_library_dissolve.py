"""The Mod Library dialog is dissolved: drop import lives in the Mods tab,
bundle components are ordinary settings, and nothing applies on the side.

These are static contracts (no browser): the dialog, its Apply button and
its backend are gone, while the drop filter, the upload path and the
library-location setting stay.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK = (ROOT / "ui/framework.js").read_text(encoding="utf-8")
HOST = (ROOT / "core/desktop_host.py").read_text(encoding="utf-8")


def test_the_dialog_apply_and_bundle_wiring_are_gone_from_the_ui():
    for gone in ("openModLibrary", "libraryDialog", "mod_library_entries",
                 "activate_library_mods", "recover_bundled_mods",
                 "set_bundled_tweak", "data-bundle-component",
                 "data-bundle-tweak", "linkedTweaks", "Apply enabled mods",
                 '"Mod library…"'):
        assert gone not in FRAMEWORK, gone


def test_drop_import_still_filters_and_lands_in_the_mods_tab():
    assert FRAMEWORK.count("globalDropFiles") >= 3
    assert "importModDrop" in FRAMEWORK
    assert "mods.importDrop(transfer)" in FRAMEWORK
    assert "const importDrop = async transfer => {" in FRAMEWORK
    assert "importDrop: transfer => importDrop(transfer)" in FRAMEWORK
    # The moved preview keeps its folder/file choice and verdict line.
    assert "Package data folder" in FRAMEWORK
    assert "PAK package(s) checked" in FRAMEWORK
    assert "begin_mod_upload" in FRAMEWORK
    assert "upload_mod_chunk" in FRAMEWORK
    assert "end_mod_upload" in FRAMEWORK


def test_library_location_and_editable_copies_survive_the_dissolve():
    assert '"Mod library location"' in FRAMEWORK
    assert "Make an editable copy of" in FRAMEWORK
    assert "copy_library_mod" in FRAMEWORK


def test_the_dialog_backend_is_gone_but_upload_stays():
    for gone in ("def mod_library_entries", "def activate_library_mods",
                 "def set_bundled_tweak", "def recover_bundled_mods",
                 "def _bundle_manager", "BundleManager", "BundledTweak",
                 "bundled_tweaks", "linkedTweaks"):
        assert gone not in HOST, gone
    assert "def _activate_mods" in HOST
    for kept in ("def begin_mod_upload", "def upload_mod_chunk",
                 "def end_mod_upload", "def inspect_mod_package",
                 "def import_mod_package", "def choose_mod_package",
                 "def copy_library_mod"):
        assert kept in HOST, kept


def test_plugins_no_longer_declare_bundle_tweak_callbacks():
    api = (ROOT / "core/plugin_api.py").read_text(encoding="utf-8")
    assert "bundled_tweaks" not in api


def test_plain_mods_carry_no_component_settings(tmp_path):
    from core import mods_service
    folder = tmp_path / "Plain"
    folder.mkdir()
    (folder / "mod.json").write_text(json.dumps({"name": "Plain"}))
    assert mods_service.mod_row(folder)["components"] is None


def test_the_selector_lists_mods_without_link_annotations(tmp_path):
    from core.desktop_host import HostApi
    from core.project_manager import ProjectManager
    from plugins.ds1.plugin import PLUGIN
    from plugins.ds1.store import MARKER
    library = tmp_path / "library"
    opened = library / "soul safety"
    opened.mkdir(parents=True)
    (opened / MARKER).write_text("project", encoding="utf-8")
    (opened / "mod.json").write_text(json.dumps({"name": "Soul Safety", "enabled": False}))
    projects = ProjectManager({PLUGIN.plugin_id: PLUGIN}, tmp_path / "projects.json")
    projects.select(PLUGIN.plugin_id, str(opened))
    host = HostApi.__new__(HostApi)
    host._projects = projects
    host._game_mods = lambda plugin_id: library
    host._managed_project_locked = lambda plugin_id, path: False
    host._plugins = {PLUGIN.plugin_id: PLUGIN}
    host._mod_adapter = lambda plugin_id: None
    rows = host.mod_projects(PLUGIN.plugin_id)["projects"]
    assert rows and all("linkedTweaks" not in row for row in rows)
    assert "Soul Safety" in [row["name"] for row in rows if not row.get("noMod")]


def test_the_bundle_doc_describes_settings_not_a_dialog():
    doc = (ROOT / "docs/BUNDLED_MODS.md").read_text(encoding="utf-8")
    for gone in ("BundledTweak", "bundled_tweaks", "set_bundled_tweak",
                 ".bundles.json", ".bundles-pending.json", "linked tweak",
                 "Apply enabled mods", "Recover linked mods",
                 "verify_bundled_mods_ui.py", "Mod Library dialog"):
        assert gone not in doc, gone
    for kept in ("settings.json", "save_mod_settings",
                 "supports_bundle_components",
                 "tests/shared/test_bundled_mods.py",
                 "tests/shared/test_library_dissolve.py",
                 "tests/shared/test_mods_tab.py"):
        assert kept in doc, kept
    assert not (ROOT / "tests/shared/verify_bundled_mods_ui.py").exists()
