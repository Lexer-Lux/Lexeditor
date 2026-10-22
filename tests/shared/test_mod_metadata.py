"""Every mod carries its name, author, description and credits in mod.json.

Only the name is required. A mod added to the library or created from a
game's starter is always stored with one, and a game's own keys in the same
file survive every write.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from core import mod_metadata
from core.mod_library import ModLibrary, metadata


class Adapter:
    """Accepts any file; enough for the library's import path."""

    def inspect(self, root, files):
        return {"valid": True, "problems": [], "packages": [p.as_posix() for p in files],
                "assets": {}, "notDeployed": []}

    def prepare_editable(self, root):
        pass


class MetadataTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_name_is_required_and_the_rest_may_be_blank(self):
        self.assertEqual(mod_metadata.clean({"name": " My Mod "}),
                         {"name": "My Mod", "author": "", "description": "", "credits": ""})
        for bad in ({}, {"name": "   "}, {"name": 5}, {"name": "x", "author": ["Lexer"]},
                    {"name": "x" * 121}, "not an object"):
            with self.assertRaises(mod_metadata.MetadataError, msg=bad):
                mod_metadata.clean(bad)

    def test_an_unnamed_mod_says_so_and_borrows_its_folder_name_for_display(self):
        mod = self.root / "Some Folder"
        mod.mkdir()
        details = mod_metadata.read(mod)
        self.assertEqual(details["missing"], ["name"])
        self.assertEqual(details["displayName"], "Some Folder")
        self.assertEqual(metadata(mod)["missing"], ["name"])
        self.assertFalse((mod / "mod.json").exists(), "reading never writes")

    def test_writing_keeps_a_games_own_keys(self):
        mod = self.root / "mod"
        mod.mkdir()
        (mod / "mod.json").write_text(json.dumps({"id": "x", "order": 3, "enabled": True,
                                                  "script": {"version": 1}}), encoding="utf-8")
        result = mod_metadata.write(mod, {"name": "Named", "author": "Lexer", "credits": "Thanks to everyone."})
        self.assertEqual(result["missing"], [])
        stored = json.loads((mod / "mod.json").read_text(encoding="utf-8"))
        self.assertEqual({k: stored[k] for k in ("id", "order", "enabled", "script")},
                         {"id": "x", "order": 3, "enabled": True, "script": {"version": 1}})
        self.assertEqual((stored["name"], stored["author"], stored["description"], stored["credits"]),
                         ("Named", "Lexer", "", "Thanks to everyone."))

    def test_an_added_mod_is_stored_with_its_details(self):
        package = self.root / "Downloaded Thing"
        (package / "data").mkdir(parents=True)
        (package / "data" / "file.bin").write_bytes(b"x")
        (package / "mod.json").write_text(json.dumps({"author": "Someone", "load": 7}), encoding="utf-8")
        library = ModLibrary(self.root / "library")
        target = library.import_mod("game", package, Adapter(), "Better Thing",
                                    details={"description": "Does a thing.", "credits": "Someone made it."})
        stored = json.loads((target / "mod.json").read_text(encoding="utf-8"))
        self.assertEqual((stored["name"], stored["author"], stored["description"], stored["credits"], stored["load"]),
                         ("Better Thing", "Someone", "Does a thing.", "Someone made it.", 7))

    def test_creating_a_mod_writes_its_details_before_it_opens(self):
        from core.desktop_host import HostApi
        from core.project_manager import ProjectManager
        template = self.root / "template"
        template.mkdir()
        (template / "mod.marker").write_text("starter", encoding="utf-8")
        spec = SimpleNamespace(template_root=template, initialize=None, required_paths=("mod.marker",),
                               required_any=(), default_root=self.root / "default", root_env="TEST_ROOT", discover=None)
        plugin = SimpleNamespace(name="Test", projects=spec)
        host = HostApi.__new__(HostApi)
        host._plugins = {"test": plugin}
        host._projects = ProjectManager({"test": plugin}, path=self.root / "projects.json")
        host._restart_for_project = lambda plugin_id, project: {**project}
        host.mod_library_location = lambda: {"root": str(self.root / "library"), "move": None}
        host.create_mod_project("test", "Fresh Mod", details={"author": "Lexer", "description": "New."})
        stored = json.loads((self.root / "library" / "test" / "Fresh Mod" / "mod.json").read_text(encoding="utf-8"))
        self.assertEqual((stored["name"], stored["author"], stored["description"]), ("Fresh Mod", "Lexer", "New."))
        with self.assertRaises(mod_metadata.MetadataError):
            host.create_mod_project("test", "Another", details={"author": ["not text"]})
        self.assertFalse((self.root / "library" / "test" / "Another").exists(), "nothing is created for bad details")


if __name__ == "__main__":
    unittest.main()
