"""Hermetic guards for the issue-161 per-action honor finding (no game).

Issue 161 asks for a real editable amount beside each honor action. The
recorded finding is that Story Mode applies shared magnitude tiers after the
event fires, so per-action interception is unproven and the editor must not
pretend independent per-event amounts exist. These tests lock that reality
into plugins.rdr2.honor_actions: event edits cannot carry an amount, the
editor-facing note says tiers are shared, and the 21-event/19-tier tables
round-trip intact.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import honor_actions as honor


class PerActionAmountGuards(unittest.TestCase):
    def test_event_edits_reject_an_independent_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "honor.csv"
            with self.assertRaisesRegex(ValueError, "no independent amount"):
                honor.save_honor_actions(path, [
                    {"id": "HONOR_EVENT_THEFT", "amount": 7},
                ])

    def test_tier_amounts_stay_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "honor.csv"
            count = honor.save_honor_actions(path, [
                {"id": "tier_+5", "amount": 6},
            ])
            self.assertEqual(count, 1)
            data = honor.read_honor_actions(path)
            tier = next(row for row in data["tiers"] if row["id"] == "tier_+5")
            self.assertEqual(tier["amount"], 6)

    def test_scope_note_states_shared_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = honor.read_honor_actions(Path(tmp) / "honor.csv")
            self.assertIn("shared tiers", data["scopeNote"])
            self.assertIn("not independent values", data["scopeNote"])

    def test_event_and_tier_tables_keep_their_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = honor.read_honor_actions(Path(tmp) / "honor.csv")
            self.assertEqual(len(data["events"]), 21)
            self.assertEqual(len(data["tiers"]), 19)
            bits = [row["bit"] for row in data["events"]]
            self.assertEqual(len(set(bits)), 21)


if __name__ == "__main__":
    unittest.main()
