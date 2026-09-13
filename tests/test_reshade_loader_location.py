"""ReShade goes beside the game's executable, not at the top of its folder.

Rebirth and Remake keep their executable in End/Binaries/Win64. Lexeditor put
the loader DLL at the installation root instead, where Windows never looks for
it, so every install reported success and the game started with no ReShade in
it at all.
"""
from pathlib import Path
from types import SimpleNamespace
import unittest

import desktop_host


class LoaderLocation(unittest.TestCase):
    def _host(self, tmp_path, launch_path, made=("End/Binaries/Win64",)):
        plugin = SimpleNamespace(installation=SimpleNamespace(launch_path=launch_path))
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

    def test_it_lands_beside_a_nested_executable(self):
        host = self._host(self.root, "End/Binaries/Win64/ff7rebirth_.exe")
        self.assertEqual(host._reshade_root("game"),
                         self.root / "End" / "Binaries" / "Win64")

    def test_a_backslash_launch_path_is_read_the_same_way(self):
        host = self._host(self.root, "End\\Binaries\\Win64\\ff7remake_.exe")
        self.assertEqual(host._reshade_root("game"),
                         self.root / "End" / "Binaries" / "Win64")

    def test_an_executable_at_the_top_keeps_the_root(self):
        host = self._host(self.root, "FF8_EN.exe")
        self.assertEqual(host._reshade_root("game"), self.root)

    def test_a_plugin_that_names_no_executable_keeps_the_root(self):
        host = self._host(self.root, "")
        self.assertEqual(host._reshade_root("game"), self.root)

    def test_a_folder_the_game_does_not_have_falls_back_to_the_root(self):
        # Better the root than a path that does not exist: the install then
        # fails loudly instead of writing into a folder it just invented.
        host = self._host(self.root, "Missing/Folder/game.exe", made=())
        self.assertEqual(host._reshade_root("game"), self.root)

    def test_no_game_means_no_directory(self):
        host = self._host(self.root, "End/Binaries/Win64/game.exe")
        host._installations = SimpleNamespace(snapshot=lambda plugin_id: {})
        self.assertIsNone(host._reshade_root("game"))

    def test_every_installed_plugin_resolves_somewhere_real(self):
        import app
        from game_installation import GameInstallationManager

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
                launch = plugin.installation.launch_path
                if launch and "/" in launch.replace("\\", "/"):
                    self.assertNotEqual(found, Path(
                        host._installations.snapshot(plugin_id)["root"]),
                        f"{plugin_id} keeps its executable in a subfolder")


if __name__ == "__main__":
    unittest.main()
