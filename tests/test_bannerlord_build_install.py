from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.project_data import run_build


CSPROJ = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net472</TargetFramework>
    <BannerlordDir>C:\\Wrong Game</BannerlordDir>
  </PropertyGroup>
</Project>
'''


class BannerlordBuildInstallTests(unittest.TestCase):
    def test_selected_game_root_is_passed_as_msbuild_global_property(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            (project / "Mod.csproj").write_text(CSPROJ, encoding="utf-8")
            selected_game = root / "Selected Bannerlord Install"
            selected_game.mkdir()
            completed = subprocess.CompletedProcess(["dotnet"], 0, stdout="Build succeeded\n", stderr="")
            with patch("games.bannerlord.project_data.subprocess.run", return_value=completed) as runner:
                result = run_build(project, configuration="Release", game_root=selected_game)

            command = runner.call_args.args[0]
            expected = f"-p:BannerlordDir={selected_game.resolve()}"
            self.assertIn(expected, command)
            self.assertEqual(command.count(expected), 1)
            self.assertFalse(runner.call_args.kwargs.get("shell", False))
            self.assertEqual(result["gameRootOverride"], str(selected_game.resolve()))
            self.assertTrue(result["succeeded"])

    def test_session_environment_root_is_used_when_explicit_root_is_omitted(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            (project / "Mod.csproj").write_text(CSPROJ, encoding="utf-8")
            selected_game = root / "Game Root From Environment"
            selected_game.mkdir()
            completed = subprocess.CompletedProcess(["dotnet"], 0, stdout="ok", stderr="")
            with patch.dict("os.environ", {"LEXEDITOR_BANNERLORD_ROOT": str(selected_game)}, clear=False), \
                 patch("games.bannerlord.project_data.subprocess.run", return_value=completed) as runner:
                result = run_build(project)
            self.assertIn(f"-p:BannerlordDir={selected_game.resolve()}", runner.call_args.args[0])
            self.assertEqual(result["gameRootOverride"], str(selected_game.resolve()))

    def test_auto_selected_project_file_cannot_escape_selected_project(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            outside = root / "Outside.csproj"
            outside.write_text(CSPROJ, encoding="utf-8")
            with patch("games.bannerlord.project_data.primary_project_file", return_value=outside):
                with self.assertRaisesRegex(ValueError, "stay inside"):
                    run_build(project)


if __name__ == "__main__":
    unittest.main()
