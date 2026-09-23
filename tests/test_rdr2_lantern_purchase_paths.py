"""Hermetic checks for the issue-291 lantern purchase-path finding (no game data)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import lantern_purchase_paths as lpp


def valid_plan():
    return {
        "steps": [
            {"record": "SADDLE_LANTERN", "route": "purchase", "shop": "horse_shop"},
            {"record": "WEAPON_MELEE_LANTERN", "route": "loot"},
        ],
        "open_unknowns": ["Light-control fixes for the saddle lantern are still open."],
    }


class LanternPathTests(unittest.TestCase):
    def test_recorded_finding_close_purchase_loopholes(self):
        by_record = {entry["record"]: entry for entry in lpp.records()}
        self.assertTrue(by_record["SADDLE_LANTERN"]["purchasable"])
        self.assertEqual(by_record["SADDLE_LANTERN"]["shop"], "horse_shop")
        self.assertTrue(by_record["HALLOWEEN_LANTERN"]["purchasable"])
        self.assertFalse(by_record["WEAPON_MELEE_LANTERN"]["purchasable"])
        self.assertFalse(by_record["WEAPON_MELEE_DAVY_LANTERN"]["purchasable"])

    def test_records_returns_an_independent_copy(self):
        first = lpp.records()
        first.append({"record": "X"})
        self.assertEqual(len(lpp.records()), 4)

    def test_valid_plan_passes(self):
        self.assertEqual(lpp.validate_lantern_test(valid_plan()), [])

    def test_belt_lantern_cannot_be_purchase_tested(self):
        plan = valid_plan()
        plan["steps"][1] = {"record": "WEAPON_MELEE_LANTERN", "route": "purchase"}
        errors = lpp.validate_lantern_test(plan)
        self.assertTrue(any("no buy path" in e for e in errors))

    def test_saddle_lantern_needs_its_own_shop(self):
        plan = valid_plan()
        plan["steps"][0] = {"record": "SADDLE_LANTERN", "route": "purchase", "shop": "fence"}
        errors = lpp.validate_lantern_test(plan)
        self.assertTrue(any("horse_shop" in e for e in errors))

    def test_unknown_record_is_rejected(self):
        plan = valid_plan()
        plan["steps"].append({"record": "MAGIC_LANTERN", "route": "loot"})
        self.assertTrue(any("unknown lantern record" in e for e in lpp.validate_lantern_test(plan)))

    def test_unknown_route_is_rejected(self):
        plan = valid_plan()
        plan["steps"][1] = {"record": "WEAPON_MELEE_LANTERN", "route": "barter"}
        self.assertTrue(any("unknown acquisition route" in e for e in lpp.validate_lantern_test(plan)))

    def test_light_control_fixes_must_be_owned(self):
        plan = valid_plan()
        plan["open_unknowns"] = ["Nothing pending."]
        self.assertTrue(any("light-control" in e for e in lpp.validate_lantern_test(plan)))

    def test_empty_steps_rejected(self):
        plan = valid_plan()
        plan["steps"] = []
        self.assertTrue(any("steps" in e for e in lpp.validate_lantern_test(plan)))


if __name__ == "__main__":
    unittest.main()
