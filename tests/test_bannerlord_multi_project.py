from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.project_data import primary_project_file, resolve_project_file, run_build
from games.bannerlord import server


PROJECT_XML = '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>net472</TargetFramework></PropertyGroup></Project>'


class BannerlordMultiProjectTests(unittest.TestCase):
    def make_workspace(self, root: Path):
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "A.csproj").write_text(PROJECT_XML, encoding="utf-8")
        (workspace / "B.csproj").write_text(PROJECT_XML, encoding="utf-8")
        (workspace / "SubModule.xml").write_text('<Module><Id value="Example"/><SingleplayerModule value="true"/></Module>', encoding="utf-8")
        return workspace

    def test_primary_project_refuses_multiple_candidates(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = self.make_workspace(Path(name))
            with self.assertRaisesRegex(ValueError, "Several .csproj files"):
                primary_project_file(workspace)

    def test_explicit_selection_resolves_exact_top_level_project(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = self.make_workspace(Path(name))
            self.assertEqual(resolve_project_file(workspace, "B.csproj").name, "B.csproj")
            with self.assertRaisesRegex(ValueError, "top-level"):
                resolve_project_file(workspace, "nested/B.csproj")
            with self.assertRaisesRegex(ValueError, "top-level"):
                resolve_project_file(workspace, "../B.csproj")

    def test_project_summary_stays_available_and_requires_choice(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = self.make_workspace(Path(name))
            with patch.object(server, "PROJECT", workspace):
                summary = server.project_summary()
                selected = server.project_summary("B.csproj")
            self.assertEqual(summary["projectFiles"], ["A.csproj", "B.csproj"])
            self.assertIsNone(summary["projectFile"])
            self.assertIn("choose", summary["projectError"].lower())
            self.assertEqual(selected["projectFile"]["name"], "B.csproj")

    def test_build_without_selection_refuses_multiple_projects_before_dotnet(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = self.make_workspace(Path(name))
            with patch("games.bannerlord.project_data.subprocess.run") as runner:
                with self.assertRaisesRegex(ValueError, "Several .csproj files"):
                    run_build(workspace)
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
