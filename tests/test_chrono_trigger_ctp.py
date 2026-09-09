from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from games.chrono_trigger.ctp import export_ctp


class CtpExportTests(unittest.TestCase):
    def test_exports_only_project_resources_deterministically(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-ctp-") as temp_name:
            root = Path(temp_name)
            project = root / "Project"
            (project / "Game/field").mkdir(parents=True)
            (project / "Localize/en/msg").mkdir(parents=True)
            (project / "Game/field/test.dat").write_bytes(b"field")
            (project / "Localize/en/msg/item.txt").write_text("0000,Tonic\n", encoding="utf-8")
            (project / "lexeditor-project.json").write_text("{}", encoding="utf-8")
            (project / ".lexeditor-deployment.json").write_text("{}", encoding="utf-8")
            first = root / "first.ctp"
            second = root / "second.ctp"

            result = export_ctp(project, first)
            result2 = export_ctp(project, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(result["sha256"], result2["sha256"])
            self.assertEqual(result["fileCount"], 2)
            with zipfile.ZipFile(first, "r") as archive:
                self.assertEqual(archive.namelist(), [
                    "Game/field/test.dat", "Localize/en/msg/item.txt",
                ])
                self.assertEqual(archive.read("Game/field/test.dat"), b"field")
                self.assertNotIn("lexeditor-project.json", archive.namelist())
                self.assertNotIn(".lexeditor-deployment.json", archive.namelist())

    def test_refuses_target_inside_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-ctp-") as temp_name:
            project = Path(temp_name) / "Project"
            project.mkdir()
            (project / "Game.dat").write_bytes(b"x")
            with self.assertRaises(ValueError):
                export_ctp(project, project / "Project.ctp")

    def test_refuses_symlink_content_when_supported(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-ctp-") as temp_name:
            root = Path(temp_name)
            project = root / "Project"
            project.mkdir()
            outside = root / "outside.dat"
            outside.write_bytes(b"outside")
            link = project / "linked.dat"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaises(RuntimeError):
                export_ctp(project, root / "Project.ctp")

    def test_refuses_empty_project(self):
        with tempfile.TemporaryDirectory(prefix="lexeditor-chrono-ctp-") as temp_name:
            project = Path(temp_name) / "Project"
            project.mkdir()
            (project / "lexeditor-project.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                export_ctp(project, project.parent / "Project.ctp")


if __name__ == "__main__":
    unittest.main()
