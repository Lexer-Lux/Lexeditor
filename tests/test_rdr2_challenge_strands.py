"""Hermetic checks for the issue-231/232 strand contract (no game data)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugins.rdr2 import challenge_strands as cs


def valid_plan():
    return {
        "approach": "runtime_strand_overlay",
        "interface": "runtime-driven challenge panel",
        "visible_strands": 1,
        "progress_correct": True,
        "open_unknowns": [
            "runtime interface approach",
            "save behavior",
            "progress behavior",
        ],
    }


class ChallengeStrandTests(unittest.TestCase):
    def test_menu_limit_recorded(self):
        self.assertEqual(cs.VANILLA_MENU_LINKS, 9)

    def test_valid_plan_passes(self):
        self.assertEqual(cs.validate_strand_plan(valid_plan()), [])

    def test_data_only_link_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "data_only_menu_link"
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("data_only_menu_link" in e for e in errors))

    def test_split_root_is_rejected(self):
        plan = valid_plan()
        plan["approach"] = "split_root_ranks"
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("split_root_ranks" in e for e in errors))

    def test_missing_interface_is_rejected(self):
        plan = valid_plan()
        plan["interface"] = ""
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("runtime-interface" in e for e in errors))

    def test_duplicate_visible_strands_rejected(self):
        plan = valid_plan()
        plan["visible_strands"] = 2
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("exactly one visible strand" in e for e in errors))

    def test_broken_progress_is_rejected(self):
        plan = valid_plan()
        plan["progress_correct"] = False
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("correct progress" in e for e in errors))

    def test_unowned_save_behavior_is_rejected(self):
        plan = valid_plan()
        plan["open_unknowns"] = ["runtime interface approach", "progress behavior"]
        errors = cs.validate_strand_plan(plan)
        self.assertTrue(any("save behavior" in e for e in errors))

    def test_non_mapping_plan_is_rejected(self):
        self.assertTrue(cs.validate_strand_plan("more strands"))


def valid_interface_probe():
    return {
        "interface": "challenge-menu datastore hook",
        "approach": "runtime menu replacement trial",
        "menu_behavior": "nine links intact, tenth via submenu",
        "progress_behavior": "ranks advance on one strand",
        "save_behavior": "progress persists across reload",
        "visible_strands": 1,
        "duplicate_entries": False,
    }


class InterfaceProbeTests(unittest.TestCase):
    def test_valid_interface_probe_passes(self):
        self.assertEqual(cs.validate_interface_probe(valid_interface_probe()), [])

    def test_split_root_probe_is_rejected(self):
        probe = valid_interface_probe()
        probe["approach"] = "split_root_ranks trial"
        errors = cs.validate_interface_probe(probe)
        self.assertTrue(any("split_root_ranks" in e for e in errors))

    def test_duplicate_entries_are_rejected(self):
        probe = valid_interface_probe()
        probe["duplicate_entries"] = True
        errors = cs.validate_interface_probe(probe)
        self.assertTrue(any("Duplicate menu entries" in e for e in errors))

    def test_unobserved_save_behavior_is_rejected(self):
        probe = valid_interface_probe()
        del probe["save_behavior"]
        errors = cs.validate_interface_probe(probe)
        self.assertTrue(any("save_behavior" in e for e in errors))

    def test_extra_visible_strand_is_rejected(self):
        probe = valid_interface_probe()
        probe["visible_strands"] = 2
        errors = cs.validate_interface_probe(probe)
        self.assertTrue(any("exactly one visible strand" in e for e in errors))

    def test_unnamed_interface_is_rejected(self):
        probe = valid_interface_probe()
        del probe["interface"]
        errors = cs.validate_interface_probe(probe)
        self.assertTrue(any("runtime-interface approach" in e for e in errors))

    def test_non_mapping_probe_is_rejected(self):
        self.assertTrue(cs.validate_interface_probe("hooked menu"))


if __name__ == "__main__":
    unittest.main()
