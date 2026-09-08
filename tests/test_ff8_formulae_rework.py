"""Contract tests for the FF8 Formulae Rework inventory and implemented arithmetic."""
from pathlib import Path
import unittest

from games.ff8 import formulae_rework, healing_rework, luck_accuracy


class FormulaeReworkTests(unittest.TestCase):
    EXPECTED_IDS = (
        "melee_damage",
        "magic_damage",
        "status_infliction",
        "spell_healing",
        "physical_accuracy",
        "mug_chance",
    )

    def test_formula_inventory_is_complete_and_ordered(self):
        self.assertEqual(tuple(row["id"] for row in formulae_rework.FORMULAE), self.EXPECTED_IDS)
        self.assertEqual(len({row["name"] for row in formulae_rework.FORMULAE}), len(self.EXPECTED_IDS))
        for row in formulae_rework.FORMULAE:
            self.assertTrue(row["replacement"])
            self.assertTrue(row["vanilla"])
            self.assertIn(row["status"], {
                formulae_rework.STATUS_IMPLEMENTED,
                formulae_rework.STATUS_INCOMPLETE,
            })

    def test_only_real_runtime_components_are_marked_implemented(self):
        self.assertEqual(
            formulae_rework.implemented_ids(),
            ("spell_healing", "physical_accuracy"),
        )
        runtime = {
            row["id"]: row["runtime"]
            for row in formulae_rework.FORMULAE
            if row["status"] == formulae_rework.STATUS_IMPLEMENTED
        }
        self.assertEqual(runtime, {
            "spell_healing": "healing_rework",
            "physical_accuracy": "luck_accuracy",
        })
        # Pin the native ownership too: a metadata-only row must never be able
        # to make the feature look complete.
        self.assertTrue(healing_rework.build_hext(True))
        self.assertTrue(luck_accuracy.build_hext(True))
        self.assertFalse(formulae_rework.available())
        self.assertEqual(
            formulae_rework.incomplete_ids(),
            ("melee_damage", "magic_damage", "status_infliction", "mug_chance"),
        )

    def test_healing_replacement_mirror(self):
        self.assertEqual(formulae_rework.healing_amount(12, 40), 480)
        self.assertEqual(formulae_rework.healing_amount(12, 40, shell=True), 240)

    def test_physical_accuracy_uses_full_attacker_luck(self):
        self.assertEqual(formulae_rework.physical_accuracy_effective(80, 30, 20, 10), 80)
        self.assertEqual(formulae_rework.physical_accuracy_effective(80, 80, 0, 0), 100)
        self.assertEqual(formulae_rework.physical_accuracy_effective(20, 0, 80, 80), 0)

    def test_requested_mug_formula_preview_and_clamp(self):
        self.assertEqual(formulae_rework.mug_chance_percent(40, 50, 70), 80)
        self.assertEqual(formulae_rework.mug_chance_percent(0, 0, 255), 100)
        self.assertEqual(formulae_rework.mug_chance_percent(100, 255, 0), 0)

    def test_mug_contract_does_not_mislabel_native_rate_as_difficulty(self):
        row = next(row for row in formulae_rework.FORMULAE if row["id"] == "mug_chance")
        self.assertIn("Mug Difficulty", row["replacement"])
        self.assertIn("Mug rate", row["vanilla"])
        self.assertEqual(row["status"], formulae_rework.STATUS_INCOMPLETE)
        self.assertIn("Difficulty", row["blocker"])
        self.assertIn("stored-rate", row["blocker"])

    def test_editor_does_not_hard_code_a_fake_complete_formula_inventory(self):
        # Once integration lands, every row must be supplied by settings data;
        # this assertion prevents the old misleading sentence from returning.
        editor = (Path(__file__).resolve().parents[1] / "games/ff8/editor.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("formula cards below define the complete requested rework", editor)


if __name__ == "__main__":
    unittest.main()
