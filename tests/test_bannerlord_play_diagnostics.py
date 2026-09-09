from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import module_load_order
from games.bannerlord.runtime_data import deployment_status


def write_module(root: Path, module_id: str, *, dependencies=(), load_after=()) -> Path:
    folder = root / "Modules" / module_id
    folder.mkdir(parents=True, exist_ok=True)
    depended = "\n".join(f'    <DependedModule Id="{value}" />' for value in dependencies)
    after = "\n".join(f'    <Module Id="{value}" />' for value in load_after)
    descriptor = f'''<Module>
  <Name value="{module_id}" />
  <Id value="{module_id}" />
  <Version value="v1" />
  <ModuleCategory value="Singleplayer" />
  <DependedModules>
{depended}
  </DependedModules>
  <ModulesToLoadAfterThis>
{after}
  </ModulesToLoadAfterThis>
  <SubModules />
</Module>
'''
    (folder / "SubModule.xml").write_text(descriptor, encoding="utf-8")
    return folder


class BannerlordPlayDiagnosticTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        game = root / "game"
        project = root / "project"
        project.mkdir()
        executable = game / "bin" / "Win64_Shipping_Client" / "Bannerlord.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        (game / "Modules").mkdir()
        return temporary, game, project

    def test_runnable_status_exposes_same_load_order_as_play(self):
        temporary, game, project = self.fixture()
        try:
            write_module(game, "Library")
            deployed = write_module(game, "Selected", dependencies=("Library",))
            (project / "SubModule.xml").write_bytes((deployed / "SubModule.xml").read_bytes())
            status = deployment_status(project, game)
            self.assertTrue(status["runnable"])
            self.assertEqual(status["playError"], "")
            self.assertEqual(status["loadOrder"], module_load_order(game, project))
            self.assertEqual(status["loadOrder"], ["Library", "Selected"])
        finally:
            temporary.cleanup()

    def test_load_order_cycle_makes_status_non_runnable_with_play_error(self):
        temporary, game, project = self.fixture()
        try:
            write_module(game, "Library")
            deployed = write_module(
                game,
                "Selected",
                dependencies=("Library",),
                load_after=("Library",),
            )
            (project / "SubModule.xml").write_bytes((deployed / "SubModule.xml").read_bytes())
            status = deployment_status(project, game)
            self.assertFalse(status["runnable"])
            self.assertIn("load-order constraints form a cycle", status["playError"])
            self.assertTrue(any("Play load-order validation failed" in row for row in status["issues"]))
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
