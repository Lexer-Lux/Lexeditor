"""Hermetic guards for the issue-111 replacement-icon inputs (no game, no art tool).

Issue 111 is now an artwork-quality task: the icons appear in game but look
poor, and replacement previews must come before any approval ask. The art
toolchain inputs live in games/rdr2/assets/item-icons. These tests lock that
the source PNGs and review previews for the named groups still exist, so a
future cleanup cannot silently drop an input. They judge presence only:
artwork quality and Lexer's approval still need the art toolchain and a
real session, and hull artwork has no checked-in source yet (see handoff).
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "games" / "rdr2" / "assets" / "item-icons"

# (group, source PNGs that must exist for that group)
REQUIRED_SOURCES = (
    ("pistol casings", ["lex_casing_pistol.png", "lex_casing_pistol-64.png"]),
    ("revolver casings", ["lex_casing_revolver.png", "lex_casing_revolver-64.png"]),
    ("repeater casings", ["lex_casing_repeater.png", "lex_casing_repeater-64.png"]),
    ("rifle casings", ["lex_casing_rifle.png", "lex_casing_rifle-64.png"]),
    ("shotgun casings", ["lex_casing_shotgun.png", "lex_casing_shotgun-64.png"]),
    ("varmint casings", ["lex_casing_varmint.png", "lex_casing_varmint-64.png"]),
    ("225 casings", ["lex_casing_225.png", "lex_casing_225-64.png"]),
    ("225 AP ammunition", ["lex_ammo_225.png", "lex_ammo_225-64.png"]),
    ("empty bottles", ["empty-bottle.png", "empty-bottle-source.png",
                       "lex_icon_empty_bottle.png"]),
)

REQUIRED_PREVIEWS = (
    "custom-inventory-icons-preview.png",
    "crafting-material-icons-preview.png",
)


class IconInputTests(unittest.TestCase):
    def test_named_group_sources_exist(self):
        for group, names in REQUIRED_SOURCES:
            for name in names:
                self.assertTrue((ICONS / name).is_file(), f"{group}: {name}")

    def test_review_previews_exist(self):
        for name in REQUIRED_PREVIEWS:
            self.assertTrue((ICONS / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
