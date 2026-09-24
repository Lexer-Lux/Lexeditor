"""Every plugin keeps exactly one top-level credits.md and no scattered notices."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"

# The shippable issue-51 package pins its GPL copy by hash and verifies it at
# install time, so that copy stays with the package (see ff8/credits.md).
ALLOWED_LICENSE_FILES = frozenset({
    "plugins/ff8/ffnx_issue_51/package/COPYING.TXT",
})
LEGACY_NAMES = re.compile(
    r"(?i)^(THIRD_PARTY.*|credits\.json|LICENSE.*|LICENCE.*|COPYING.*|NOTICE\.(md|txt))$"
)


def plugin_dirs() -> list[Path]:
    return sorted(path.parent for path in PLUGINS.glob("*/plugin.py"))


class PluginCreditsTests(unittest.TestCase):
    def test_every_plugin_has_exactly_one_top_level_credits_md(self):
        dirs = plugin_dirs()
        self.assertTrue(dirs, "no plugins discovered")
        for plugin in dirs:
            matches = [path for path in plugin.iterdir()
                       if path.is_file() and path.name.lower() == "credits.md"]
            self.assertEqual(len(matches), 1,
                             f"{plugin.name} must hold exactly one credits.md")
            credits = matches[0]
            self.assertEqual(credits.name, "credits.md",
                             f"{plugin.name} credits file must be exactly credits.md")
            text = credits.read_text(encoding="utf-8-sig")
            self.assertTrue(text.strip(), f"{plugin.name}/credits.md is empty")
            self.assertTrue(text.startswith("# "),
                            f"{plugin.name}/credits.md must start with a heading")

    def test_no_legacy_or_scattered_credit_files_remain(self):
        for path in sorted(PLUGINS.rglob("*")):
            if not path.is_file():
                continue
            if not LEGACY_NAMES.match(path.name):
                continue
            relative = path.relative_to(ROOT).as_posix()
            self.assertIn(relative, ALLOWED_LICENSE_FILES,
                          f"scattered credit file must move into credits.md: {relative}")

    def test_allowlist_does_not_go_stale(self):
        for relative in sorted(ALLOWED_LICENSE_FILES):
            self.assertTrue((ROOT / relative).is_file(),
                            f"allowlisted credit file is missing: {relative}")


if __name__ == "__main__":
    unittest.main()
