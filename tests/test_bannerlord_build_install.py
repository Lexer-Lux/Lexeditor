from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from games.bannerlord.project_data import primary_project_file, run_build


CSPROJ = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net472</TargetFramework>
    <BannerlordDir>C:\\Wrong Game</BannerlordDir>
    <GameBin>C:\\Wrong Game\\bin</GameBin>
    <ModuleDir>C:\\Wrong Module</ModuleDir>
    <OutputPath>C:\\Wrong Output\\</OutputPath>
  </PropertyGroup>
</Project>
'''
SUBMODULE = '<Module><Id value="SafeModule" /><SingleplayerModule value="true" /></Module>'


def write_project(project: Path) -> None:
    (project / "Mod.csproj").write_text(CSPROJ, encoding="utf-8")
    (project / "SubModule.xml").write_text(SUBMODULE, encoding="utf-8")


class BannerlordBuildInstallTests(unittest.TestCase):
    def test_selected_game_root_pins_standard_build_and_deploy_paths(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            write_project(project)
            selected_game = root / "Selected Bannerlord Install"
            selected_game.mkdir()
            completed = subprocess.CompletedProcess(["dotnet"], 0, stdout="Build succeeded\n", stderr="")
            with patch("games.bannerlord.project_data.subprocess.run", return_value=completed) as runner:
                result = run_build(project, configuration="Release", game_root=selected_game)

            command = runner.call_args.args[0]
            selected = selected_game.resolve()
            expected = {
                "BannerlordDir": str(selected),
                "GameBin": str((selected / "bin" / "Win64_Shipping_Client").resolve()),
                "ModuleDir": str((selected / "Modules" / "SafeModule").resolve()),
                "OutputPath": str((selected / "Modules" / "SafeModule" / "bin" / "Win64_Shipping_Client").resolve()) + os.sep,
                "LexeditorSkipAssetDeploy": "true",
            }
            for property_name, value in expected.items():
                argument = f"-p:{property_name}={value}"
                self.assertIn(argument, command)
                self.assertEqual(command.count(argument), 1)
            self.assertFalse(runner.call_args.kwargs.get("shell", False))
            self.assertEqual(result["gameRootOverride"], str(selected))
            self.assertEqual(result["pathOverrides"], expected)
            self.assertTrue(result["succeeded"])

    def test_session_environment_root_is_used_when_explicit_root_is_omitted(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            write_project(project)
            selected_game = root / "Game Root From Environment"
            selected_game.mkdir()
            completed = subprocess.CompletedProcess(["dotnet"], 0, stdout="ok", stderr="")
            with patch.dict("os.environ", {"LEXEDITOR_BANNERLORD_ROOT": str(selected_game)}, clear=False), \
                 patch("games.bannerlord.project_data.subprocess.run", return_value=completed) as runner:
                result = run_build(project)
            selected = selected_game.resolve()
            command = runner.call_args.args[0]
            self.assertIn(f"-p:BannerlordDir={selected}", command)
            self.assertIn(f"-p:GameBin={(selected / 'bin' / 'Win64_Shipping_Client').resolve()}", command)
            self.assertIn(f"-p:ModuleDir={(selected / 'Modules' / 'SafeModule').resolve()}", command)
            self.assertIn("-p:LexeditorSkipAssetDeploy=true", command)
            self.assertEqual(result["gameRootOverride"], str(selected))

    def test_selected_install_build_rejects_unsafe_module_id_before_dotnet(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            (project / "Mod.csproj").write_text(CSPROJ, encoding="utf-8")
            (project / "SubModule.xml").write_text(
                '<Module><Id value="../Escape" /></Module>', encoding="utf-8"
            )
            with patch("games.bannerlord.project_data.subprocess.run") as runner:
                with self.assertRaisesRegex(ValueError, "unsafe module Id"):
                    run_build(project, game_root=root / "game")
            runner.assert_not_called()

    def test_selected_install_build_rejects_redirected_module_path_before_dotnet(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            write_project(project)
            selected_game = root / "game"
            selected_game.mkdir()
            outside = root / "outside-module"
            outside.mkdir()
            selected = selected_game.resolve()
            modules_root = selected / "Modules"
            outside_resolved = outside.resolve()
            real_resolve = Path.resolve

            def fake_resolve(path, *args, **kwargs):
                if path == modules_root / "SafeModule":
                    return outside_resolved
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=fake_resolve), \
                 patch("games.bannerlord.project_data.subprocess.run") as runner:
                with self.assertRaisesRegex(ValueError, "build module path escaped"):
                    run_build(project, game_root=selected_game)
            runner.assert_not_called()

    def test_selected_install_build_rejects_redirected_output_path_before_dotnet(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            write_project(project)
            selected_game = root / "game"
            selected_game.mkdir()
            outside = root / "outside-output"
            outside.mkdir()
            selected = selected_game.resolve()
            module_dir = selected / "Modules" / "SafeModule"
            output_path = module_dir / "bin" / "Win64_Shipping_Client"
            outside_resolved = outside.resolve()
            real_resolve = Path.resolve

            def fake_resolve(path, *args, **kwargs):
                if path == output_path:
                    return outside_resolved
                return real_resolve(path, *args, **kwargs)

            with patch.object(Path, "resolve", new=fake_resolve), \
                 patch("games.bannerlord.project_data.subprocess.run") as runner:
                with self.assertRaisesRegex(ValueError, "build output path escaped"):
                    run_build(project, game_root=selected_game)
            runner.assert_not_called()

    def test_primary_project_file_cannot_escape_selected_project(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            project = root / "project"
            project.mkdir()
            outside = root / "Outside.csproj"
            outside.write_text(CSPROJ, encoding="utf-8")
            with patch("games.bannerlord.project_data._project_files", return_value=[outside]):
                with self.assertRaisesRegex(ValueError, "stay inside"):
                    primary_project_file(project)

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
