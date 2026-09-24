"""The shared UI stays browsable and stays shared.

Blank is the one place every shared component is shown, so a component that is
exported without being catalogued is invisible there and drifts. And a plugin
may not reach further into the shared components than it already does.
"""
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from generate_component_usage import exports  # noqa: E402


def catalogued() -> list[str]:
    source = (ROOT / "ui" / "component-catalog.js").read_text(encoding="utf-8")
    body = source[source.index("const entries = ["):source.index("window.LexeditorComponentCatalog")]
    return re.findall(r'^\s*\{id:\s*"([A-Za-z_][A-Za-z0-9_]*)",\s*level:', body, re.M)


class SharedUiCatalogTests(unittest.TestCase):
    def test_every_shared_component_is_catalogued(self):
        missing = sorted(set(exports()) - set(catalogued()))
        self.assertEqual(missing, [], "Add these to ui/component-catalog.js so Blank shows them")

    def test_the_catalogue_names_only_real_components(self):
        unknown = sorted(set(catalogued()) - set(exports()))
        self.assertEqual(unknown, [], "These are catalogued but the framework does not export them")

    def test_every_entry_has_a_level_and_a_summary(self):
        source = (ROOT / "ui" / "component-catalog.js").read_text(encoding="utf-8")
        levels = set(re.findall(r'\{id: "(\w+)", label:', source))
        self.assertTrue(levels, "the catalogue declares no levels")
        for entry in re.findall(r'\{id: "([A-Za-z_][A-Za-z0-9_]*)", level: "(\w+)", summary: "([^"]*)"', source):
            name, level, summary = entry
            self.assertIn(level, levels, name)
            self.assertTrue(summary.strip(), name)

    def test_a_component_every_game_needs_is_in_every_game(self):
        """Counting use is not enough: the catalogue says what should use it."""
        import json

        source = (ROOT / "ui" / "component-catalog.js").read_text(encoding="utf-8")
        usage = json.loads((ROOT / "ui" / "component-usage.json").read_text(encoding="utf-8"))["components"]
        games = {name for names in usage.values() for name in names} - {"blank"}
        required = re.findall(r'^\s{4}\{id: "(\w+)", level: "\w+", expect: "every game"', source, re.M)
        self.assertTrue(required, "no component claims to be needed by every game")
        for component in required:
            missing = sorted(games - set(usage.get(component, [])))
            self.assertEqual(missing, [], f"{component} is missing from {missing}")

    def test_component_usage_is_generated_not_remembered(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/generate_component_usage.py"), "--check"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plugins_do_not_copy_more_of_each_other(self):
        result = subprocess.run([sys.executable, str(ROOT / "tests/verify_shared_code_budget.py")],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plugins_do_not_reach_further_into_the_shared_ui(self):
        result = subprocess.run([sys.executable, str(ROOT / "tests/verify_shared_ui_budget.py")],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
