"""Stylesheets may only get cleaner.

A plugin stylesheet should hold theme tokens and nothing else; the framework
should define each rule once, without !important. These ceilings are today's
counts (tools/css_audit.py). Lower one whenever the real count drops. Raising
one means a plugin went back to styling itself, which is the bug this exists
to stop.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import css_audit  # noqa: E402

# Non-token rules per plugin; the target for every one is 0.
PLUGIN_RULES = {
    "bannerlord": 1, "blank": 0, "factorio": 0, "ff7": 0, "ff7r": 0, "ff7r2": 0, "ff8": 0, "ff9": 0,
    "palworld": 0, "project_zomboid": 0, "rdr": 0, "rdr2": 0, "terraria": 0, "warband": 0, "ds3": 0, "ffx_x2": 0, "stardew_valley": 0, "chrono_trigger": 0,
}
PLUGIN_IMPORTANT = {
    "bannerlord": 0, "blank": 0, "factorio": 0, "ff7": 0, "ff7r": 0, "ff7r2": 0, "ff8": 0, "ff9": 0,
    "palworld": 0, "project_zomboid": 0, "rdr": 0, "rdr2": 0, "terraria": 0, "warband": 0, "ds3": 0, "ffx_x2": 0, "stardew_valley": 0, "chrono_trigger": 0,
}
FRAMEWORK_DUPLICATES = 0
# One, and only for `[hidden]`: see the comment on it in ui/framework.css.
FRAMEWORK_IMPORTANT = 1


class CssBudgetTests(unittest.TestCase):
    def setUp(self):
        self.summary = css_audit.summary()

    def test_plugin_stylesheets_do_not_grow(self):
        for plugin, counts in self.summary.items():
            if plugin == "framework":
                continue
            with self.subTest(plugin=plugin):
                self.assertIn(plugin, PLUGIN_RULES,
                              f"{plugin} is a new plugin: its stylesheet may hold tokens only (budget 0)")
                self.assertLessEqual(counts["rules"], PLUGIN_RULES[plugin],
                                     f"{plugin} gained styling rules; use framework components and tokens")
                self.assertLessEqual(counts["important"], PLUGIN_IMPORTANT[plugin])

    def test_new_plugins_hold_tokens_only(self):
        for plugin, counts in self.summary.items():
            if plugin != "framework" and plugin not in PLUGIN_RULES:
                self.assertEqual(counts["rules"], 0, plugin)

    def test_framework_does_not_grow_overrides(self):
        framework = self.summary["framework"]
        self.assertLessEqual(framework["duplicates"], FRAMEWORK_DUPLICATES,
                             "a framework selector gained another definition; edit the one that exists")
        self.assertLessEqual(framework["important"], FRAMEWORK_IMPORTANT)


if __name__ == "__main__":
    unittest.main()
