from pathlib import Path
import tempfile
import unittest

from games.bannerlord.game_launch import BannerlordGameController


def write_module(root: Path, module_id: str) -> Path:
    module = root / "Modules" / module_id
    module.mkdir(parents=True, exist_ok=True)
    (module / "SubModule.xml").write_text(
        f'<Module><Name value="{module_id}"/><Id value="{module_id}"/>'
        '<SingleplayerModule value="true"/><DependedModules/></Module>',
        encoding="utf-8",
    )
    return module


class FakeProcess:
    pid = 4242

    def __init__(self, command, cwd, *, exited=False):
        self.command = command
        self.cwd = cwd
        self.returncode = 1 if exited else None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class BannerlordGameControllerTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        game = root / "game"
        workspace = root / "workspace"
        workspace.mkdir()
        bin_dir = game / "bin" / "Win64_Shipping_Client"
        bin_dir.mkdir(parents=True)
        (bin_dir / "Bannerlord.exe").write_bytes(b"")
        write_module(game, "LexerSkillTweaks")
        (workspace / "SubModule.xml").write_text(
            '<Module><Id value="LexerSkillTweaks"/></Module>', encoding="utf-8"
        )
        return temporary, game, workspace

    def test_launch_status_and_stop_track_only_owned_process(self):
        temporary, game, workspace = self.fixture()
        try:
            created = []
            def factory(command, cwd):
                process = FakeProcess(command, cwd)
                created.append(process)
                return process

            controller = BannerlordGameController(process_factory=factory)
            launched = controller.launch(game, workspace)
            self.assertTrue(launched["running"])
            self.assertFalse(launched["alreadyRunning"])
            self.assertEqual(launched["module"], "LexerSkillTweaks")
            self.assertEqual(launched["pid"], 4242)
            self.assertIn("LexerSkillTweaks", launched["loadOrder"])
            again = controller.launch(game, workspace)
            self.assertTrue(again["alreadyRunning"])
            self.assertEqual(len(created), 1)
            stopped = controller.stop()
            self.assertTrue(stopped["stopped"])
            self.assertTrue(created[0].terminated)
            self.assertFalse(controller.status()["running"])
        finally:
            temporary.cleanup()

    def test_immediate_exit_is_not_reported_as_running(self):
        temporary, game, workspace = self.fixture()
        try:
            controller = BannerlordGameController(
                process_factory=lambda command, cwd: FakeProcess(command, cwd, exited=True)
            )
            with self.assertRaisesRegex(RuntimeError, "exited immediately"):
                controller.launch(game, workspace)
            self.assertFalse(controller.status()["running"])
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
