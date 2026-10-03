"""Central plugin credits retain notices; pinned distributions keep licenses."""
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "plugins"

# The shippable issue-51 package pins its GPL copy by hash and verifies it at
# install time, so that copy stays with the package (see ff8/credits.md).
# The vendored FF8 Ultimate Editor source also keeps its upstream GPL copy;
# the complete notice and attribution remain in the central credits page.
ALLOWED_LICENSE_FILES = frozenset({
    "plugins/ff8/ffnx_issue_51/package/COPYING.TXT",
    "plugins/ff8/vendor/ff8ue/LICENSE",
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

    def test_vendored_ff8ue_license_is_pinned_and_in_central_credits(self):
        # read_text normalizes checkout line endings so Linux and Windows
        # verify the same upstream license text.
        vendor = PLUGINS / "ff8/vendor/ff8ue"
        license_text = (vendor / "LICENSE").read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(license_text.encode("utf-8")).hexdigest(),
                         "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986")
        credits = (PLUGINS / "ff8/credits.md").read_text(encoding="utf-8-sig")
        self.assertIn(license_text.strip(), credits,
                      "vendored license must remain complete in the central credits")
        self.assertIn("HobbitDur and FF8 Ultimate Editor contributors", credits)
        self.assertIn("97772fffe4c8a8df6e483a68804497958c6bc095", credits)
        self.assertIn("97772fffe4c8a8df6e483a68804497958c6bc095",
                      (vendor / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
