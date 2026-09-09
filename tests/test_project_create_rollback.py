from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from project_manager import ProjectManager


class ProjectCreateRollbackTests(unittest.TestCase):
    def manager(self, root: Path, initializer, *, required_paths=("SubModule.xml",)):
        template = root / "template"
        template.mkdir()
        (template / "SubModule.xml").write_text("<Module/>", encoding="utf-8")
        spec = SimpleNamespace(
            template_root=template,
            initialize=initializer,
            required_paths=required_paths,
            required_any=(),
            default_root=root / "default",
            root_env="TEST_PROJECT_ROOT",
            discover=None,
        )
        plugin = SimpleNamespace(name="Test Plugin", projects=spec)
        return ProjectManager({"test": plugin}, path=root / "projects.json")

    def test_initializer_failure_removes_only_new_target(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = root / "projects"
            parent.mkdir()
            sibling = parent / "keep"
            sibling.mkdir()
            marker = sibling / "marker.txt"
            marker.write_text("keep", encoding="utf-8")

            def fail(target: Path):
                (target / "partially-written.txt").write_text("partial", encoding="utf-8")
                raise ValueError("initializer failed")

            manager = self.manager(root, fail)
            with self.assertRaisesRegex(ValueError, "initializer failed"):
                manager.create("test", str(parent), "New Project")
            self.assertFalse((parent / "New Project").exists())
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            self.assertFalse((root / "projects.json").exists())

    def test_select_validation_failure_after_initializer_also_rolls_back(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = root / "projects"
            parent.mkdir()

            def invalidate(target: Path):
                (target / "SubModule.xml").unlink()

            manager = self.manager(root, invalidate)
            with self.assertRaisesRegex(ValueError, "missing SubModule.xml"):
                manager.create("test", str(parent), "Broken")
            self.assertFalse((parent / "Broken").exists())
            self.assertFalse((root / "projects.json").exists())

    def test_successful_creation_remains_selected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            parent = root / "projects"
            parent.mkdir()
            manager = self.manager(root, lambda _target: None)
            snapshot = manager.create("test", str(parent), "Good")
            target = (parent / "Good").resolve()
            self.assertTrue(target.is_dir())
            self.assertEqual(Path(snapshot["current"]).resolve(), target)
            self.assertTrue((root / "projects.json").is_file())


if __name__ == "__main__":
    unittest.main()
