"""The app must start.

Two plugin registries refused a new plugin in a row - a relative project
template, then a missing Mod Loading entry - and both were caught by a person
opening the program rather than by this suite. Every one of those checks lives
behind app.discover_plugins, so that is what this runs: whatever the shell
validates at startup, in the order it validates it, against the plugins
actually in the repository.
"""
import importlib
import os
from pathlib import Path
import unittest

from core.plugin_api import validate_plugin


ROOT = Path(__file__).resolve().parents[2]


def _key(path: Path) -> str:
    """One comparable form of a path: resolved, and case-folded on Windows."""
    return os.path.normcase(str(Path(path).resolve()))


def plugins():
    for path in sorted((ROOT / "plugins").glob("*/plugin.py")):
        module = importlib.import_module("plugins." + path.parent.name + ".plugin")
        yield path.parent.name, getattr(module, "PLUGIN", None)


class Startup(unittest.TestCase):
    def test_the_app_discovers_and_accepts_every_plugin(self):
        """Exactly what happens when Lexeditor opens, minus the window.

        This covers the descriptor validation, the credits bundle and the mod
        loading document at once, because discover_plugins is where the shell
        checks all three. A plugin added without one of them fails here now
        instead of in a dialog.
        """
        import app

        plugins = app.discover_plugins()
        self.assertTrue(plugins)
        folders = {path.parent.name for path in (ROOT / "plugins").glob("*/plugin.py")}
        self.assertEqual(len(plugins), len(folders))


    def test_every_plugin_service_is_one_the_runtime_will_start(self):
        """The allowlist and the plugins must agree.

        A plugin whose service module is not listed imports, validates, and
        opens its window, then fails the moment someone clicks the game. That
        is too late to find out.
        """
        import app
        from core.runtime_bootstrap import SERVICE_MODULES

        for plugin_id, plugin in sorted(app.discover_plugins().items()):
            with self.subTest(plugin=plugin_id):
                session = plugin.session_factory()
                self.assertIn(session.module, SERVICE_MODULES,
                              f"{plugin_id} runs {session.module}, which the runtime refuses")
                self.assertTrue((ROOT / Path(session.module.replace(".", "/") + ".py")).is_file(),
                                f"{session.module} has no file behind it")


class PluginDescriptors(unittest.TestCase):
    def test_windows_project_defaults_are_valid_metadata_on_posix(self):
        from dataclasses import replace
        from pathlib import PurePosixPath
        from types import SimpleNamespace
        from unittest.mock import patch
        from plugins.ff7r.plugin import PLUGIN

        with patch('core.plugin_api.os', SimpleNamespace(name='posix')):
            for path in ('C:/FF7RMod', '/home/player/FF7RMod'):
                validate_plugin(replace(PLUGIN, projects=replace(
                    PLUGIN.projects, default_root=PurePosixPath(path))))
            for path in ('relative/mod', 'C:relative'):
                with self.assertRaisesRegex(ValueError, 'invalid project descriptor'):
                    validate_plugin(replace(PLUGIN, projects=replace(
                        PLUGIN.projects, default_root=PurePosixPath(path))))

    def test_every_plugin_exports_one_and_validates(self):
        found = list(plugins())
        self.assertTrue(found, "no plugins were discovered")
        for directory, plugin in found:
            with self.subTest(plugin=directory):
                self.assertIsNotNone(plugin, f"plugins/{directory}/plugin.py exports no PLUGIN")
                validate_plugin(plugin)

    def test_a_created_project_starts_from_a_real_template(self):
        # canCreate is false when the template folder is missing, which turns
        # the Create button off rather than failing when it is pressed. A
        # plugin that offers project creation should mean it.
        for directory, plugin in plugins():
            spec = getattr(plugin, "projects", None)
            if spec is None or not spec.template_root or not spec.template_root.is_dir():
                continue
            with self.subTest(plugin=directory):
                names = {path.name for path in spec.template_root.rglob("*")}
                self.assertTrue(names, f"{directory}'s project template is empty")
                for group in spec.required_any or ():
                    if any((spec.template_root / name).exists() for name in group):
                        break
                else:
                    if spec.required_any:
                        self.fail(f"{directory}'s template satisfies none of its own "
                                  f"required paths: {spec.required_any}")

    def test_plugin_ids_match_their_folders(self):
        for directory, plugin in plugins():
            with self.subTest(plugin=directory):
                self.assertEqual(plugin.plugin_id.replace("-", "_"),
                                 directory.replace("-", "_"))

    def test_no_plugin_opens_on_a_folder_inside_the_app(self):
        """The folder a session starts on is never part of Lexeditor itself.

        FF9's default project folder fell back to the plugin's own
        `project_template` whenever the real folder did not exist yet, so a
        game nobody had modded opened on the shipped starter and the header
        named `project_template` as the current, editable mod. Lexer read that
        as the editor creating a mod on its own opening. A copy source lives
        inside the app; a project a reader edits never does.
        """
        app = _key(ROOT)
        for directory, plugin in plugins():
            spec = getattr(plugin, "projects", None)
            if spec is None:
                continue
            with self.subTest(plugin=directory):
                default = spec.default_root.resolve()
                self.assertNotEqual(
                    _key(default), app,
                    f"{directory} opens on the app's own folder, {default}")
                self.assertNotIn(
                    app, {_key(parent) for parent in default.parents},
                    f"{directory}'s default project folder {default} sits "
                    f"inside Lexeditor's own folder")

    def test_a_game_with_no_project_folder_yet_reports_no_mod(self):
        """Vanilla is the ordinary state, not a damaged project.

        When the folder a plugin would write into does not exist and the
        reader never chose one, the store says `noMod`. Home keeps the card
        ready and the session opens on the game's own data, read-only, which
        is what Lexer's rule requires: Lexeditor never creates a mod the
        reader did not ask for.
        """
        import tempfile
        from dataclasses import replace as replace_field

        from core.project_manager import ProjectManager

        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            for directory, plugin in plugins():
                spec = getattr(plugin, "projects", None)
                if spec is None:
                    continue
                with self.subTest(plugin=directory):
                    never_created = scratch / "folder-that-does-not-exist"
                    patched = replace_field(plugin, projects=replace_field(
                        spec, default_root=never_created))
                    manager = ProjectManager({plugin.plugin_id: patched},
                                             scratch / f"{plugin.plugin_id}.json")
                    row = manager.snapshot(plugin.plugin_id)["projects"][0]
                    self.assertTrue(row["noMod"], row)
                    self.assertFalse(row["valid"], row)
                    self.assertIn("Create one to save changes", row["problems"][0], row)


if __name__ == "__main__":
    unittest.main()
