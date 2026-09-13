"""Every plugin the shell will load must survive the shell's own validation.

This exists because a plugin shipped that the app refused at startup with
"has a relative project template". The check was there; nothing ran it over
the plugins in the repository, so the failure waited for a person to open the
program. It runs here now.
"""
import importlib
from pathlib import Path
import unittest

from plugin_api import validate_plugin


ROOT = Path(__file__).resolve().parents[1]


def plugins():
    for path in sorted((ROOT / "games").glob("*/plugin.py")):
        module = importlib.import_module("games." + path.parent.name + ".plugin")
        yield path.parent.name, getattr(module, "PLUGIN", None)


class PluginDescriptors(unittest.TestCase):
    def test_every_plugin_exports_one_and_validates(self):
        found = list(plugins())
        self.assertTrue(found, "no plugins were discovered")
        for directory, plugin in found:
            with self.subTest(plugin=directory):
                self.assertIsNotNone(plugin, f"games/{directory}/plugin.py exports no PLUGIN")
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


if __name__ == "__main__":
    unittest.main()
