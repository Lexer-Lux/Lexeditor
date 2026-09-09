from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import launch_command, module_load_order, selected_module


def write_module(
    root: Path,
    folder: str,
    module_id: str,
    dependencies=(),
    *,
    singleplayer=True,
    load_after=(),
    incompatible=(),
) -> Path:
    module = root / "Modules" / folder
    module.mkdir(parents=True, exist_ok=True)
    dependency_lines = []
    for dependency_id, optional in dependencies:
        optional_attribute = ' Optional="true"' if optional else ""
        dependency_lines.append(
            f'    <DependedModule Id="{dependency_id}"{optional_attribute} />'
        )
    dependency_xml = "\n".join(dependency_lines)
    singleplayer_value = "true" if singleplayer else "false"
    load_after_xml = "\n".join(f'    <Module Id="{value}" />' for value in load_after)
    incompatible_xml = "\n".join(f'    <Module Id="{value}" />' for value in incompatible)
    (module / "SubModule.xml").write_text(
        f'''<?xml version="1.0" encoding="utf-8"?>
<Module>
  <Name value="{module_id}" />
  <Id value="{module_id}" />
  <Version value="v1.0.0" />
  <SingleplayerModule value="{singleplayer_value}" />
  <MultiplayerModule value="{'false' if singleplayer else 'true'}" />
  <DependedModules>
{dependency_xml}
  </DependedModules>
  <ModulesToLoadAfterThis>
{load_after_xml}
  </ModulesToLoadAfterThis>
  <IncompatibleModules>
{incompatible_xml}
  </IncompatibleModules>
</Module>
''',
        encoding="utf-8",
    )
    return module


def write_core_stack(game: Path, *, harmony=False) -> None:
    if harmony:
        write_module(
            game,
            "Harmony",
            "Bannerlord.Harmony",
            load_after=("Native", "SandBoxCore", "Sandbox", "StoryMode", "CustomBattle"),
        )
    write_module(game, "Native", "Native")
    write_module(game, "SandBoxCore", "SandBoxCore", (("Native", False),))
    write_module(game, "BirthAndDeath", "BirthAndDeath", (("SandBoxCore", False),))
    write_module(game, "CustomBattle", "CustomBattle", (("Native", False), ("SandBoxCore", False)))
    write_module(game, "SandBox", "Sandbox", (("Native", False), ("SandBoxCore", False)))
    write_module(
        game,
        "StoryMode",
        "StoryMode",
        (("Native", False), ("SandBoxCore", False), ("Sandbox", False)),
    )
    write_module(
        game,
        "NavalDLC",
        "NavalDLC",
        (("Native", False), ("SandBoxCore", False), ("Sandbox", False)),
    )


class BannerlordLaunchTests(unittest.TestCase):
    def test_workspace_matches_deployed_module_by_submodule_id(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            deployed = write_module(game, "LexerSkillTweaks", "LexerSkillTweaks")
            module_id, installed = selected_module(game, workspace)
            self.assertEqual(module_id, "LexerSkillTweaks")
            self.assertEqual(installed.resolve(), deployed.resolve())

    def test_direct_launch_honors_harmony_inverse_order_and_modern_official_stack(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            bin_dir = game / "bin" / "Win64_Shipping_Client"
            bin_dir.mkdir(parents=True)
            (bin_dir / "Bannerlord.exe").write_bytes(b"")
            write_core_stack(game, harmony=True)
            write_module(
                game,
                "LexerSkillTweaks",
                "LexerSkillTweaks",
                (("Bannerlord.Harmony", False), ("Native", False), ("SandBoxCore", False), ("Sandbox", False)),
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            order = module_load_order(game, workspace)
            self.assertEqual(
                order,
                [
                    "Bannerlord.Harmony",
                    "Native",
                    "SandBoxCore",
                    "BirthAndDeath",
                    "CustomBattle",
                    "Sandbox",
                    "StoryMode",
                    "NavalDLC",
                    "LexerSkillTweaks",
                ],
            )
            self.assertEqual(len(order), len(set(order)))
            command = launch_command(game, workspace)
            self.assertEqual(command[1], "/singleplayer")
            self.assertEqual(command[2], "_MODULES_*" + "*".join(order) + "*_MODULES_")

    def test_modern_singleplayer_module_category_is_accepted_without_legacy_flag(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            bin_dir = game / "bin" / "Win64_Shipping_Client"
            bin_dir.mkdir(parents=True)
            (bin_dir / "Bannerlord.exe").write_bytes(b"")
            module = game / "Modules" / "ModernModule"
            module.mkdir(parents=True)
            (module / "SubModule.xml").write_text(
                '''<Module>
  <Name value="Modern Module" />
  <Id value="ModernModule" />
  <Version value="v1.0.0" />
  <ModuleCategory value="Singleplayer" />
  <ModuleType value="Community" />
  <DependedModules />
</Module>''',
                encoding="utf-8",
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="ModernModule" /></Module>', encoding="utf-8"
            )
            self.assertEqual(module_load_order(game, workspace), ["ModernModule"])
            self.assertEqual(launch_command(game, workspace)[1], "/singleplayer")

    def test_missing_required_dependency_refuses_launch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            write_module(game, "LexerSkillTweaks", "LexerSkillTweaks", (("Missing.Required.Mod", False),))
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "Missing.Required.Mod"):
                module_load_order(game, workspace)

    def test_installed_optional_dependency_is_not_auto_enabled(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            write_module(game, "OptionalLibrary", "Optional.Library")
            write_module(
                game,
                "LexerSkillTweaks",
                "LexerSkillTweaks",
                (("Optional.Library", True),),
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            self.assertEqual(module_load_order(game, workspace), ["LexerSkillTweaks"])

    def test_missing_optional_dependency_is_allowed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            write_module(game, "LexerSkillTweaks", "LexerSkillTweaks", (("Missing.Optional.Mod", True),))
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            self.assertEqual(module_load_order(game, workspace), ["LexerSkillTweaks"])

    def test_inverse_order_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            write_module(game, "Library", "Library")
            write_module(
                game,
                "LexerSkillTweaks",
                "LexerSkillTweaks",
                (("Library", False),),
                load_after=("Library",),
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "load-order constraints form a cycle"):
                module_load_order(game, workspace)

    def test_incompatible_enabled_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            write_module(game, "Native", "Native")
            write_module(
                game,
                "LexerSkillTweaks",
                "LexerSkillTweaks",
                incompatible=("Native",),
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="LexerSkillTweaks" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "Incompatible Bannerlord modules"):
                module_load_order(game, workspace)

    def test_multiplayer_only_module_refuses_singleplayer_direct_launch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            game = root / "game"
            workspace = root / "workspace"
            workspace.mkdir()
            bin_dir = game / "bin" / "Win64_Shipping_Client"
            bin_dir.mkdir(parents=True)
            (bin_dir / "Bannerlord.exe").write_bytes(b"")
            write_module(
                game,
                "MultiplayerOnly",
                "MultiplayerOnly",
                singleplayer=False,
            )
            (workspace / "SubModule.xml").write_text(
                '<Module><Id value="MultiplayerOnly" /></Module>', encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "single-player modules only"):
                launch_command(game, workspace)


if __name__ == "__main__":
    unittest.main()
