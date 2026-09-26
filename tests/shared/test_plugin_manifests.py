"""One metadata file per plugin, and it is the one the plugin reads.

The accent, the Steam application, where the game installs, which of its
programs is the game and the lines it shows while loading used to be written
in full inside `plugins/<id>/plugin.py`, between lambdas and a session class.
This holds the split: the data is in `plugin.json`, the behaviour is in the
module, and the module builds its descriptor from the file.
"""
import importlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.plugin_manifest import loading_quotes, manifest  # noqa: E402


def plugins():
    for path in sorted((ROOT / "plugins").glob("*/plugin.py")):
        module = importlib.import_module(f"plugins.{path.parent.name}.plugin")
        yield path.parent, module.PLUGIN


class PluginManifestTests(unittest.TestCase):
    def test_every_plugin_has_a_manifest_named_after_its_folder(self):
        found = 0
        for directory, plugin in plugins():
            with self.subTest(plugin=directory.name):
                path = directory / "plugin.json"
                self.assertTrue(path.is_file(), f"{directory.name} has no plugin.json")
                data = manifest(directory / "plugin.py")
                self.assertEqual(data["id"], plugin.plugin_id)
                # The file is the record of the id, so the id cannot drift from
                # the folder it lives in.
                self.assertEqual(plugin.plugin_id.replace("-", "_"), directory.name.replace("-", "_"))
                found += 1
        self.assertGreaterEqual(found, 19, found)

    def test_the_plugin_file_does_not_restate_the_metadata(self):
        """A fact with two homes drifts. These fields come from the file only."""
        import ast

        for directory, _plugin in plugins():
            with self.subTest(plugin=directory.name):
                source = (directory / "plugin.py").read_text(encoding="utf-8")
                self.assertIn("**plugin_defaults(__file__)", source)
                call = next(node for node in ast.walk(ast.parse(source))
                            if isinstance(node, ast.Call)
                            and getattr(node.func, "id", "") == "GamePlugin")
                given = {keyword.arg for keyword in call.keywords if keyword.arg}
                # The session class passes its own plugin_id; that is wiring,
                # not the game's metadata. The descriptor must not restate it.
                self.assertEqual(
                    given & {"plugin_id", "name", "accent", "process_names",
                             "can_launch", "mods_load"},
                    set(), f"{directory.name} restates metadata in its descriptor")

    def test_the_descriptor_matches_the_manifest(self):
        for directory, plugin in plugins():
            with self.subTest(plugin=directory.name):
                data = manifest(directory / "plugin.py")
                self.assertEqual(plugin.name, data["name"])
                self.assertEqual(plugin.accent, data["accent"])
                self.assertEqual(list(plugin.process_names), data.get("processNames", []))
                self.assertEqual(plugin.can_launch, data.get("canLaunch", True))
                install, declared = plugin.installation, data.get("installation")
                if declared:
                    self.assertEqual(install.executable, declared["executable"])
                    self.assertEqual(install.steam_app_id, declared["steamAppId"])
                    self.assertEqual(list(install.install_dir_names), declared["installDirNames"])
                    self.assertEqual([str(path) for path in install.default_roots],
                                     declared["defaultRoots"])
                    self.assertEqual(list(install.required_paths), declared["requiredPaths"])
                else:
                    self.assertIsNone(install)
                projects, project_data = plugin.projects, data.get("projects")
                if project_data:
                    self.assertEqual(projects.root_env, project_data["rootEnv"])
                    self.assertEqual(list(projects.required_paths), project_data["requiredPaths"])
                else:
                    self.assertIsNone(projects)

    def test_the_manifest_holds_no_value_from_this_machine(self):
        """Computed values stay in code: a project folder under the reader's
        Documents, or downloaded art, must not be frozen into the file."""
        home = str(Path.home())
        for directory, _plugin in plugins():
            with self.subTest(plugin=directory.name):
                text = (directory / "plugin.json").read_text(encoding="utf-8")
                self.assertNotIn(home, text)
                self.assertNotIn("Documents", text)
                self.assertNotIn("cover-art", text)

    def test_loading_lines_come_from_the_manifest(self):
        for directory, plugin in plugins():
            with self.subTest(plugin=directory.name):
                declared = manifest(directory / "plugin.py").get("loadingQuotes", [])
                self.assertEqual(loading_quotes(plugin.plugin_id), list(dict.fromkeys(declared)))
                self.assertFalse((directory / "loading_quotes.json").is_file(),
                                 f"{directory.name} still has a second quotes file")
        # A game that borrows another's lines says so by holding them.
        self.assertTrue(loading_quotes("ff8"))
        self.assertEqual(loading_quotes("ff7-2013"), loading_quotes("ff7"))
        # The shared file keeps only the lines that are about no game.
        shared = json.loads((ROOT / "ui" / "loading_quotes.json").read_text(encoding="utf-8"))
        self.assertEqual(list(shared), ["global"])


if __name__ == "__main__":
    unittest.main()
