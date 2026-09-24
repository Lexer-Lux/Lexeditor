"""Each game says where its ReShade loader goes. Nothing is inferred.

Rebirth and Remake keep their renderer in End/Binaries/Win64 and FF9 keeps
its in x64. Lexeditor wrote the DLL to the installation root, where Windows
never looks for it, and reported success: the page said ReShade was installed
and the game started with none in it.

Working it out from the launch path was the first repair and it was still a
guess - FF9's launch path is a launcher at the root, and the renderer is
somewhere else entirely. The folder is declared per game now, and a game that
declares one it does not have is an error rather than a quiet fall back.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest

from core import desktop_host


class LoaderLocation(unittest.TestCase):
    def _host(self, tmp_path, declared, made=("End/Binaries/Win64",)):
        plugin = SimpleNamespace(installation=SimpleNamespace(
            launch_path="", reshade_root=declared))
        for relative in made:
            (tmp_path / relative).mkdir(parents=True, exist_ok=True)
        host = desktop_host.HostApi.__new__(desktop_host.HostApi)
        host._plugins = {"game": plugin}
        host._installations = SimpleNamespace(
            snapshot=lambda plugin_id: {"root": str(tmp_path)})
        return host

    def setUp(self):
        import tempfile
        self._folder = tempfile.TemporaryDirectory(prefix="lex-loader-")
        self.addCleanup(self._folder.cleanup)
        self.root = Path(self._folder.name)

    def test_it_lands_where_the_game_declares(self):
        host = self._host(self.root, "End/Binaries/Win64")
        self.assertEqual(host._reshade_root("game"),
                         self.root / "End" / "Binaries" / "Win64")

    def test_a_backslash_declaration_is_read_the_same_way(self):
        host = self._host(self.root, "End\\Binaries\\Win64")
        self.assertEqual(host._reshade_root("game"),
                         self.root / "End" / "Binaries" / "Win64")

    def test_an_empty_declaration_means_the_root(self):
        host = self._host(self.root, "")
        self.assertEqual(host._reshade_root("game"), self.root)

    def test_a_folder_the_game_does_not_have_is_refused(self):
        # Falling back to the root is how the DLL ended up somewhere useless.
        host = self._host(self.root, "Missing/Folder", made=())
        with self.assertRaises(ValueError) as refused:
            host._reshade_root("game")
        self.assertIn("Nothing was written", str(refused.exception))

    def test_no_game_means_no_directory(self):
        host = self._host(self.root, "End/Binaries/Win64")
        host._installations = SimpleNamespace(snapshot=lambda plugin_id: {})
        self.assertIsNone(host._reshade_root("game"))

    def test_every_installed_plugin_resolves_somewhere_real(self):
        import app
        from core.game_installation import GameInstallationManager

        plugins = app.discover_plugins()
        host = desktop_host.HostApi.__new__(desktop_host.HostApi)
        host._plugins = plugins
        host._installations = GameInstallationManager(plugins, auto_scan=False)
        for plugin_id, plugin in sorted(plugins.items()):
            if getattr(plugin, "installation", None) is None:
                continue
            with self.subTest(plugin=plugin_id):
                found = host._reshade_root(plugin_id)
                if found is None:
                    continue  # the game is not installed on this machine
                self.assertTrue(found.is_dir(), f"{plugin_id} resolved to {found}")
                # The check that would have caught Rebirth: a renderer wrapper
                # is only loaded from a folder holding an executable.
                self.assertTrue(list(found.glob("*.exe")),
                                f"{plugin_id} points ReShade at {found}, which has no "
                                "executable, so nothing there would ever load it")


if __name__ == "__main__":
    unittest.main()
