"""Hermetic checks for RDR2 settings help added by the per-game pass.

Guards the shared question-mark help so honest limits cannot silently
drop out of the schema: the prone one-handed test mode must keep its
blocked-scope note, and the Core Clock section must keep its location
stable for that note.
"""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "plugins" / "rdr2" / "settings_schema.json"


def load_schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


class SettingsHelpTests(unittest.TestCase):
    def test_prone_aim_mode_help_states_test_limits(self):
        help_text = load_schema()["help"]["Prone|GroundedAimMode"]
        self.assertIn("test mode", help_text)
        self.assertIn("Reload stays blocked", help_text)
        self.assertIn("longarms", help_text)
        self.assertIn("in-game validation", help_text)

    def test_core_clock_section_still_exists(self):
        categories = load_schema()["categories"]
        titles = [
            sub.get("title")
            for cat in categories
            for sub in cat.get("subs", [])
        ]
        self.assertIn("Core Clock", titles)


if __name__ == "__main__":
    unittest.main()
