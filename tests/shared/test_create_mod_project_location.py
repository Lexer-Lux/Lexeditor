"""Shared Create Mod: default location is the mod library shown in
Settings, organized per plugin; an alternate location is a separate,
explicit action. No test here touches the reader's real library or
settings - everything runs under a temporary directory.
"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest

from core.desktop_host import HostApi
from core.project_manager import ProjectManager


class CreateModProjectLocationTests(unittest.TestCase):
    def host(self, root: Path, library_root: Path):
        template = root / "template"
        template.mkdir(parents=True, exist_ok=True)
        (template / "mod.marker").write_text("starter", encoding="utf-8")
        spec = SimpleNamespace(
            template_root=template, initialize=None,
            required_paths=("mod.marker",), required_any=(),
            default_root=root / "default", root_env="TEST_PROJECT_ROOT", discover=None,
        )
        plugin = SimpleNamespace(name="Test Plugin", projects=spec)
        host = HostApi.__new__(HostApi)
        host._plugins = {"test": plugin}
        host._projects = ProjectManager({"test": plugin}, path=root / "projects.json")
        host._restart_for_project = lambda plugin_id, project: {**project, "url": "http://fixture", "identity": "test"}
        host.mod_library_location = lambda: {"root": str(library_root), "move": None}
        return host

    def test_default_creation_lands_under_the_library_s_own_plugin_folder(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            # No ds1-style registry entry or library folder exists yet - the
            # default path has to make both.
            self.assertFalse(library_root.exists())
            host = self.host(root, library_root)
            result = host.create_mod_project("test", "My Mod")
            target = library_root / "test" / "My Mod"
            self.assertTrue(target.is_dir())
            self.assertTrue((target / "mod.marker").is_file())
            self.assertEqual(Path(result["current"]).resolve(), target.resolve())
            self.assertNotIn("cancelled", result)

    def test_an_explicit_alternate_location_is_used_instead(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            elsewhere = root / "elsewhere"
            elsewhere.mkdir()
            host = self.host(root, library_root)
            result = host.create_mod_project("test", "My Mod", str(elsewhere))
            target = elsewhere / "My Mod"
            self.assertTrue(target.is_dir())
            self.assertEqual(Path(result["current"]).resolve(), target.resolve())
            # The library's own folder was never touched by the alternate path.
            self.assertFalse(library_root.exists())

    def test_a_colliding_name_is_rejected_in_either_location(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            host = self.host(root, library_root)
            host.create_mod_project("test", "My Mod")
            with self.assertRaises(ValueError):
                host.create_mod_project("test", "My Mod")

    def test_choose_mod_project_location_anchors_on_the_library_s_plugin_folder(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            (library_root / "test").mkdir(parents=True)
            host = self.host(root, library_root)
            seen = []
            host._choose_folder = lambda directory="": (seen.append(directory), "")[1]
            result = host.choose_mod_project_location("test")
            self.assertEqual(seen, [str(library_root / "test")])
            self.assertEqual(result, {"parent": "", "cancelled": True})

    def test_choose_mod_project_location_anchors_on_the_library_root_when_the_plugin_folder_is_new(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            library_root.mkdir()
            host = self.host(root, library_root)
            seen = []
            host._choose_folder = lambda directory="": (seen.append(directory), str(root / "chosen"))[1]
            result = host.choose_mod_project_location("test")
            self.assertEqual(seen, [str(library_root)])
            self.assertEqual(result, {"parent": str(root / "chosen"), "cancelled": False})

    def test_an_unregistered_plugin_id_never_creates_a_library_folder(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            host = self.host(root, library_root)
            host._choose_folder = lambda directory="": self.fail("picker opened")
            for plugin_id in ("../escape", "missing", None):
                with self.assertRaises(ValueError):
                    host.create_mod_project(plugin_id, "My Mod")
                with self.assertRaises(ValueError):
                    host.choose_mod_project_location(plugin_id)
            self.assertFalse(library_root.exists())
            self.assertFalse((root / "escape").exists())

    def test_choosing_a_location_never_creates_or_writes_anything_itself(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            library_root = root / "library"
            host = self.host(root, library_root)
            host._choose_folder = lambda directory="": str(root / "picked")
            host.choose_mod_project_location("test")
            self.assertFalse(library_root.exists())
            self.assertFalse((root / "picked").exists())


if __name__ == "__main__":
    unittest.main()
