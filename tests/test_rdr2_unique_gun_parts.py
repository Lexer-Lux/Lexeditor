"""Hermetic checks for the issue-107 unique-gun parts prototype (no game data)."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from games.rdr2 import unique_gun_parts as ugp


class PrototypeValidityTests(unittest.TestCase):
    def test_shipped_prototype_is_valid(self):
        self.assertEqual(ugp.validate_prototype(ugp.prototype()), [])

    def test_prototype_returns_an_independent_copy(self):
        first = ugp.prototype()
        first["parts"].append({"component": "X", "slot": "y"})
        self.assertEqual(ugp.validate_prototype(ugp.prototype()), [])

    def test_empty_parts_are_rejected(self):
        plan = ugp.prototype()
        plan["parts"] = []
        self.assertTrue(any("parts" in e for e in ugp.validate_prototype(plan)))

    def test_stat_toggle_only_part_is_rejected(self):
        plan = ugp.prototype()
        plan["parts"][0] = {
            "component": "COMPONENT_REVOLVER_SCHOFIELD_CALLOWAY_GRIP",
            "slot": "grip",
            "modifiers": {"price": 50},
            "engraved_mesh": "unproven",
        }
        self.assertTrue(
            any("stat toggle" in e for e in ugp.validate_prototype(plan))
        )

    def test_part_must_name_its_slot_and_mesh_source(self):
        plan = ugp.prototype()
        del plan["parts"][0]["slot"]
        del plan["parts"][1]["engraved_mesh"]
        errors = ugp.validate_prototype(plan)
        self.assertTrue(any("slot" in e for e in errors))
        self.assertTrue(any("engraved_mesh" in e for e in errors))

    def test_missing_catalog_entry_is_rejected(self):
        plan = ugp.prototype()
        plan["catalog_entries"] = []
        self.assertTrue(
            any("catalog_entries" in e for e in ugp.validate_prototype(plan))
        )

    def test_catalog_entry_must_unlock_a_planned_part(self):
        plan = ugp.prototype()
        plan["catalog_entries"][0]["unlocks"] = "COMPONENT_UNKNOWN"
        self.assertTrue(
            any("planned components" in e for e in ugp.validate_prototype(plan))
        )

    def test_pickup_must_grant_planned_parts(self):
        plan = ugp.prototype()
        plan["pickup_unlock"]["unlocks"] = ["COMPONENT_UNKNOWN"]
        errors = ugp.validate_prototype(plan)
        self.assertTrue(any("not a planned part" in e for e in errors))

    def test_every_required_verification_must_be_covered(self):
        plan = ugp.prototype()
        plan["verification"] = [
            item for item in plan["verification"] if item["id"] != "dual_wield"
        ]
        self.assertTrue(
            any("dual_wield" in e for e in ugp.validate_prototype(plan))
        )

    def test_unproven_mesh_must_be_owned_as_unknown(self):
        plan = ugp.prototype()
        plan["open_unknowns"] = ["Nothing pending."]
        self.assertTrue(
            any("engraved-mesh" in e for e in ugp.validate_prototype(plan))
        )

    def test_base_must_differ_from_unique_identity(self):
        plan = ugp.prototype()
        plan["base_weapon"] = plan["source_unique"]
        self.assertTrue(
            any("must differ" in e for e in ugp.validate_prototype(plan))
        )


if __name__ == "__main__":
    unittest.main()
