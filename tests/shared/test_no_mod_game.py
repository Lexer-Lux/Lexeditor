"""A game with no mod yet is not a broken game.

Home used to flag every game whose project folder had not been created yet
with a warning and refuse to open it. It is the ordinary state of a game
nobody has modded: the editor can show the game's own data, so the card stays
ready, and the session opens locked so nothing can be written. Only a project
that exists and is damaged still warns.
"""
import json
from dataclasses import replace
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.desktop_host import HostApi
from core.project_manager import ProjectManager
from plugins.palworld.plugin import PLUGIN


def host_with_project(row):
    host = HostApi.__new__(HostApi)
    host._installations = Mock()
    host._installations.rows.return_value = [{
        "plugin": PLUGIN,
        "installation": {"status": "added", "problems": [], "canOpen": True,
                         "statusText": "", "root": "C:/Games/Palworld"},
    }]
    host._installations.environment.return_value = {}
    host._enforce_installations = True
    host._projects = Mock()
    host._projects.snapshot.return_value = {
        "pluginId": PLUGIN.plugin_id, "current": row["path"], "projects": [row]}
    host._github = Mock()
    host._plugin_id = None
    host._font_errors = {}
    host._cover_art = Mock()
    return host


NO_MOD_ROW = {"path": "C:/Mods/PalworldProject", "name": "PalworldProject",
              "version": "", "valid": False, "noMod": True, "current": True,
              "problems": ["No Palworld project yet at C:/Mods/PalworldProject. "
                           "Create one to save changes."]}
DAMAGED_ROW = {"path": "C:/Mods/Broken", "name": "Broken", "version": "",
               "valid": False, "noMod": False, "current": True,
               "problems": ["C:/Mods/Broken is missing Info.json"]}
MISSING_ROW = {"path": "C:/Mods/Gone", "name": "Gone", "version": "",
               "valid": False, "noMod": False, "current": True,
               "problems": ["Project folder not found: C:/Mods/Gone. "
                            "Reselect or recreate it."]}


class NoModGameTests(unittest.TestCase):
    def row(self, row):
        host = host_with_project(row)
        with patch("core.desktop_host.game_version", return_value=""), \
                patch("core.desktop_host.font_status", return_value={}):
            return host.plugins()[0]

    def test_no_mod_yet_stays_ready(self):
        row = self.row(NO_MOD_ROW)
        self.assertTrue(row["noMod"])
        self.assertEqual(row["status"], "added")
        self.assertTrue(row["canOpen"])
        self.assertTrue(row["ready"], row)
        self.assertFalse(row["problem"])

    def test_damaged_project_still_warns(self):
        row = self.row(DAMAGED_ROW)
        self.assertFalse(row["noMod"])
        self.assertEqual(row["status"], "warning")
        self.assertFalse(row["canOpen"])
        self.assertIn("missing Info.json", row["statusText"])

    def test_missing_selected_folder_still_warns(self):
        row = self.row(MISSING_ROW)
        self.assertFalse(row["noMod"])
        self.assertEqual(row["status"], "warning")
        self.assertFalse(row["canOpen"])
        self.assertIn("Reselect or recreate it", row["statusText"])

    def test_open_marks_a_no_mod_session_read_only(self):
        host = host_with_project(NO_MOD_ROW)
        host._lock = __import__("threading").RLock()
        host._plugins = {PLUGIN.plugin_id: PLUGIN}
        host._session = None
        host._session_project_path = None
        host._dirty_count = 0
        host._font_errors = {}
        host._session_no_mod = False
        host.update_managed_mod = Mock()
        host.download_fonts = Mock(return_value={})
        session = Mock()
        session.start.return_value = {"ok": True}
        session.url = "http://127.0.0.1:9/"
        captured = {}

        def factory(environment=None):
            captured.update(environment or {})
            return session

        plugin = type(PLUGIN)(**{**PLUGIN.__dict__, "session_factory": factory,
                                 "check": staticmethod(lambda: [])})
        host._plugins = {PLUGIN.plugin_id: plugin}
        with patch("core.desktop_host.game_version", return_value=""):
            opened = host.open_plugin(PLUGIN.plugin_id)
        self.assertEqual(captured.get("LEXEDITOR_MOD_READ_ONLY"), "1", captured)
        self.assertEqual(captured.get("LEXEDITOR_NO_MOD"), "1", captured)
        self.assertIn("lexNoMod=1", opened["url"], opened)


class ProjectlessPluginTests(unittest.TestCase):
    """A plugin with no project store opens without a read-only answer.

    The no-mod flag is read for every plugin when a session opens, but it was
    only assigned inside the projects branch, so Blank - which has no project
    store at all - failed to open with an UnboundLocalError.
    """

    def test_a_plugin_with_no_projects_still_opens(self):
        from plugins.blank.plugin import PLUGIN as BLANK

        host = HostApi.__new__(HostApi)
        host._lock = threading.RLock()
        host._installations = Mock()
        host._installations.rows.return_value = []
        host._enforce_installations = False
        host._projects = Mock()
        host._github = Mock()
        host._cover_art = Mock()
        host._session = None
        host._session_project_path = None
        host._dirty_count = 0
        host._font_errors = {}
        host._session_no_mod = False
        host.update_managed_mod = Mock()
        host.download_fonts = Mock(return_value={})
        session = Mock()
        session.start.return_value = {"ok": True}
        session.url = "http://127.0.0.1:9/"
        plugin = type(BLANK)(**{**BLANK.__dict__,
                                "session_factory": lambda environment=None: session,
                                "check": staticmethod(lambda: [])})
        host._plugins = {plugin.plugin_id: plugin}
        with patch("core.desktop_host.game_version", return_value=""):
            opened = host.open_plugin(plugin.plugin_id)
        self.assertEqual(opened["id"], "blank")
        self.assertNotIn("lexNoMod", opened["url"])
        self.assertFalse(host._session_no_mod)


class NoModProjectTests(unittest.TestCase):
    def test_removing_current_mod_returns_to_vanilla_without_a_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            default=root/'DefaultMod'
            default.mkdir()
            (default/'data.txt').write_text('Keep this mod',encoding='utf-8')
            other=root/'OtherMod'
            other.mkdir()
            (other/'data.txt').write_text('Keep this too',encoding='utf-8')
            plugin=replace(PLUGIN,projects=replace(PLUGIN.projects,default_root=default,
                required_paths=('data.txt',),required_any=(),discover=lambda:[default,other]))
            manager=ProjectManager({plugin.plugin_id:plugin},root/'projects.json')
            for selected in [default,other]:
                manager.select(plugin.plugin_id,str(selected))
                result=manager.forget(plugin.plugin_id,str(selected))
                current=next(row for row in result['projects'] if row['current'])
                self.assertEqual(current['name'],'Vanilla')
                self.assertTrue(current['noMod'])
                self.assertTrue(current['readOnly'])
                self.assertFalse(Path(result['current']).exists())
                self.assertNotIn(str(selected.resolve()),[row['path'] for row in result['projects']])
                restored=ProjectManager({plugin.plugin_id:plugin},manager.path).snapshot(plugin.plugin_id)
                self.assertEqual(restored,result)
            self.assertEqual((default/'data.txt').read_text(),'Keep this mod')
            self.assertEqual((other/'data.txt').read_text(),'Keep this too')
            self.assertFalse((root/'vanilla-view').exists())
            selected=manager.select(plugin.plugin_id,str(default))
            self.assertFalse(next(row for row in selected['projects'] if row['current'])['noMod'])

    def test_project_store_reports_no_mod_apart_from_damage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manager = ProjectManager({PLUGIN.plugin_id: PLUGIN}, root / "projects.json")
            fresh = manager.snapshot(PLUGIN.plugin_id)["projects"][0]
            self.assertTrue(fresh["noMod"], fresh)
            self.assertFalse(fresh["valid"])
            self.assertIn("Create one to save changes", fresh["problems"][0])
            # A folder the reader picked that has since gone is damage, not
            # a game that was never modded.
            manager.path.write_text(json.dumps({PLUGIN.plugin_id: {
                "current": str(root / "gone")}}), encoding="utf-8")
            gone = manager.snapshot(PLUGIN.plugin_id)["projects"][0]
            self.assertFalse(gone["noMod"], gone)
            self.assertIn("Reselect or recreate it", gone["problems"][0])


if __name__ == "__main__":
    unittest.main()
