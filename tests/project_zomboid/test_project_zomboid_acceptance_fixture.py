from __future__ import annotations

from pathlib import Path
import unittest

from plugins.project_zomboid import core, zedscript


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "project_zomboid" / "fixtures"


class ProjectZomboidAcceptanceFixtureTests(unittest.TestCase):
    def test_fixture_is_a_real_editable_build42_project(self):
        info = core.read_mod_info(FIXTURE)
        self.assertEqual(info["fields"]["id"], "LexeditorPZAcceptance")
        self.assertEqual(info["fields"]["versionMin"], "42.20")

        items = core.read_items(FIXTURE)
        self.assertEqual(items["errors"], [])
        row = next(row for row in items["rows"] if row["id"] == "AcceptanceToken")
        self.assertEqual(row["module"], "LexeditorAcceptance")
        self.assertEqual(row["fields"]["Weight"], "0.25")
        self.assertEqual(row["fields"]["Icon"], "Radio")
        self.assertEqual(row["fields"]["DisplayCategory"], "Tool")

        inventory = zedscript.inventory(FIXTURE)
        self.assertEqual(inventory["errors"], [])
        record = next(row for row in inventory["rows"] if row["name"] == "AcceptanceToken")
        self.assertTrue(record["editable"])
        self.assertEqual(record["kind"], "item")


if __name__ == "__main__":
    unittest.main()
