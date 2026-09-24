"""Contracts for the FF8 battle reward screen, GitHub issue #466."""
from pathlib import Path
import tempfile
import unittest

from plugins.ff8 import battle_results_issue_466 as battle_results
from plugins.ff8 import gameplay_settings

ROOT = Path(__file__).resolve().parents[2]

NAMES = {147: "Shear Feather", 1: "Potion", 2: "Hi-Potion"}
HELPS = {
    147: "Bird's feather that flies on wind.",
    1: "Restores HP.",
    2: "A887B8C9D0E1F2G3H4I5J6K7L8 super-calibration overflow wording pack",
}


class BattleResultsTests(unittest.TestCase):
    def test_default_is_off_and_tweak_is_registered(self):
        self.assertFalse(gameplay_settings.DEFAULT_BATTLE_RESULTS_HELP)
        self.assertFalse(battle_results.DEFAULT_BATTLE_RESULTS_HELP)
        self.assertIn("battleResultsHelp", gameplay_settings.ACCEPTED_TWEAKS)

    def test_load_defaults_and_forces_off_without_hooks(self):
        with tempfile.TemporaryDirectory(prefix="ff8-battle-results-") as directory:
            project = Path(directory)
            defaults = gameplay_settings.load(project)
            self.assertIs(defaults["battleResultsHelp"], False)
            self.assertFalse(defaults["battleResultsHelpAvailable"])
            self.assertIn("no proved native drawing hooks",
                          defaults["battleResultsHelpBlocker"])
            gameplay_settings.settings_path(project).write_text(
                '{"battleResultsHelp": true}', encoding="utf-8",
            )
            # No proved drawing hooks: a stored true never loads as enabled.
            self.assertIs(gameplay_settings.load(project)["battleResultsHelp"], False)

    def test_disabled_build_emits_no_reward_bytes(self):
        patch = gameplay_settings.build_hext(25, False)
        self.assertIn("Battle Results Item Help is disabled", patch)
        with self.assertRaisesRegex(ValueError, "no proved native drawing hooks"):
            battle_results.build_hext(True)

    def test_editor_exposes_gated_tweak(self):
        editor = (ROOT / "plugins/ff8/boot.js").read_text(encoding="utf-8")
        self.assertIn('"aria-label":"Battle Results Item Help"', editor)
        self.assertIn('row("BATTLE RESULTS ITEM HELP"', editor)
        self.assertIn("battleResultsHelp:state.data.settings.battleResultsHelp", editor)

    def test_single_reward_keeps_name_quantity_and_help(self):
        rows = battle_results.build_reward_rows(
            [{"itemId": 147, "quantity": 1}], NAMES, HELPS)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["name"], "Shear Feather")
        self.assertEqual(row["quantity"], 1)
        self.assertEqual(row["helpLines"], ["Bird's feather that flies on wind."])
        self.assertEqual(row["height"], 1)

    def test_several_rewards_stay_visible_together(self):
        rows = battle_results.build_reward_rows(
            [{"itemId": 147, "quantity": 1}, {"itemId": 1, "quantity": 3}],
            NAMES, HELPS)
        self.assertEqual([(row["name"], row["quantity"]) for row in rows],
                         [("Shear Feather", 1), ("Potion", 3)])
        for row in rows:
            self.assertTrue(row["helpLines"])

    def test_long_descriptions_wrap_and_size_rows_without_overlap(self):
        rows = battle_results.build_reward_rows(
            [{"itemId": 2, "quantity": 2}, {"itemId": 1, "quantity": 1}],
            NAMES, HELPS, help_width=20)
        self.assertGreater(rows[0]["height"], 1)
        self.assertEqual(rows[0]["height"], len(rows[0]["helpLines"]))
        for line in rows[0]["helpLines"]:
            self.assertLessEqual(len(line), 20)
        table = battle_results.layout_table(rows, help_width=20)
        self.assertEqual([column["id"] for column in table["columns"]],
                         ["item", "quantity", "help"])
        first, second = table["rows"]
        self.assertEqual(first["y"], 0)
        self.assertEqual(second["y"], first["height"])
        self.assertEqual(table["totalHeight"], first["height"] + second["height"])

    def test_modded_descriptions_are_used_verbatim(self):
        helps = dict(HELPS)
        helps[1] = "Modded: restores 9999 HP and cures all."
        rows = battle_results.build_reward_rows(
            [{"itemId": 1, "quantity": 1}], NAMES, helps)
        self.assertIn("Modded:", rows[0]["helpLines"][0])

    def test_confirm_awards_every_reward_exactly_once(self):
        inventory = {147: 4, 1: 0}
        rewards = [{"itemId": 147, "quantity": 1},
                   {"itemId": 1, "quantity": 3},
                   {"itemId": 1, "quantity": 2}]
        awarded = battle_results.apply_rewards(inventory, rewards)
        self.assertEqual(awarded, {147: 5, 1: 5})
        # The caller's stock is untouched; confirmation returns new stock.
        self.assertEqual(inventory, {147: 4, 1: 0})

    def test_invalid_rewards_are_rejected(self):
        with self.assertRaises(ValueError):
            battle_results.build_reward_rows(
                [{"itemId": 200, "quantity": 1}], NAMES, HELPS)
        with self.assertRaises(ValueError):
            battle_results.build_reward_rows(
                [{"itemId": 1, "quantity": 0}], NAMES, HELPS)
        with self.assertRaises(ValueError):
            battle_results.build_reward_rows(
                [{"itemId": 3, "quantity": 1}], NAMES, HELPS)
        with self.assertRaises(ValueError):
            battle_results.apply_rewards({1: -1}, [{"itemId": 1, "quantity": 1}])

    def test_item_text_comes_from_kernel_sections(self):
        kernel_rows = {"rows": [
            {"sectionId": 39, "recordId": 0, "slot": 0, "value": "Potion"},
            {"sectionId": 39, "recordId": 0, "slot": 1, "value": "Restores HP."},
            {"sectionId": 40, "recordId": 114, "slot": 0, "value": "Shear Feather"},
            {"sectionId": 40, "recordId": 114, "slot": 1,
             "value": "Bird's feather that flies on wind."},
            {"sectionId": 32, "recordId": 1, "slot": 0, "value": "Attack"},
        ]}
        text = battle_results.item_text_from_kernel(kernel_rows)
        self.assertEqual(text["names"][0], "Potion")
        self.assertEqual(text["helps"][0], "Restores HP.")
        self.assertEqual(text["names"][147], "Shear Feather")
        self.assertEqual(text["helps"][147], "Bird's feather that flies on wind.")
        with self.assertRaises(ValueError):
            battle_results.item_text_from_kernel({"rows": "nope"})


if __name__ == "__main__":
    unittest.main()
