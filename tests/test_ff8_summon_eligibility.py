"""Summon states its own eligibility before any menu hook exists.

Monogamy gives each character one GF. A character with none has nothing to
summon, and choosing the slot does nothing, which reads as a bug rather than a
rule. The rule and the sentence it shows are settled here the way Draw's were,
so the menu hook has something verified to implement.
"""
import unittest

from games.ff8 import battle_issue_54 as battle


class SummonEligibility(unittest.TestCase):
    def test_a_character_with_no_gf_cannot_summon(self):
        self.assertFalse(battle.summon_command_available(junctioned_gf_count=0))

    def test_one_junctioned_gf_is_enough(self):
        self.assertTrue(battle.summon_command_available(junctioned_gf_count=1))

    def test_monogamy_is_not_assumed(self):
        # Monogamy is a separate tweak. Summon asks whether there is a GF, not
        # whether there is exactly one, so the rule holds with it off.
        self.assertTrue(battle.summon_command_available(junctioned_gf_count=3))

    def test_a_negative_count_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            battle.summon_command_available(junctioned_gf_count=-1)

    def test_the_grey_slot_says_why(self):
        reason = battle.summon_unavailable_reason(junctioned_gf_count=0)
        self.assertIn("No GF is junctioned", reason)
        # It says what to do about it, not only what is wrong.
        self.assertIn("Junction", reason)

    def test_a_usable_slot_says_nothing(self):
        self.assertEqual(battle.summon_unavailable_reason(junctioned_gf_count=1), "")

    def test_the_missing_addresses_are_declared_rather_than_guessed(self):
        # The grouped feature stays fail-closed until the GF slot's render and
        # select addresses are verified against the running game.
        self.assertTrue(any("Greying Summon" in blocker for blocker in battle.BLOCKERS))


if __name__ == "__main__":
    unittest.main()
